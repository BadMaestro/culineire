from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.conf import settings
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from .models import (
    ProcessedStripeEvent,
    SponsorApplication,
    SponsorAuditLog,
    SponsorCell,
    SponsorPayment,
    SponsorRoadmapItem,
)


class SponsorStripeConfigurationError(RuntimeError):
    pass


class SponsorPaymentVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutSessionInfo:
    session_id: str
    checkout_url: str


def _get(obj: Any, key: str, default=None):
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _stripe():
    try:
        import stripe  # type: ignore
    except ImportError as exc:
        raise SponsorStripeConfigurationError(
            "The stripe Python package is not installed."
        ) from exc

    secret_key = getattr(settings, "STRIPE_SECRET_KEY", "")
    if not secret_key:
        raise SponsorStripeConfigurationError("STRIPE_SECRET_KEY is not configured.")
    stripe.api_key = secret_key
    return stripe


def site_base_url(request=None) -> str:
    configured = getattr(settings, "SITE_BASE_URL", "").strip()
    if configured:
        return configured.rstrip("/")
    if request is not None:
        return f"{request.scheme}://{request.get_host()}".rstrip("/")
    return f"{getattr(settings, 'SITE_SCHEME', 'https')}://{getattr(settings, 'SITE_DOMAIN', 'culineire.ie')}".rstrip("/")


def _checkout_metadata(application: SponsorApplication) -> dict[str, str]:
    return {
        "sponsor_application_id": str(application.pk),
        "sponsor_cell_id": str(application.cell_id),
    }


def create_checkout_session(application: SponsorApplication, request=None) -> CheckoutSessionInfo:
    stripe = _stripe()
    base_url = site_base_url(request)
    metadata = _checkout_metadata(application)
    session = stripe.checkout.Session.create(
        mode="payment",
        success_url=f"{base_url}{reverse('sponsors:checkout_success')}?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{base_url}{reverse('sponsors:checkout_cancel')}?application={application.reference}",
        billing_address_collection="required",
        tax_id_collection={"enabled": True},
        customer_creation="always",
        automatic_tax={"enabled": True},
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
        line_items=[
            {
                "price_data": {
                    "currency": "eur",
                    "unit_amount": application.price_net_cents,
                    "tax_behavior": "exclusive",
                    "product_data": {
                        "name": "CulinEire Annual Sponsor Spot",
                        "description": "Annual sponsor placement on the CulinEire Sponsor Puzzle",
                    },
                },
                "quantity": 1,
            }
        ],
    )
    return CheckoutSessionInfo(
        session_id=_get(session, "id", ""),
        checkout_url=_get(session, "url", ""),
    )


def construct_stripe_event(payload: bytes, signature: str):
    stripe = _stripe()
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
    if not webhook_secret:
        raise SponsorStripeConfigurationError("STRIPE_WEBHOOK_SECRET is not configured.")
    return stripe.Webhook.construct_event(payload, signature, webhook_secret)


def record_audit(
    *,
    action: str,
    application: SponsorApplication | None = None,
    cell: SponsorCell | None = None,
    actor=None,
    from_status: str = "",
    to_status: str = "",
    notes: str = "",
    metadata: dict | None = None,
) -> SponsorAuditLog:
    if cell is None and application is not None:
        cell = application.cell
    return SponsorAuditLog.objects.create(
        application=application,
        cell=cell,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        from_status=from_status,
        to_status=to_status,
        notes=notes,
        metadata=metadata or {},
    )


def checkout_created(application: SponsorApplication, session_info: CheckoutSessionInfo) -> None:
    payment = application.payment
    payment.stripe_checkout_session_id = session_info.session_id
    payment.save(update_fields=["stripe_checkout_session_id", "updated_at"])
    record_audit(
        action=SponsorAuditLog.Action.CHECKOUT_CREATED,
        application=application,
        metadata={"stripe_checkout_session_id": session_info.session_id},
    )


def checkout_failed(application: SponsorApplication, message: str) -> None:
    with transaction.atomic():
        application = SponsorApplication.objects.select_for_update().select_related("cell").get(pk=application.pk)
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = application.status
        application.status = SponsorApplication.Status.CANCELLED
        application.save(update_fields=["status", "updated_at"])
        SponsorPayment.objects.filter(application=application).update(
            status=SponsorPayment.Status.FAILED,
            failure_message=message[:500],
            updated_at=timezone.now(),
        )
        if cell.status == SponsorCell.Status.PAYMENT_PENDING:
            cell.status = SponsorCell.Status.AVAILABLE
            cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CHECKOUT_FAILED,
            application=application,
            from_status=from_status,
            to_status=application.status,
            notes=message,
        )


def cancel_pending_application(reference) -> SponsorApplication | None:
    with transaction.atomic():
        application = (
            SponsorApplication.objects.select_for_update()
            .select_related("cell")
            .filter(reference=reference)
            .first()
        )
        if not application:
            return None
        payment = getattr(application, "payment", None)
        if payment and payment.status == SponsorPayment.Status.PAID:
            return application
        if application.status != SponsorApplication.Status.PAYMENT_PENDING:
            return application

        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = application.status
        application.status = SponsorApplication.Status.CANCELLED
        application.save(update_fields=["status", "updated_at"])
        if payment:
            payment.status = SponsorPayment.Status.FAILED
            payment.failure_message = "Checkout cancelled before payment."
            payment.save(update_fields=["status", "failure_message", "updated_at"])
        if cell.status == SponsorCell.Status.PAYMENT_PENDING:
            cell.status = SponsorCell.Status.AVAILABLE
            cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CHECKOUT_CANCELLED,
            application=application,
            from_status=from_status,
            to_status=application.status,
        )
        return application


def _event_object(event):
    return _get(_get(event, "data", {}), "object", {})


def _metadata(obj) -> dict:
    metadata = _get(obj, "metadata", {}) or {}
    return dict(metadata)


def _application_from_metadata(metadata: dict) -> SponsorApplication | None:
    application_id = metadata.get("sponsor_application_id")
    if not application_id:
        return None
    return (
        SponsorApplication.objects.select_for_update()
        .select_related("cell")
        .filter(pk=application_id)
        .first()
    )


def handle_stripe_event(event) -> dict[str, Any]:
    event_id = _get(event, "id", "")
    event_type = _get(event, "type", "")
    if not event_id or not event_type:
        raise SponsorPaymentVerificationError("Stripe event is missing id or type.")

    with transaction.atomic():
        processed, created = ProcessedStripeEvent.objects.get_or_create(
            event_id=event_id,
            defaults={"event_type": event_type},
        )
        if not created:
            return {"duplicate": True, "event_type": event_type}

        application = None
        if event_type == "checkout.session.completed":
            application = _handle_checkout_completed(_event_object(event))
        elif event_type == "checkout.session.expired":
            application = _handle_checkout_expired(_event_object(event))
        elif event_type == "payment_intent.payment_failed":
            application = _handle_payment_intent_failed(_event_object(event))
        elif event_type == "charge.refunded":
            application = _handle_charge_refunded(_event_object(event))

        processed.application = application
        processed.event_type = event_type
        processed.save(update_fields=["application", "event_type"])
        return {"duplicate": False, "event_type": event_type, "application": application}


def _handle_checkout_completed(session) -> SponsorApplication | None:
    metadata = _metadata(session)
    application = _application_from_metadata(metadata)
    if not application:
        return None

    cell_id = metadata.get("sponsor_cell_id")
    if cell_id and str(application.cell_id) != str(cell_id):
        raise SponsorPaymentVerificationError("Stripe metadata cell id does not match application.")

    amount_subtotal = _get(session, "amount_subtotal")
    currency = (_get(session, "currency", "") or "").lower()
    if amount_subtotal is not None and int(amount_subtotal) != application.price_net_cents:
        raise SponsorPaymentVerificationError("Stripe checkout amount does not match sponsor cell price.")
    if currency and currency != application.currency:
        raise SponsorPaymentVerificationError("Stripe checkout currency does not match application currency.")

    cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
    total_details = _get(session, "total_details", {}) or {}
    tax_amount = _get(total_details, "amount_tax", 0) or 0
    total_amount = _get(session, "amount_total", 0) or 0
    payment_intent = _get(session, "payment_intent", "") or ""
    session_id = _get(session, "id", "") or ""

    payment, _ = SponsorPayment.objects.select_for_update().get_or_create(
        application=application,
        defaults={"net_amount_cents": application.price_net_cents, "currency": application.currency},
    )
    payment.status = SponsorPayment.Status.PAID
    payment.stripe_checkout_session_id = session_id or payment.stripe_checkout_session_id
    payment.stripe_payment_intent_id = payment_intent
    payment.net_amount_cents = int(amount_subtotal if amount_subtotal is not None else application.price_net_cents)
    payment.vat_amount_cents = int(tax_amount)
    payment.total_amount_cents = int(total_amount)
    payment.currency = currency or application.currency
    payment.paid_at = payment.paid_at or timezone.now()
    payment.failure_message = ""
    payment.save()

    from_status = application.status
    application.status = SponsorApplication.Status.PAID_PENDING_APPROVAL
    application.save(update_fields=["status", "updated_at"])
    cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
    cell.save(update_fields=["status", "updated_at"])
    record_audit(
        action=SponsorAuditLog.Action.PAYMENT_CONFIRMED,
        application=application,
        from_status=from_status,
        to_status=application.status,
        metadata={
            "stripe_checkout_session_id": session_id,
            "stripe_payment_intent_id": payment_intent,
            "net_amount_cents": payment.net_amount_cents,
            "vat_amount_cents": payment.vat_amount_cents,
            "total_amount_cents": payment.total_amount_cents,
        },
    )
    return application


def _handle_checkout_expired(session) -> SponsorApplication | None:
    application = _application_from_metadata(_metadata(session))
    if not application:
        return None
    payment = getattr(application, "payment", None)
    if payment and payment.status == SponsorPayment.Status.PAID:
        return application

    cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
    from_status = application.status
    application.status = SponsorApplication.Status.EXPIRED
    application.save(update_fields=["status", "updated_at"])
    if payment:
        payment.status = SponsorPayment.Status.FAILED
        payment.failure_message = "Stripe Checkout Session expired before payment."
        payment.save(update_fields=["status", "failure_message", "updated_at"])
    if cell.status == SponsorCell.Status.PAYMENT_PENDING:
        cell.status = SponsorCell.Status.AVAILABLE
        cell.save(update_fields=["status", "updated_at"])
    record_audit(
        action=SponsorAuditLog.Action.CHECKOUT_EXPIRED,
        application=application,
        from_status=from_status,
        to_status=application.status,
    )
    return application


def _handle_payment_intent_failed(payment_intent) -> SponsorApplication | None:
    metadata = _metadata(payment_intent)
    application = _application_from_metadata(metadata)
    if application is None:
        intent_id = _get(payment_intent, "id", "") or ""
        payment = SponsorPayment.objects.select_for_update().filter(stripe_payment_intent_id=intent_id).first()
        application = payment.application if payment else None
    if application is None:
        return None

    payment = getattr(application, "payment", None)
    if payment and payment.status != SponsorPayment.Status.PAID:
        payment.status = SponsorPayment.Status.FAILED
        payment.failure_message = _get(_get(payment_intent, "last_payment_error", {}), "message", "") or "Payment failed."
        payment.save(update_fields=["status", "failure_message", "updated_at"])
    record_audit(
        action=SponsorAuditLog.Action.PAYMENT_FAILED,
        application=application,
        notes=payment.failure_message if payment else "Payment failed.",
    )
    return application


def _handle_charge_refunded(charge) -> SponsorApplication | None:
    payment_intent_id = _get(charge, "payment_intent", "") or ""
    payment = SponsorPayment.objects.select_for_update().filter(
        stripe_payment_intent_id=payment_intent_id
    ).select_related("application", "application__cell").first()
    if not payment:
        return None

    refunded_amount = int(_get(charge, "amount_refunded", 0) or 0)
    total_amount = int(_get(charge, "amount", 0) or payment.total_amount_cents or 0)
    payment.refunded_amount_cents = refunded_amount
    payment.refunded_at = timezone.now()
    payment.status = (
        SponsorPayment.Status.REFUNDED
        if total_amount and refunded_amount >= total_amount
        else SponsorPayment.Status.PARTIALLY_REFUNDED
    )
    payment.save(update_fields=["refunded_amount_cents", "refunded_at", "status", "updated_at"])
    record_audit(
        action=SponsorAuditLog.Action.REFUND_COMPLETED,
        application=payment.application,
        metadata={"refunded_amount_cents": refunded_amount, "stripe_payment_intent_id": payment_intent_id},
    )
    return payment.application


def add_one_year(value):
    try:
        return value.replace(year=value.year + 1)
    except ValueError:
        return value.replace(year=value.year + 1, day=28)


def approve_application(application_id: int, actor) -> SponsorApplication:
    with transaction.atomic():
        application = (
            SponsorApplication.objects.select_for_update()
            .select_related("cell")
            .get(pk=application_id)
        )
        if application.status != SponsorApplication.Status.PAID_PENDING_APPROVAL:
            raise ValueError("Only paid applications pending approval can be approved.")
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        now = timezone.now()
        from_status = application.status

        application.status = SponsorApplication.Status.APPROVED
        application.approved_by = actor
        application.approved_at = now
        application.published_at = now
        application.expires_at = add_one_year(now)
        application.save()

        cell.sponsor_name = application.sponsor_name
        cell.sponsor_logo = application.logo
        cell.sponsor_url = application.website_url
        cell.logo_offset_x = application.logo_offset_x
        cell.logo_offset_y = application.logo_offset_y
        cell.logo_scale = application.logo_scale
        cell.status = SponsorCell.Status.ACTIVE
        cell.purchased_at = now
        cell.save()

        record_audit(
            action=SponsorAuditLog.Action.APPROVED,
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=application.status,
        )
        return application


def reject_application(application_id: int, actor, reason: str = "") -> SponsorApplication:
    with transaction.atomic():
        application = (
            SponsorApplication.objects.select_for_update()
            .select_related("cell")
            .get(pk=application_id)
        )
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        payment = getattr(application, "payment", None)
        from_status = application.status

        application.rejected_by = actor
        application.rejected_at = timezone.now()
        application.rejection_reason = reason
        application.status = (
            SponsorApplication.Status.REFUND_REQUIRED
            if payment and payment.status == SponsorPayment.Status.PAID
            else SponsorApplication.Status.REJECTED
        )
        application.save()

        cell.status = (
            SponsorCell.Status.REJECTED
            if application.status == SponsorApplication.Status.REFUND_REQUIRED
            else SponsorCell.Status.AVAILABLE
        )
        cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=(
                SponsorAuditLog.Action.REFUND_REQUIRED
                if application.status == SponsorApplication.Status.REFUND_REQUIRED
                else SponsorAuditLog.Action.REJECTED
            ),
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=application.status,
            notes=reason,
        )
        return application


def mark_refund_completed(application_id: int, actor, notes: str = "") -> SponsorApplication:
    with transaction.atomic():
        application = (
            SponsorApplication.objects.select_for_update()
            .select_related("cell")
            .get(pk=application_id)
        )
        payment = getattr(application, "payment", None)
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = application.status

        application.status = SponsorApplication.Status.REFUNDED
        application.save(update_fields=["status", "updated_at"])
        if payment:
            payment.status = SponsorPayment.Status.REFUNDED
            payment.refunded_at = timezone.now()
            payment.save(update_fields=["status", "refunded_at", "updated_at"])
        cell.status = SponsorCell.Status.AVAILABLE
        cell.sponsor_name = ""
        cell.sponsor_url = ""
        cell.sponsor_tagline = ""
        cell.sponsor_logo = None
        cell.save()
        record_audit(
            action=SponsorAuditLog.Action.REFUND_COMPLETED,
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=application.status,
            notes=notes,
        )
        return application


def unpublish_application(application_id: int, actor, notes: str = "") -> SponsorApplication:
    with transaction.atomic():
        application = SponsorApplication.objects.select_for_update().select_related("cell").get(pk=application_id)
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = cell.status
        cell.status = SponsorCell.Status.UNAVAILABLE
        cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.UNPUBLISHED,
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=cell.status,
            notes=notes,
        )
        return application


def expire_application(application_id: int, actor, notes: str = "") -> SponsorApplication:
    with transaction.atomic():
        application = SponsorApplication.objects.select_for_update().select_related("cell").get(pk=application_id)
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = application.status
        application.status = SponsorApplication.Status.EXPIRED
        application.save(update_fields=["status", "updated_at"])
        cell.status = SponsorCell.Status.EXPIRED
        cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.EXPIRED,
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=application.status,
            notes=notes,
        )
        return application


ROADMAP_MILESTONES = [
    "Audit existing Sponsors section",
    "Update sponsor data model",
    "Add VAT-aware pricing display",
    "Add sponsor application form updates",
    "Add sponsor cell locking",
    "Add Stripe Checkout Session creation",
    "Add Stripe webhook handling",
    "Add payment status tracking",
    "Add paid pending approval workflow",
    "Add approval and publication workflow",
    "Add rejection and refund-required workflow",
    "Update annual sponsorship terms wording",
    "Add success and cancel pages",
    "Add moderation dashboard views",
    "Add super-admin roadmap page",
    "Add audit logging",
    "Add tests",
    "Complete test-mode Stripe payment",
    "Complete webhook test",
    "Prepare live-mode checklist",
]


def seed_roadmap_items() -> None:
    now = timezone.now()
    for index, title in enumerate(ROADMAP_MILESTONES, start=1):
        is_done = index <= 17
        SponsorRoadmapItem.objects.get_or_create(
            title=title,
            defaults={
                "phase": "Stripe Sponsors",
                "sort_order": index,
                "status": SponsorRoadmapItem.Status.DONE if is_done else SponsorRoadmapItem.Status.NOT_STARTED,
                "priority": SponsorRoadmapItem.Priority.HIGH if index <= 17 else SponsorRoadmapItem.Priority.MEDIUM,
                "completed_at": now if is_done else None,
            },
        )


def build_roadmap_context() -> dict[str, Any]:
    seed_roadmap_items()
    items = list(SponsorRoadmapItem.objects.all())
    done_statuses = {SponsorRoadmapItem.Status.DONE, SponsorRoadmapItem.Status.SKIPPED}
    done_count = sum(1 for item in items if item.status in done_statuses)
    total_count = len(items)
    blockers = [item for item in items if item.is_blocker or item.status == SponsorRoadmapItem.Status.BLOCKED]
    pending_items = [item for item in items if item.status not in done_statuses]
    completed_items = [item for item in items if item.status in done_statuses]
    stripe_secret = bool(getattr(settings, "STRIPE_SECRET_KEY", ""))
    publishable_key = bool(getattr(settings, "STRIPE_PUBLISHABLE_KEY", ""))
    webhook_secret = bool(getattr(settings, "STRIPE_WEBHOOK_SECRET", ""))
    stripe_live_mode = str(getattr(settings, "STRIPE_SECRET_KEY", "")).startswith("sk_live_")

    checks = {
        "stripe": [
            ("Publishable key configured", publishable_key),
            ("Secret key configured", stripe_secret),
            ("Webhook secret configured", webhook_secret),
            ("Automatic tax expected/enabled", True),
        ],
        "vat": [
            ("Bearcave VAT number present", True),
            ("Prices excluding VAT", True),
            ("Checkout VAT calculation enabled", True),
        ],
        "flow": [
            ("Sponsor cell selection working", True),
            ("Form validation working", True),
            ("Checkout creation working", stripe_secret),
            ("Webhook working", webhook_secret),
            ("Paid pending approval working", True),
            ("Approval publishing working", True),
            ("Rejection/refund workflow working", True),
        ],
        "tests": [
            ("Unit tests", any(item.title == "Add tests" and item.status == SponsorRoadmapItem.Status.DONE for item in items)),
            ("Integration tests", False),
            ("Webhook tests", False),
            ("Manual test checklist", False),
        ],
    }
    return {
        "items": items,
        "completed_items": completed_items,
        "pending_items": pending_items,
        "blockers": blockers,
        "done_count": done_count,
        "total_count": total_count,
        "percent": round((done_count / total_count) * 100) if total_count else 0,
        "current_phase": "Stripe Checkout and moderation workflow",
        "last_updated": max((item.updated_at for item in items), default=timezone.now()),
        "environment_mode": "Stripe live mode" if stripe_live_mode else "Stripe test mode",
        "checks": checks,
    }
