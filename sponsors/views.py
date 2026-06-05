from __future__ import annotations

import logging

from django.contrib import messages
from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.views.generic import TemplateView

from accounts.views import can_grant_bearseeker_privileges, is_moderator

from .forms import SponsorApplicationForm
from .models import SponsorApplication, SponsorAuditLog, SponsorCell, SponsorPayment
from .services import (
    SponsorPaymentVerificationError,
    SponsorStripeConfigurationError,
    approve_application,
    build_roadmap_context,
    cancel_pending_application,
    checkout_created,
    checkout_failed,
    construct_stripe_event,
    create_checkout_session,
    expire_application,
    handle_stripe_event,
    mark_refund_completed,
    mark_application_ready_for_review,
    record_audit,
    reject_application,
    request_application_changes,
    unpublish_application,
)

logger = logging.getLogger(__name__)


class AnnualContractView(TemplateView):
    template_name = "sponsors/annual_contract.html"


def puzzle_page(request):
    cells = SponsorCell.objects.all().order_by("ring", "position_in_ring")
    cells_data = [cell.as_dict() for cell in cells]

    public_cells = cells.exclude(ring=0)
    active_statuses = [SponsorCell.Status.ACTIVE, SponsorCell.Status.SOLD]
    reserved_statuses = [
        SponsorCell.Status.PAYMENT_PENDING,
        SponsorCell.Status.PAID_PENDING_APPROVAL,
        SponsorCell.Status.RESERVED,
    ]
    sold = public_cells.filter(status__in=active_statuses).count()
    reserved = public_cells.filter(status__in=reserved_statuses).count()
    available = public_cells.filter(status=SponsorCell.Status.AVAILABLE).count()
    sellable_total = public_cells.count()

    return render(
        request,
        "sponsors/puzzle.html",
        {
            "cells_data": cells_data,
            "sold": sold,
            "reserved": reserved,
            "available": available,
            "sellable_total": sellable_total,
            "percent_sold": round((sold / sellable_total * 100) if sellable_total else 0),
            "stripe_publishable_key": getattr(settings, "STRIPE_PUBLISHABLE_KEY", ""),
        },
    )


@require_GET
def cell_detail(request, cell_id):
    cell = get_object_or_404(SponsorCell, pk=cell_id)
    data = cell.as_dict()

    if request.user.is_staff or is_moderator(request.user):
        latest_application = cell.applications.order_by("-created_at").first()
        data["is_admin"] = True
        data["enquiry_name"] = cell.enquiry_name
        data["enquiry_email"] = cell.enquiry_email
        data["enquiry_company"] = cell.enquiry_company
        data["enquiry_website"] = cell.enquiry_website
        data["enquiry_message"] = cell.enquiry_message
        data["enquiry_submitted_at"] = (
            cell.enquiry_submitted_at.isoformat()
            if cell.enquiry_submitted_at
            else None
        )
        data["logo_pending"] = cell.logo_pending.url if cell.logo_pending else None
        data["application_id"] = latest_application.pk if latest_application else None
        data["application_status"] = latest_application.status if latest_application else ""
        data["application_detail_url"] = (
            reverse("sponsors:moderation_application_detail", args=[latest_application.pk])
            if latest_application
            else ""
        )

    return JsonResponse(data)


def _first_form_error(form: SponsorApplicationForm) -> str:
    for field, errors in form.errors.items():
        if field in (None, "__all__"):
            return str(errors[0])
        if field == "terms_accepted":
            return f"Terms accepted: {errors[0]}"
        if field == "logo_rights_confirmed":
            return f"Image rights confirmed: {errors[0]}"
        if field == "approval_acknowledged":
            return f"Approval acknowledgement: {errors[0]}"
        label = form.fields[field].label if field in form.fields else field
        return f"{label}: {errors[0]}"
    return "Please check the sponsor application form."


@require_POST
def cell_enquire(request, cell_id):
    required_confirmations = {
        "logo_rights_confirmed": "Image rights confirmed",
        "terms_accepted": "Terms accepted",
        "approval_acknowledged": "Approval acknowledgement",
    }
    for field_name, label in required_confirmations.items():
        if field_name not in request.POST:
            return JsonResponse({"error": f"{label}: This field is required."}, status=400)

    form = SponsorApplicationForm(request.POST, request.FILES)
    if not form.is_valid():
        return JsonResponse({"error": _first_form_error(form)}, status=400)

    with transaction.atomic():
        cell = SponsorCell.objects.select_for_update().get(pk=cell_id)
        if not cell.is_available_for_checkout:
            return JsonResponse(
                {"error": "This sponsor spot is no longer available."},
                status=400,
            )

        application = form.save(commit=False)
        application.cell = cell
        application.status = SponsorApplication.Status.PAYMENT_PENDING
        application.price_net_cents = cell.price_net_cents
        application.currency = "eur"
        application.product_type = cell.product_type
        application.term_days = 30 if cell.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY else 365
        application.save()

        SponsorPayment.objects.create(
            application=application,
            status=SponsorPayment.Status.PENDING,
            net_amount_cents=application.price_net_cents,
            currency=application.currency,
        )

        cell.status = SponsorCell.Status.PAYMENT_PENDING
        cell.enquiry_name = application.contact_name
        cell.enquiry_email = application.email
        cell.enquiry_company = application.sponsor_name
        cell.enquiry_website = application.website_url
        cell.enquiry_message = application.sponsor_note
        cell.enquiry_submitted_at = timezone.now()
        cell.save()

        record_audit(
            action=SponsorAuditLog.Action.APPLICATION_CREATED,
            application=application,
            to_status=application.status,
            metadata={"cell_number": cell.cell_number, "price_net_cents": application.price_net_cents},
        )

    try:
        session_info = create_checkout_session(application, request=request)
    except SponsorStripeConfigurationError as exc:
        checkout_failed(application, str(exc))
        return JsonResponse(
            {"error": "Online checkout is not configured yet. Please contact culineire@bearcave.ie."},
            status=503,
        )
    except Exception as exc:
        logger.exception("Sponsor checkout creation failed for application %s", application.pk)
        checkout_failed(application, str(exc))
        return JsonResponse(
            {"error": "Checkout could not be started. Please try again."},
            status=502,
        )

    checkout_created(application, session_info)
    return JsonResponse({"ok": True, "checkout_url": session_info.checkout_url})


@require_POST
def cell_moderate(request, cell_id):
    if not is_moderator(request.user):
        return JsonResponse({"error": "Forbidden"}, status=403)

    cell = get_object_or_404(SponsorCell, pk=cell_id)
    action = request.POST.get("action", "")
    latest_application = cell.applications.order_by("-created_at").first()

    if latest_application and action == "approve":
        try:
            approve_application(latest_application.pk, request.user)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        return JsonResponse({"ok": True, "status": SponsorCell.Status.ACTIVE})

    if latest_application and action == "reject":
        reject_application(latest_application.pk, request.user, request.POST.get("reason", ""))
        return JsonResponse({"ok": True, "status": cell.status})

    if action == "edit":
        sponsor_name = request.POST.get("sponsor_name", "").strip()
        sponsor_url = _normalize_url(request.POST.get("sponsor_url", "").strip())
        if sponsor_name:
            cell.sponsor_name = sponsor_name
        if sponsor_url:
            cell.sponsor_url = sponsor_url
        try:
            if request.POST.get("offset_x") is not None:
                cell.logo_offset_x = float(request.POST["offset_x"])
            if request.POST.get("offset_y") is not None:
                cell.logo_offset_y = float(request.POST["offset_y"])
            if request.POST.get("scale") is not None:
                cell.logo_scale = float(request.POST["scale"])
        except (ValueError, TypeError):
            pass
        cell.save()
        return JsonResponse({"ok": True, "status": cell.status})

    return JsonResponse({"error": "Use the sponsor moderation pages for this action."}, status=400)


def _normalize_url(url):
    if url and not url.lower().startswith(("http://", "https://")):
        return "https://" + url
    return url


def checkout_success(request):
    session_id = request.GET.get("session_id", "").strip()
    application = None
    if session_id:
        payment = (
            SponsorPayment.objects.select_related("application", "application__cell")
            .filter(stripe_checkout_session_id=session_id)
            .first()
        )
        application = payment.application if payment else None
    payment_details = None
    if application:
        payment = getattr(application, "payment", None)
        if payment and payment.total_amount_cents:
            payment_details = {
                "net": f"€{payment.net_amount_cents / 100:,.2f}",
                "vat": f"€{payment.vat_amount_cents / 100:,.2f}",
                "total": f"€{payment.total_amount_cents / 100:,.2f}",
            }
    return render(
        request,
        "sponsors/checkout_success.html",
        {
            "application": application,
            "payment_details": payment_details,
            "session_id": session_id,
        },
    )


def checkout_cancel(request):
    reference = request.GET.get("application", "").strip()
    application = cancel_pending_application(reference) if reference else None
    return render(
        request,
        "sponsors/checkout_cancel.html",
        {"application": application},
    )


@csrf_exempt
@require_POST
def stripe_webhook(request):
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")
    try:
        event = construct_stripe_event(request.body, signature)
    except SponsorStripeConfigurationError as exc:
        logger.warning("Stripe webhook configuration error: %s", exc)
        return JsonResponse({"error": "Webhook not configured."}, status=503)
    except Exception:
        logger.warning("Stripe webhook signature verification failed.")
        return JsonResponse({"error": "Invalid Stripe signature."}, status=400)

    try:
        result = handle_stripe_event(event)
    except SponsorPaymentVerificationError as exc:
        logger.warning("Stripe webhook verification failed: %s", exc)
        return JsonResponse({"error": "Payment verification failed."}, status=400)
    except Exception:
        logger.exception("Stripe webhook processing failed.")
        return JsonResponse({"error": "Webhook processing failed."}, status=500)

    return JsonResponse({"ok": True, "duplicate": result.get("duplicate", False)})


def _require_moderator(user):
    if not is_moderator(user):
        raise Http404


def _require_super_admin(user):
    if not can_grant_bearseeker_privileges(user):
        raise Http404


def moderation_applications(request):
    _require_moderator(request.user)
    status_filter = request.GET.get("status", SponsorApplication.Status.PAID_PENDING_APPROVAL)
    valid_statuses = {choice[0] for choice in SponsorApplication.Status.choices}
    if status_filter not in valid_statuses and status_filter != "all":
        status_filter = SponsorApplication.Status.PAID_PENDING_APPROVAL

    qs = SponsorApplication.objects.select_related("cell", "payment").order_by("-created_at")
    if status_filter != "all":
        qs = qs.filter(status=status_filter)

    status_counts = {
        status: SponsorApplication.objects.filter(status=status).count()
        for status, _label in SponsorApplication.Status.choices
    }
    status_options = [{"value": "all", "label": "All", "count": SponsorApplication.objects.count()}]
    status_options.extend(
        {"value": status, "label": label, "count": status_counts[status]}
        for status, label in SponsorApplication.Status.choices
    )
    return render(
        request,
        "sponsors/moderation_applications.html",
        {
            "applications": qs,
            "status_filter": status_filter,
            "status_options": status_options,
        },
    )


def moderation_cells(request):
    _require_moderator(request.user)
    cells = SponsorCell.objects.order_by("ring", "position_in_ring")
    return render(request, "sponsors/moderation_cells.html", {"cells": cells})


def moderation_application_detail(request, application_id):
    _require_moderator(request.user)
    application = get_object_or_404(
        SponsorApplication.objects.select_related("cell", "payment", "approved_by", "rejected_by"),
        pk=application_id,
    )

    if request.method == "POST":
        action = request.POST.get("action", "")
        note = request.POST.get("note", "").strip()
        try:
            if action == "approve":
                approve_application(application.pk, request.user)
                messages.success(request, "Sponsor approved and published.")
            elif action == "reject":
                reject_application(application.pk, request.user, note)
                messages.warning(request, "Sponsor rejected. Manual refund is required if payment was completed.")
            elif action == "request_changes":
                request_application_changes(application.pk, request.user, note)
                messages.warning(request, "Changes requested. The paid placement remains reserved.")
            elif action == "ready_for_review":
                mark_application_ready_for_review(application.pk, request.user, note)
                messages.success(request, "Sponsor application marked ready for review.")
            elif action == "mark_refunded":
                mark_refund_completed(application.pk, request.user, note)
                messages.success(request, "Refund marked completed and the sponsor cell was released.")
            elif action == "unpublish":
                unpublish_application(application.pk, request.user, note)
                messages.warning(request, "Sponsor image unpublished.")
            elif action == "expire":
                expire_application(application.pk, request.user, note)
                messages.warning(request, "Sponsorship marked expired.")
            else:
                messages.error(request, "Unknown sponsor moderation action.")
        except ValueError as exc:
            messages.error(request, str(exc))
        return redirect("sponsors:moderation_application_detail", application_id=application.pk)

    audit_logs = application.audit_logs.select_related("actor").order_by("-created_at")[:50]
    payment = getattr(application, "payment", None)
    action_flags = {
        "can_approve": application.status == SponsorApplication.Status.PAID_PENDING_APPROVAL,
        "can_request_changes": application.status == SponsorApplication.Status.PAID_PENDING_APPROVAL,
        "can_ready_for_review": application.status == SponsorApplication.Status.CHANGES_REQUESTED,
        "can_reject_paid": application.status in {
            SponsorApplication.Status.PAID_PENDING_APPROVAL,
            SponsorApplication.Status.CHANGES_REQUESTED,
        },
        "can_mark_refunded": application.status == SponsorApplication.Status.REFUND_REQUIRED,
        "can_unpublish": application.status == SponsorApplication.Status.APPROVED,
        "can_expire": application.status == SponsorApplication.Status.APPROVED,
    }
    return render(
        request,
        "sponsors/moderation_application_detail.html",
        {"application": application, "payment": payment, "audit_logs": audit_logs, **action_flags},
    )


def sponsor_roadmap(request):
    _require_super_admin(request.user)
    return render(
        request,
        "sponsors/roadmap.html",
        {"roadmap": build_roadmap_context()},
    )
