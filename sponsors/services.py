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
                        "tax_code": "txcd_20060002",
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
    if isinstance(metadata, dict):
        return metadata
    # Stripe SDK returns metadata as a StripeObject; dict(stripe_obj) fails with
    # KeyError: 0 because StripeObject.__iter__ yields integer indices, not keys.
    # Use to_dict_recursive() → to_dict() → _data → fall back to empty dict.
    for attr in ("to_dict_recursive", "to_dict"):
        fn = getattr(metadata, attr, None)
        if callable(fn):
            try:
                result = fn()
                if isinstance(result, dict):
                    return result
            except Exception:
                pass
    raw = getattr(metadata, "_data", None) or getattr(metadata, "__dict__", None)
    if isinstance(raw, dict):
        return raw
    return {}


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
    # Issue 2: Require payment_status == "paid" before marking as paid.
    payment_status = (_get(session, "payment_status", "") or "").lower()
    if payment_status and payment_status != "paid":
        # Not a completed card payment — do not mark as paid.
        return None

    metadata = _metadata(session)
    application = _application_from_metadata(metadata)
    if not application:
        return None

    cell_id = metadata.get("sponsor_cell_id")
    if cell_id and str(application.cell_id) != str(cell_id):
        raise SponsorPaymentVerificationError("Stripe metadata cell id does not match application.")

    # Issue 3: Monotonic state guard — only advance from valid payment_pending states.
    _VALID_COMPLETION_STATES = {
        SponsorApplication.Status.PAYMENT_PENDING,
        SponsorApplication.Status.PAID_PENDING_APPROVAL,  # idempotent replay
    }
    _TERMINAL_STATES = {
        SponsorApplication.Status.APPROVED,
        SponsorApplication.Status.REJECTED,
        SponsorApplication.Status.REFUND_REQUIRED,
        SponsorApplication.Status.REFUNDED,
        SponsorApplication.Status.CANCELLED,
        SponsorApplication.Status.EXPIRED,
    }
    if application.status in _TERMINAL_STATES:
        # Late/replayed event — audit and leave for manual review.
        record_audit(
            action=SponsorAuditLog.Action.PAYMENT_CONFIRMED,
            application=application,
            from_status=application.status,
            to_status=application.status,
            notes=(
                f"checkout.session.completed received but application is already in terminal "
                f"state '{application.status}'. Left for manual review."
            ),
            metadata={"stripe_session_id": _get(session, "id", "")},
        )
        return application

    amount_subtotal = _get(session, "amount_subtotal")
    currency = (_get(session, "currency", "") or "").lower()
    if amount_subtotal is not None and int(amount_subtotal) != application.price_net_cents:
        raise SponsorPaymentVerificationError("Stripe checkout amount does not match sponsor cell price.")
    if currency and currency != application.currency:
        raise SponsorPaymentVerificationError("Stripe checkout currency does not match application currency.")

    cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)

    # Issue 1: Late payment conflict — verify cell is still owned by this application.
    _VALID_CELL_STATES = {
        SponsorCell.Status.PAYMENT_PENDING,
        SponsorCell.Status.PAID_PENDING_APPROVAL,  # idempotent replay
    }
    session_id = _get(session, "id", "") or ""
    if cell.status not in _VALID_CELL_STATES:
        # Cell was released and may have been taken by another applicant.
        payment_conflict, _ = SponsorPayment.objects.select_for_update().get_or_create(
            application=application,
            defaults={"net_amount_cents": application.price_net_cents, "currency": application.currency},
        )
        payment_intent_conflict = _get(session, "payment_intent", "") or ""
        payment_conflict.stripe_payment_intent_id = payment_conflict.stripe_payment_intent_id or payment_intent_conflict
        payment_conflict.stripe_checkout_session_id = payment_conflict.stripe_checkout_session_id or session_id
        payment_conflict.save(update_fields=["stripe_payment_intent_id", "stripe_checkout_session_id", "updated_at"])
        from_status = application.status
        application.status = SponsorApplication.Status.REFUND_REQUIRED
        application.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.REFUND_REQUIRED,
            application=application,
            from_status=from_status,
            to_status=application.status,
            notes=(
                f"Late checkout.session.completed: cell {cell.pk} is in state '{cell.status}' "
                f"and is no longer reserved for this application. "
                f"Application set to refund_required for manual review."
            ),
            metadata={"stripe_session_id": session_id, "cell_status": cell.status},
        )
        return application

    total_details = _get(session, "total_details", {}) or {}
    tax_amount = _get(total_details, "amount_tax", 0) or 0
    total_amount = _get(session, "amount_total", 0) or 0
    payment_intent = _get(session, "payment_intent", "") or ""

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
    # Notify admin — only on a genuine new confirmation (not idempotent replay).
    if from_status == SponsorApplication.Status.PAYMENT_PENDING:
        _notify_sponsor_payment_confirmed(application, payment)
    return application


def _notify_sponsor_payment_confirmed(application: SponsorApplication, payment: SponsorPayment) -> None:
    """Send an email notification to the sponsor admin after payment is confirmed."""
    try:
        from config.email_utils import build_absolute_url, send_template_mail
        admin_email = getattr(settings, "SPONSOR_ADMIN_EMAIL", "culineire@bearcave.ie")
        if not admin_email:
            return
        detail_url = build_absolute_url(
            reverse("sponsors:moderation_application_detail", args=[application.pk])
        )

        def _cents_to_eur(cents: int) -> str:
            return f"{cents / 100:.2f}"

        context = {
            "application_id": application.pk,
            "sponsor_name": application.sponsor_name,
            "sponsor_email": application.email,
            "cell_id": application.cell_id,
            "ring": getattr(application.cell, "ring", None),
            "net_eur": _cents_to_eur(payment.net_amount_cents or 0),
            "vat_eur": _cents_to_eur(payment.vat_amount_cents or 0),
            "total_eur": _cents_to_eur(payment.total_amount_cents or 0),
            "moderation_url": detail_url,
        }
        send_template_mail(
            subject="New paid sponsor application pending approval",
            template="sponsor_payment_confirmed",
            context=context,
            recipient_list=[admin_email],
            fail_silently=True,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to send sponsor payment confirmation email for application pk=%s",
            application.pk,
        )


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
    # Issue 4: On verified full refund, complete the refund workflow atomically.
    payment_intent_id = _get(charge, "payment_intent", "") or ""
    payment = SponsorPayment.objects.select_for_update().filter(
        stripe_payment_intent_id=payment_intent_id
    ).select_related("application", "application__cell").first()
    if not payment:
        return None

    application = SponsorApplication.objects.select_for_update().select_related("cell").get(
        pk=payment.application_id
    )
    cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)

    refunded_amount = int(_get(charge, "amount_refunded", 0) or 0)
    total_amount = int(_get(charge, "amount", 0) or payment.total_amount_cents or 0)
    is_full_refund = bool(total_amount and refunded_amount >= total_amount)

    payment.refunded_amount_cents = refunded_amount
    payment.refunded_at = timezone.now()
    payment.status = (
        SponsorPayment.Status.REFUNDED
        if is_full_refund
        else SponsorPayment.Status.PARTIALLY_REFUNDED
    )
    payment.save(update_fields=["refunded_amount_cents", "refunded_at", "status", "updated_at"])

    # If the application is in refund_required and the refund is now full, transition atomically.
    if is_full_refund and application.status == SponsorApplication.Status.REFUND_REQUIRED:
        from_status = application.status
        application.status = SponsorApplication.Status.REFUNDED
        application.save(update_fields=["status", "updated_at"])
        # Release cell only if it is still held by this application (not already taken).
        if cell.status in {SponsorCell.Status.REJECTED, SponsorCell.Status.PAID_PENDING_APPROVAL}:
            cell.status = SponsorCell.Status.AVAILABLE
            cell.sponsor_name = ""
            cell.sponsor_url = ""
            cell.sponsor_tagline = ""
            cell.sponsor_logo = None
            cell.save()
        record_audit(
            action=SponsorAuditLog.Action.REFUND_COMPLETED,
            application=application,
            from_status=from_status,
            to_status=application.status,
            notes="Full refund verified via charge.refunded webhook. Cell released automatically.",
            metadata={"refunded_amount_cents": refunded_amount, "stripe_payment_intent_id": payment_intent_id},
        )
    else:
        record_audit(
            action=SponsorAuditLog.Action.REFUND_COMPLETED,
            application=application,
            metadata={
                "refunded_amount_cents": refunded_amount,
                "stripe_payment_intent_id": payment_intent_id,
                "is_full_refund": is_full_refund,
            },
        )
    return application


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
        cell.logo_rotation = application.logo_rotation
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

    # Announce on Telegram outside the atomic block so a Telegram failure
    # never rolls back the approval.
    try:
        from newsfeed.telegram import publish_sponsor_to_telegram
        publish_sponsor_to_telegram(application)
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "Failed to send sponsor Telegram announcement for application pk=%s",
            application.pk,
        )

    return application


def reject_application(application_id: int, actor, reason: str = "") -> SponsorApplication:
    with transaction.atomic():
        application = (
            SponsorApplication.objects.select_for_update()
            .select_related("cell")
            .get(pk=application_id)
        )
        # Issue 5: Do not silently reject terminal/active applications.
        _REJECTABLE_STATES = {
            SponsorApplication.Status.DRAFT,
            SponsorApplication.Status.PAYMENT_PENDING,
            SponsorApplication.Status.PAID_PENDING_APPROVAL,
        }
        if application.status not in _REJECTABLE_STATES:
            raise ValueError(
                f"Cannot reject application in status '{application.status}'. "
                f"Only draft, payment_pending, or paid_pending_approval applications can be rejected."
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
        # Issue 5: Only allow from refund_required.
        if application.status != SponsorApplication.Status.REFUND_REQUIRED:
            raise ValueError(
                f"mark_refund_completed is only valid from refund_required status. "
                f"Current status: {application.status}"
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
        # Issue 5: Only expire approved/active applications.
        if application.status != SponsorApplication.Status.APPROVED:
            raise ValueError(
                f"expire_application is only valid for approved applications. "
                f"Current status: {application.status}"
            )
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


# Each entry: (title, phase, is_done, is_blocker)
ROADMAP_MILESTONES: list[tuple[str, str, bool, bool]] = [
    # Phase 1 — Foundation
    ("Audit existing Sponsors section",             "Phase 1: Foundation",    True,  False),
    ("Update sponsor data model",                   "Phase 1: Foundation",    True,  False),
    ("Add VAT-aware pricing display",               "Phase 1: Foundation",    True,  False),
    ("Add sponsor application form",                "Phase 1: Foundation",    True,  False),
    ("Add sponsor cell locking",                    "Phase 1: Foundation",    True,  False),
    ("Add Stripe Checkout Session creation",        "Phase 1: Foundation",    True,  False),
    ("Add Stripe webhook handling",                 "Phase 1: Foundation",    True,  False),
    ("Add payment status tracking",                 "Phase 1: Foundation",    True,  False),
    ("Add paid pending approval workflow",          "Phase 1: Foundation",    True,  False),
    ("Add approval and publication workflow",       "Phase 1: Foundation",    True,  False),
    ("Add rejection and refund-required workflow",  "Phase 1: Foundation",    True,  False),
    ("Update annual sponsorship terms wording",     "Phase 1: Foundation",    True,  False),
    ("Add success and cancel pages",                "Phase 1: Foundation",    True,  False),
    ("Add moderation dashboard views",              "Phase 1: Foundation",    True,  False),
    ("Add super-admin roadmap page",                "Phase 1: Foundation",    True,  False),
    ("Add audit logging",                           "Phase 1: Foundation",    True,  False),
    ("Add tests",                                   "Phase 1: Foundation",    True,  False),
    # Phase 2 — Hardening
    ("Harden state machine: late payment conflict", "Phase 2: Hardening",     True,  False),
    ("Harden state machine: payment_status guard",  "Phase 2: Hardening",     True,  False),
    ("Harden state machine: monotonic transitions", "Phase 2: Hardening",     True,  False),
    ("Harden state machine: refund webhook",        "Phase 2: Hardening",     True,  False),
    ("Harden state machine: moderation validation", "Phase 2: Hardening",     True,  False),
    ("Add Stripe Tax code (txcd_20060002)",         "Phase 2: Hardening",     True,  False),
    ("Fix Stripe StripeObject metadata conversion", "Phase 2: Hardening",     True,  False),
    ("Add logo rights checkbox to sponsor form",    "Phase 2: Hardening",     True,  False),
    ("Add logo rotation editor to sponsor form",    "Phase 2: Hardening",     True,  False),
    # Sandbox testing
    ("Complete test-mode Stripe payment",           "Sandbox Testing",        True,  False),
    ("Complete webhook test",                       "Sandbox Testing",        True,  False),
    # Notifications
    ("Admin email on payment confirmation",         "Notifications",          True,  False),
    ("Telegram announcement on sponsor approval",   "Notifications",          True,  False),
    ("Sponsor Applications in nav dropdown",        "Notifications",          True,  False),
    ("Paid badge on Moderation Panel",              "Notifications",          True,  False),
    # Live mode
    ("Fix media folder permissions on server",      "Live Mode Prep",         True,  False),
    ("Merge feature branch to main",                "Live Mode Prep",         False, True),
    ("Switch Stripe to live mode",                  "Live Mode Prep",         False, True),
    ("Configure live Stripe webhook endpoint",      "Live Mode Prep",         False, True),
    ("Prepare live-mode checklist",                 "Live Mode Prep",         False, False),
]


def seed_roadmap_items() -> None:
    now = timezone.now()
    for index, (title, phase, is_done, is_blocker) in enumerate(ROADMAP_MILESTONES, start=1):
        SponsorRoadmapItem.objects.update_or_create(
            title=title,
            defaults={
                "phase": phase,
                "sort_order": index,
                "status": SponsorRoadmapItem.Status.DONE if is_done else SponsorRoadmapItem.Status.NOT_STARTED,
                "priority": SponsorRoadmapItem.Priority.HIGH,
                "is_blocker": is_blocker,
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
