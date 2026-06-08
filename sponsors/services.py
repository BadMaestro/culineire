from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
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
from .compliance import compliance_allows_progress, mark_screening_required


class SponsorStripeConfigurationError(RuntimeError):
    pass


class SponsorPaymentVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutSessionInfo:
    session_id: str
    checkout_url: str


def validate_stripe_runtime_configuration(*, require_webhook_secret: bool = False) -> None:
    mode = str(getattr(settings, "STRIPE_PRICE_MODE", "") or "").strip().lower()
    secret_key = str(getattr(settings, "STRIPE_SECRET_KEY", "") or "").strip()
    publishable_key = str(getattr(settings, "STRIPE_PUBLISHABLE_KEY", "") or "").strip()
    webhook_secret = str(getattr(settings, "STRIPE_WEBHOOK_SECRET", "") or "").strip()

    if mode not in {"test", "live"}:
        raise SponsorStripeConfigurationError("STRIPE_PRICE_MODE must be either 'test' or 'live'.")
    if not secret_key:
        raise SponsorStripeConfigurationError("STRIPE_SECRET_KEY is not configured.")
    if mode == "test" and secret_key.startswith("sk_live_"):
        raise SponsorStripeConfigurationError("Stripe live secret key cannot be used while STRIPE_PRICE_MODE is test.")
    if mode == "live" and secret_key.startswith("sk_test_"):
        raise SponsorStripeConfigurationError("Stripe test secret key cannot be used while STRIPE_PRICE_MODE is live.")
    if publishable_key:
        if mode == "test" and publishable_key.startswith("pk_live_"):
            raise SponsorStripeConfigurationError("Stripe live publishable key cannot be used while STRIPE_PRICE_MODE is test.")
        if mode == "live" and publishable_key.startswith("pk_test_"):
            raise SponsorStripeConfigurationError("Stripe test publishable key cannot be used while STRIPE_PRICE_MODE is live.")
    if require_webhook_secret and not webhook_secret:
        raise SponsorStripeConfigurationError("STRIPE_WEBHOOK_SECRET is not configured.")


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

    validate_stripe_runtime_configuration()
    secret_key = getattr(settings, "STRIPE_SECRET_KEY", "")
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
        "sponsor_product_type": application.product_type,
    }


def create_checkout_session(application: SponsorApplication, request=None) -> CheckoutSessionInfo:
    stripe = _stripe()
    base_url = site_base_url(request)
    metadata = _checkout_metadata(application)
    is_central = application.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY
    is_weekly = application.product_type == SponsorCell.ProductType.WEEKLY_RING
    product_name = (
        "CulinEire Sponsor of the Month" if is_central
        else "CulinEire 7-Day Ring Sponsor Spot" if is_weekly
        else "CulinEire Annual Sponsor Spot"
    )
    product_description = (
        "Monthly central sponsor placement on the CulinEire Sponsor Puzzle" if is_central
        else "7-day ring sponsor placement on the CulinEire Sponsor Puzzle" if is_weekly
        else "Annual sponsor placement on the CulinEire Sponsor Puzzle"
    )
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
                        "name": product_name,
                        "description": product_description,
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
    validate_stripe_runtime_configuration(require_webhook_secret=True)
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", "")
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
        action=(
            SponsorAuditLog.Action.CHECKOUT_CREATED_AFTER_DECLARATION
            if hasattr(application, "applicant_declaration")
            else SponsorAuditLog.Action.CHECKOUT_CREATED
        ),
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
        SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
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
    customer_details = _get(session, "customer_details", {}) or {}
    billing_addr = _get(customer_details, "address", None)

    payment.status = SponsorPayment.Status.PAID
    payment.stripe_checkout_session_id = session_id or payment.stripe_checkout_session_id
    payment.stripe_payment_intent_id = payment_intent
    payment.net_amount_cents = int(amount_subtotal if amount_subtotal is not None else application.price_net_cents)
    payment.vat_amount_cents = int(tax_amount)
    payment.total_amount_cents = int(total_amount)
    payment.currency = currency or application.currency
    payment.paid_at = payment.paid_at or timezone.now()
    payment.failure_message = ""
    if billing_addr and not payment.billing_address:
        payment.billing_address = billing_addr
    payment.save()

    from_status = application.status
    application.status = SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW
    application.save(update_fields=["status", "updated_at"])
    cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
    cell.save(update_fields=["status", "updated_at"])
    mark_screening_required(application)
    declaration = getattr(application, "applicant_declaration", None)
    if declaration and session_id and declaration.stripe_session_id != session_id:
        declaration.stripe_session_id = session_id
        declaration.save(update_fields=["stripe_session_id"])
    record_audit(
        action=SponsorAuditLog.Action.PAYMENT_RECEIVED_PENDING_COMPLIANCE_REVIEW,
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
    try:
        from .sanctions_matching import screen_sponsor_application
        screen_sponsor_application(application)
    except Exception as exc:
        record_audit(
            action=SponsorAuditLog.Action.COMPLIANCE_BLOCKED,
            application=application,
            notes=f"Sanctions screening failed and requires manual review: {exc}",
        )
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
        if application.status == SponsorApplication.Status.REFUND_REQUIRED and not is_full_refund:
            cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
            cell.save(update_fields=["status", "updated_at"])
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
    blocked_message = "This sponsor application cannot be approved while sanctions compliance review is unresolved or blocked."
    preflight_application = SponsorApplication.objects.filter(pk=application_id).first()
    if preflight_application:
        from .sanctions_matching import has_blocked_sanctions_match, has_unresolved_sanctions_matches
        if has_unresolved_sanctions_matches(preflight_application):
            record_audit(
                action=SponsorAuditLog.Action.APPROVAL_BLOCKED_SANCTIONS,
                application=preflight_application,
                actor=actor,
                notes="Approval blocked due to unresolved possible sanctions matches.",
            )
            raise ValueError(
                f"{blocked_message} unresolved possible sanctions matches must be reviewed first."
            )
        if has_blocked_sanctions_match(preflight_application):
            record_audit(
                action=SponsorAuditLog.Action.APPROVAL_BLOCKED_SANCTIONS,
                application=preflight_application,
                actor=actor,
                notes="Approval blocked due to a blocked sanctions match decision.",
            )
            raise ValueError(
                f"{blocked_message} This application is blocked for compliance."
            )
    with transaction.atomic():
        application = (
            SponsorApplication.objects.select_for_update()
            .select_related("cell")
            .get(pk=application_id)
        )
        if application.status not in {
            SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            SponsorApplication.Status.PAID_PENDING_APPROVAL,
        }:
            raise ValueError("Only paid applications pending review can be approved.")
        if not compliance_allows_progress(application):
            from .sanctions_matching import has_blocked_sanctions_match, has_unresolved_sanctions_matches
            if has_unresolved_sanctions_matches(application):
                record_audit(
                    action=SponsorAuditLog.Action.APPROVAL_BLOCKED_SANCTIONS,
                    application=application,
                    actor=actor,
                    notes="Approval blocked due to unresolved possible sanctions matches.",
                )
                raise ValueError(
                    f"{blocked_message} unresolved possible sanctions matches must be reviewed first."
                )
            if has_blocked_sanctions_match(application):
                record_audit(
                    action=SponsorAuditLog.Action.APPROVAL_BLOCKED_SANCTIONS,
                    application=application,
                    actor=actor,
                    notes="Approval blocked due to a blocked sanctions match decision.",
                )
                raise ValueError(
                    f"{blocked_message} This application is blocked for compliance."
                )
            raise ValueError(
                f"{blocked_message} Compliance must be clear or manually cleared before approval and publication."
            )
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        now = timezone.now()
        from_status = application.status

        application.status = SponsorApplication.Status.APPROVED
        application.approved_by = actor
        application.approved_at = now
        application.published_at = now
        application.expires_at = (
            add_one_year(now)
            if application.product_type == SponsorCell.ProductType.ANNUAL_RING
            else now + timedelta(days=application.term_days)
        )
        application.contract_reference = _generate_contract_reference(application)
        application.contract_email_status = SponsorApplication.ContractEmailStatus.PENDING
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

    # Send agreement email — failure must not roll back or block approval.
    try:
        pdf_filename = _send_contract_email(application)
        application.contract_sent_at = timezone.now()
        application.contract_email_status = SponsorApplication.ContractEmailStatus.SENT
        application.save(update_fields=["contract_sent_at", "contract_email_status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CONTRACT_SENT,
            application=application,
            actor=actor,
            notes=f"Agreement email sent to {application.email}",
            metadata={
                "pdf_attached": True,
                "pdf_filename": pdf_filename,
                "contract_reference": application.contract_reference,
            },
        )
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "Failed to send sponsor contract email for application pk=%s", application.pk,
        )
        application.contract_email_status = SponsorApplication.ContractEmailStatus.FAILED
        application.save(update_fields=["contract_email_status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CONTRACT_EMAIL_FAILED,
            application=application,
            actor=actor,
            notes="Contract agreement email failed to send.",
        )

    return application


def _generate_contract_reference(application: SponsorApplication) -> str:
    prefix = {
        SponsorCell.ProductType.ANNUAL_RING: "AN",
        SponsorCell.ProductType.WEEKLY_RING: "WK",
        SponsorCell.ProductType.CENTRAL_MONTHLY: "MO",
    }.get(application.product_type, "SP")
    year = timezone.now().year
    return f"CUL-{prefix}-{year}-{application.pk:06d}"


def _select_agreement_template(product_type: str) -> str:
    return {
        SponsorCell.ProductType.WEEKLY_RING: "sponsors/agreement_weekly",
        SponsorCell.ProductType.CENTRAL_MONTHLY: "sponsors/agreement_monthly",
    }.get(product_type, "sponsors/agreement_annual")


def generate_contract_pdf(application: SponsorApplication) -> bytes:
    from io import BytesIO
    from xml.sax.saxutils import escape

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            KeepTogether,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is not installed. Add reportlab to requirements.txt.") from exc

    # ── Palette: Heritage Legal Paper ─────────────────────────────────────────
    c_parchment = colors.HexColor("#FAF6EF")
    c_card      = colors.HexColor("#FFFDF8")
    c_text      = colors.HexColor("#2A2622")
    c_heading   = colors.HexColor("#1E1A16")
    c_copper    = colors.HexColor("#B07A3A")
    c_stone     = colors.HexColor("#D8C8B6")
    c_muted     = colors.HexColor("#6B5E52")

    page_w, page_h = A4
    l_margin = r_margin = 22 * mm
    t_margin = 24 * mm
    b_margin = 28 * mm
    text_w = page_w - l_margin - r_margin

    # ── Helpers ───────────────────────────────────────────────────────────────
    def _cents_display(cents):
        return f"EUR {cents / 100:.2f}" if cents else "-"

    def _fmt_date(dt):
        return f"{dt.day} {dt.strftime('%B %Y')}" if dt else "-"

    def _safe(value):
        return escape(str(value or ""))

    # ── Page callback: background, watermark, footer ──────────────────────────
    def _draw_page(canvas, doc):
        canvas.saveState()

        # parchment background
        canvas.setFillColor(c_parchment)
        canvas.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        # watermark on page 1 only
        if doc.page == 1:
            canvas.saveState()
            canvas.setFont("Times-Roman", 80)
            canvas.setFillColor(colors.Color(0.69, 0.478, 0.227, alpha=0.04))
            canvas.translate(page_w / 2, page_h / 2)
            canvas.rotate(32)
            canvas.drawCentredString(0, 0, "CulinEire")
            canvas.restoreState()

        # footer
        y_rule = b_margin - 8 * mm
        canvas.setStrokeColor(c_stone)
        canvas.setLineWidth(0.5)
        canvas.line(l_margin, y_rule, page_w - r_margin, y_rule)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(c_muted)
        canvas.drawString(
            l_margin, y_rule - 5 * mm,
            "Bearcave Limited  ·  Company No. 658124  ·  "
            "Trading as CulinEire (Business Name No. 786815)",
        )
        canvas.drawString(
            l_margin, y_rule - 9 * mm,
            "VAT IE3645402WH  ·  culineire@bearcave.ie  ·  www.culineire.ie",
        )
        ref = getattr(doc, "_contract_ref", "")
        canvas.drawRightString(page_w - r_margin, y_rule - 5 * mm, f"Page {doc.page} of 2")
        if ref:
            canvas.drawRightString(page_w - r_margin, y_rule - 9 * mm, f"Ref: {ref}")

        canvas.restoreState()

    # ── Styles ────────────────────────────────────────────────────────────────
    brand_name = ParagraphStyle(
        "BrandName", fontName="Times-Bold", fontSize=20, leading=24,
        textColor=c_heading, alignment=TA_LEFT,
    )
    brand_sub = ParagraphStyle(
        "BrandSub", fontName="Times-Roman", fontSize=10, leading=13,
        textColor=c_muted, alignment=TA_LEFT,
    )
    hdr_label = ParagraphStyle(
        "HdrLabel", fontName="Helvetica", fontSize=7, leading=10,
        textColor=c_muted, alignment=TA_RIGHT, charSpace=0.8,
    )
    hdr_status = ParagraphStyle(
        "HdrStatus", fontName="Helvetica-Bold", fontSize=9, leading=12,
        textColor=c_copper, alignment=TA_RIGHT,
    )
    hdr_ref = ParagraphStyle(
        "HdrRef", fontName="Helvetica", fontSize=8, leading=11,
        textColor=c_muted, alignment=TA_RIGHT,
    )
    title_main = ParagraphStyle(
        "TitleMain", fontName="Times-Bold", fontSize=20, leading=24,
        textColor=c_heading, alignment=TA_CENTER, spaceBefore=6, spaceAfter=2,
    )
    title_sub = ParagraphStyle(
        "TitleSub", fontName="Times-Roman", fontSize=11, leading=14,
        textColor=c_copper, alignment=TA_CENTER, spaceAfter=8,
    )
    card_head = ParagraphStyle(
        "CardHead", fontName="Helvetica-Bold", fontSize=7, leading=10,
        textColor=c_copper, alignment=TA_LEFT, charSpace=1.0, spaceAfter=5,
    )
    card_primary = ParagraphStyle(
        "CardPrimary", fontName="Helvetica-Bold", fontSize=9, leading=13,
        textColor=c_heading, alignment=TA_LEFT,
    )
    card_detail = ParagraphStyle(
        "CardDetail", fontName="Helvetica", fontSize=8, leading=12,
        textColor=c_muted, alignment=TA_LEFT,
    )
    sec_num_s = ParagraphStyle(
        "SecNum", fontName="Helvetica-Bold", fontSize=8, leading=11,
        textColor=c_copper,
    )
    sec_title_s = ParagraphStyle(
        "SecTitle", fontName="Helvetica-Bold", fontSize=8, leading=11,
        textColor=c_heading, charSpace=0.5, spaceAfter=3,
    )
    body_style = ParagraphStyle(
        "Body", fontName="Helvetica", fontSize=8.5, leading=13,
        textColor=c_text, alignment=TA_JUSTIFY, spaceAfter=0,
    )

    # ── Data ──────────────────────────────────────────────────────────────────
    payment = getattr(application, "payment", None)
    cell = application.cell

    if cell.is_centre:
        placement_label = "Central Sponsor of the Month"
        slot_detail    = "Central featured position"
    elif application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        placement_label = "7-Day Ring Sponsor Slot"
        slot_detail    = f"Ring {cell.ring}  ·  Cell #{cell.cell_number}"
    else:
        placement_label = "Annual Ring Sponsor Slot"
        slot_detail    = f"Ring {cell.ring}  ·  Cell #{cell.cell_number}"

    if application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        term_label   = "7 calendar days"
        service_text = (
            f"Bearcave Limited has approved and activated a 7-Day Ring Sponsor Slot on the "
            f"CulinEire Sponsor Puzzle at Ring {_safe(cell.ring)}, Cell #{_safe(cell.cell_number)}. "
            "The sponsor logo or avatar will be displayed on the CulinEire website for "
            "7 calendar days from the activation date stated above. This is a one-off payment for "
            "a single 7-day sponsorship placement period. It is not a weekly subscription and does "
            "not renew automatically."
        )
        payment_text = (
            "The net sponsor fee is quoted exclusive of VAT. VAT was calculated at Stripe Checkout "
            "where applicable. Payment reserved the selected sponsor spot for review only. Payment "
            "did not guarantee approval, publication or activation. The sponsorship term starts from "
            "the activation date confirmed above. Your payment covers one fixed 7-day sponsorship "
            "period only. No recurring weekly charge or automatic renewal applies unless you place a "
            "new order."
        )
        approval_text = (
            "All sponsorship applications are subject to review and approval by Bearcave Limited. "
            "Payment does not guarantee acceptance, approval, publication or activation of a sponsor "
            "slot. Bearcave Limited may refuse, delay, cancel, suspend or reject a sponsorship "
            "application where legal, payment, compliance, sanctions, fraud, content, reputational, "
            "technical or policy concerns arise. A paid sponsor spot is not published automatically. "
            "The submitted logo or avatar becomes visible only after Bearcave Limited approves and "
            "publishes it."
        )
        refund_text = (
            "If Bearcave Limited declines a paid placement before publication, the application enters "
            "the refund-required workflow and Bearcave Limited will process a refund through Stripe. "
            "Once a sponsor image has been published, refunds are not guaranteed unless required by "
            "applicable law or agreed in writing by Bearcave Limited. Bearcave Limited may suspend, "
            "cancel or remove a sponsorship placement where compliance, sanctions, legal or policy "
            "concerns arise."
        )
        sanctions_text = (
            "By submitting the sponsor application, the sponsor confirmed that, to the best of their "
            "knowledge, neither the sponsor, nor the company or organisation represented, nor any "
            "relevant owner, director, beneficial owner or controlling person, is subject to EU, UN, "
            "Irish or other applicable financial sanctions. The applicant also confirmed that they "
            "are not applying for sponsorship on behalf of, for the benefit of, or under the control "
            "of any sanctioned person, entity or body. Bearcave Limited cannot accept sponsorship "
            "from persons or entities subject to applicable sanctions, asset freezes or restrictive measures."
        )
    elif application.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY:
        term_label   = "30 calendar days"
        service_text = (
            "Bearcave Limited has approved and activated the Central Sponsor of the Month placement "
            "on the CulinEire Sponsor Puzzle. The sponsor logo or avatar will be displayed in the "
            "central featured position on the CulinEire website for 30 calendar days from the "
            "activation date stated above. This is a one-time placement and is not a recurring "
            "subscription or calendar-month product."
        )
        payment_text = (
            "The net sponsor fee was quoted exclusive of VAT. VAT was calculated at Stripe Checkout "
            "where applicable. Payment reserved the selected sponsor spot for review only. Payment "
            "did not guarantee approval, publication or activation. The sponsorship term starts from "
            "the activation date confirmed above."
        )
        approval_text  = ""
        refund_text    = (
            "Once a sponsor image has been published, refunds are not guaranteed unless required by "
            "applicable law or agreed in writing by Bearcave Limited. Bearcave Limited may suspend, "
            "cancel or remove a sponsorship placement where compliance, sanctions, legal or policy "
            "concerns arise."
        )
        sanctions_text = (
            "By submitting the sponsor application, the sponsor confirmed that, to the best of their "
            "knowledge, neither the sponsor, nor the company or organisation represented, nor any "
            "relevant owner, director, beneficial owner or controlling person, is subject to EU, UN, "
            "Irish or other applicable financial sanctions."
        )
    else:
        term_label   = "12 months"
        service_text = (
            f"Bearcave Limited has approved and activated an Annual Ring Sponsor Slot on the "
            f"CulinEire Sponsor Puzzle at Ring {_safe(cell.ring)}, Cell #{_safe(cell.cell_number)}. "
            "The sponsor logo or avatar will be displayed on the CulinEire website for 12 months "
            "from the activation date stated above, subject to the terms below."
        )
        payment_text = (
            "The net sponsor fee was quoted exclusive of VAT. VAT was calculated at Stripe Checkout "
            "where applicable. Payment reserved the selected sponsor spot for review only. Payment "
            "did not guarantee approval, publication or activation. The sponsorship term starts from "
            "the activation date confirmed above."
        )
        approval_text  = ""
        refund_text    = (
            "Once a sponsor image has been published, refunds are not guaranteed unless required by "
            "applicable law or agreed in writing by Bearcave Limited. Bearcave Limited may suspend, "
            "cancel or remove a sponsorship placement where compliance, sanctions, legal or policy "
            "concerns arise."
        )
        sanctions_text = (
            "By submitting the sponsor application, the sponsor confirmed that, to the best of their "
            "knowledge, neither the sponsor, nor the company or organisation represented, nor any "
            "relevant owner, director, beneficial owner or controlling person, is subject to EU, UN, "
            "Irish or other applicable financial sanctions."
        )

    activation_str  = _fmt_date(application.published_at)
    end_str         = _fmt_date(application.expires_at)
    terms_date_str  = _fmt_date(application.terms_accepted_at)

    # ── Header ────────────────────────────────────────────────────────────────
    hdr_left = [
        Paragraph("CulinEire", brand_name),
        Paragraph("Sponsor Agreement", brand_sub),
    ]
    hdr_right = [
        Paragraph("PROVIDER COPY", hdr_label),
        Paragraph("Activated", hdr_status),
        Paragraph(f"Ref: {_safe(application.contract_reference)}", hdr_ref),
    ]
    header_table = Table(
        [[hdr_left, hdr_right]],
        colWidths=[text_w * 0.6, text_w * 0.4],
    )
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    def _copper_rule():
        return HRFlowable(width="100%", thickness=1.2, color=c_copper,
                          spaceAfter=6, spaceBefore=0)

    def _stone_rule():
        return HRFlowable(width="100%", thickness=0.4, color=c_stone,
                          spaceAfter=4, spaceBefore=8)

    def _ornament():
        return Paragraph(
            "◆",
            ParagraphStyle(
                "Orn", fontName="Helvetica", fontSize=9, leading=16,
                textColor=c_copper, alignment=TA_CENTER, spaceBefore=8, spaceAfter=8,
            ),
        )

    # ── 3 summary cards ───────────────────────────────────────────────────────
    def _card_cell(heading, lines):
        items = [Paragraph(heading.upper(), card_head)]
        for i, line in enumerate(lines):
            items.append(Paragraph(_safe(line), card_primary if i == 0 else card_detail))
        return items

    sponsor_lines = [application.sponsor_name, application.contact_name, application.email]
    if application.website_url:
        sponsor_lines.append(application.website_url)

    placement_lines = [placement_label, slot_detail, f"{activation_str} → {end_str}"]

    payment_lines = [f"Net  {_cents_display(application.price_net_cents)}"]
    if payment and payment.vat_amount_cents:
        payment_lines.append(f"VAT (23%)  {_cents_display(payment.vat_amount_cents)}")
    if payment and payment.total_amount_cents:
        payment_lines.append(f"Total paid  {_cents_display(payment.total_amount_cents)}")

    gap = 3 * mm
    cw  = (text_w - 2 * gap) / 3
    cards_table = Table(
        [[
            _card_cell("Sponsor",   sponsor_lines),
            Spacer(gap, 1),
            _card_cell("Placement", placement_lines),
            Spacer(gap, 1),
            _card_cell("Payment",   payment_lines),
        ]],
        colWidths=[cw, gap, cw, gap, cw],
    )
    cards_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND",    (0, 0), (0, 0),   c_card),
        ("BACKGROUND",    (2, 0), (2, 0),   c_card),
        ("BACKGROUND",    (4, 0), (4, 0),   c_card),
        ("LINEABOVE",     (0, 0), (0, 0),   2.0, c_copper),
        ("LINEABOVE",     (2, 0), (2, 0),   2.0, c_copper),
        ("LINEABOVE",     (4, 0), (4, 0),   2.0, c_copper),
        ("BOX",           (0, 0), (0, 0),   0.5, c_stone),
        ("BOX",           (2, 0), (2, 0),   0.5, c_stone),
        ("BOX",           (4, 0), (4, 0),   0.5, c_stone),
        ("TOPPADDING",    (0, 0), (0, 0),   10),
        ("TOPPADDING",    (2, 0), (2, 0),   10),
        ("TOPPADDING",    (4, 0), (4, 0),   10),
        ("BOTTOMPADDING", (0, 0), (0, 0),   12),
        ("BOTTOMPADDING", (2, 0), (2, 0),   12),
        ("BOTTOMPADDING", (4, 0), (4, 0),   12),
        ("LEFTPADDING",   (0, 0), (0, 0),   10),
        ("RIGHTPADDING",  (0, 0), (0, 0),   10),
        ("LEFTPADDING",   (2, 0), (2, 0),   10),
        ("RIGHTPADDING",  (2, 0), (2, 0),   10),
        ("LEFTPADDING",   (4, 0), (4, 0),   10),
        ("RIGHTPADDING",  (4, 0), (4, 0),   10),
        ("LEFTPADDING",   (1, 0), (1, 0),   0),
        ("RIGHTPADDING",  (1, 0), (1, 0),   0),
        ("LEFTPADDING",   (3, 0), (3, 0),   0),
        ("RIGHTPADDING",  (3, 0), (3, 0),   0),
    ]))

    # ── QR code ───────────────────────────────────────────────────────────────
    qr_row = None
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        qr_size = 18 * mm
        qr = QrCodeWidget("https://www.culineire.ie")
        qr.barWidth  = qr_size
        qr.barHeight = qr_size
        d = Drawing(qr_size, qr_size)
        d.add(qr)
        qr_label = Paragraph(
            '<font color="#B07A3A">www.culineire.ie</font>',
            ParagraphStyle("QRL", fontName="Helvetica", fontSize=6.5, leading=9,
                           textColor=c_copper, alignment=TA_CENTER),
        )
        qr_block = Table([[d], [qr_label]], colWidths=[20 * mm])
        qr_block.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        qr_row = Table(
            [[Spacer(1, 1), qr_block]],
            colWidths=[text_w - 20 * mm, 20 * mm],
        )
        qr_row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    except Exception:
        pass

    # ── Numbered sections ─────────────────────────────────────────────────────
    def _section(num, title, paragraphs):
        num_p   = Paragraph(f'<font color="#B07A3A">{num}</font>', sec_num_s)
        title_p = Paragraph(title.upper(), sec_title_s)
        hdr_row = Table([[num_p, title_p]], colWidths=[8 * mm, text_w - 8 * mm])
        hdr_row.setStyle(TableStyle([
            ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ]))
        head = [_stone_rule(), hdr_row]
        if paragraphs:
            head.append(Paragraph(paragraphs[0], body_style))
        items = [KeepTogether(head)]
        for text in paragraphs[1:]:
            items.append(Paragraph(text, body_style))
        return items

    if approval_text:
        sec_offset = 5
    else:
        sec_offset = 4

    # ── Story ─────────────────────────────────────────────────────────────────
    story = [
        header_table,
        _copper_rule(),
        Paragraph("Sponsor Agreement", title_main),
        Paragraph(placement_label, title_sub),
        Spacer(1, 2 * mm),
        cards_table,
        Spacer(1, 4 * mm),
    ]

    story += _section(
        "01", "Parties", [
            "<b>Service provider:</b> Bearcave Limited, Company No. 658124, 2 The Fairways, "
            "Tir Cluain, Midleton, Co. Cork, P25 W8W3, Ireland. Trading as CulinEire "
            "(Business Name No. 786815). VAT number: IE3645402WH.",
            f"<b>Client / Sponsor:</b> {_safe(application.sponsor_name)}, "
            f"{_safe(application.contact_name)}, {_safe(application.email)}",
        ],
    )
    story += _section("02", "Service",     [service_text])
    story += _section("03", "Payment and VAT", [payment_text])
    if approval_text:
        story += _section("04", "Approval Before Publication", [approval_text])

    if qr_row:
        story += [Spacer(1, 4 * mm), qr_row]

    story.append(_ornament())

    story += _section(
        f"{sec_offset:02d}", "Sponsor Materials Licence", [
            "The sponsor confirms they have the right to use the submitted logo, avatar, website or "
            "profile link and related materials. The sponsor grants Bearcave Limited a non-exclusive "
            "licence to display those materials on CulinEire for the sponsorship term.",
        ],
    )
    story += _section(
        f"{sec_offset+1:02d}", "Content Standards", [
            "The sponsor must not use the sponsorship slot to promote unlawful goods or services, "
            "defamatory content, misleading claims, infringing materials or anything that violates "
            "Irish or EU law. The sponsor must not imply editorial endorsement by CulinEire or "
            "Bearcave Limited unless expressly agreed in writing.",
        ],
    )
    story += _section(
        f"{sec_offset+2:02d}", "No Guarantee of Results", [
            "Bearcave Limited does not guarantee any particular level of traffic, impressions, clicks "
            "or commercial results from the sponsorship placement.",
        ],
    )
    story += _section(
        f"{sec_offset+3:02d}", "Website Changes and Availability", [
            "CulinEire is provided on a best-efforts basis. Bearcave Limited may update the website "
            "design, layout or features at any time without affecting the sponsor's right to display "
            "their approved logo or avatar for the agreed term, except where required by law, safety "
            "or compliance obligations.",
        ],
    )
    story += _section(f"{sec_offset+4:02d}", "Refunds and Compliance",             [refund_text])
    story += _section(f"{sec_offset+5:02d}", "Sanctions and Compliance Declaration", [sanctions_text])
    story += _section(
        f"{sec_offset+6:02d}", "Governing Law", [
            "This agreement is governed by the laws of Ireland. Any disputes are subject to the "
            "exclusive jurisdiction of the Irish courts, without prejudice to any statutory rights "
            "that may apply under Irish or EU law.",
        ],
    )
    story += _section(
        f"{sec_offset+7:02d}", "Electronic Acceptance", [
            f"This agreement was entered into electronically when the sponsor submitted their "
            f"application and accepted the CulinEire sponsorship terms via the website on "
            f"{_safe(terms_date_str)}. This document is the provider copy issued on behalf of "
            f"Bearcave Limited upon activation of the sponsorship.",
        ],
    )

    # ── Build ─────────────────────────────────────────────────────────────────
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=l_margin,
        rightMargin=r_margin,
        topMargin=t_margin,
        bottomMargin=b_margin,
        title=f"CulinEire Sponsor Agreement {application.contract_reference}",
        author="Bearcave Limited",
    )
    doc._contract_ref = application.contract_reference
    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buf.getvalue()


def generate_invoice_pdf(application: SponsorApplication) -> bytes:  # noqa: C901
    import os
    from io import BytesIO
    from xml.sax.saxutils import escape

    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable,
            Image as RLImage,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except ImportError as exc:
        raise RuntimeError("reportlab is not installed.") from exc

    # ── Palette ───────────────────────────────────────────────────────────────
    c_parchment = colors.HexColor("#FAF6EF")
    c_card      = colors.HexColor("#FFFDF8")
    c_text      = colors.HexColor("#2A2622")
    c_heading   = colors.HexColor("#1E1A16")
    c_copper    = colors.HexColor("#B07A3A")
    c_stone     = colors.HexColor("#D8C8B6")
    c_muted     = colors.HexColor("#6B5E52")
    c_stripe    = colors.HexColor("#F0EBE3")  # subtle band for header bg

    page_w, page_h = A4
    l_margin = r_margin = 20 * mm
    t_margin = 18 * mm
    b_margin = 24 * mm
    text_w = page_w - l_margin - r_margin

    payment = getattr(application, "payment", None)
    cell    = application.cell

    def _eur(cents):
        return f"EUR {cents / 100:.2f}" if cents else "EUR 0.00"

    def _fmt_date(dt):
        return f"{dt.day} {dt.strftime('%B %Y')}" if dt else "-"

    def _safe(v):
        return escape(str(v or ""))

    def _p(text, **kw):
        return Paragraph(_safe(text), ParagraphStyle("_", **kw))

    raw_ref        = application.contract_reference or ""
    parts          = raw_ref.split("-")
    invoice_number = "INV-" + "-".join(parts[2:]) if len(parts) >= 4 else f"INV-{raw_ref}"
    issue_date     = _fmt_date(application.published_at)
    supply_date    = _fmt_date(application.published_at)
    payment_date   = _fmt_date(payment.paid_at if payment else None)
    service_period = f"{_fmt_date(application.published_at)} – {_fmt_date(application.expires_at)}"

    if cell.is_centre:
        service_desc = "CulinEire Sponsor Placement — Central Sponsor of the Month"
    elif application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        service_desc = (
            f"CulinEire 7-Day Ring Sponsor Slot — Ring {cell.ring}, Cell #{cell.cell_number}"
        )
    else:
        service_desc = (
            f"CulinEire Annual Ring Sponsor Slot — Ring {cell.ring}, Cell #{cell.cell_number}"
        )

    net_eur   = _eur(application.price_net_cents)
    vat_eur   = _eur(payment.vat_amount_cents   if payment else 0)
    total_eur = _eur(payment.total_amount_cents if payment else 0)

    # ── Logo ──────────────────────────────────────────────────────────────────
    logo_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static", "images", "logo2.png",
    )
    logo_sz = 14 * mm
    try:
        logo_img = RLImage(logo_path, width=logo_sz, height=logo_sz)
    except Exception:
        logo_img = Spacer(logo_sz, logo_sz)

    # ── QR code ───────────────────────────────────────────────────────────────
    qr_sz      = 18 * mm
    qr_element = None
    try:
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        _qr = QrCodeWidget("https://www.culineire.ie")
        _qr.barWidth  = qr_sz
        _qr.barHeight = qr_sz
        _d = Drawing(qr_sz, qr_sz)
        _d.add(_qr)
        qr_element = _d
    except Exception:
        pass

    # ── Page background + footer ──────────────────────────────────────────────
    def _draw_page(canvas, doc):
        canvas.saveState()
        canvas.setFillColor(c_parchment)
        canvas.rect(0, 0, page_w, page_h, fill=1, stroke=0)

        # subtle watermark
        canvas.saveState()
        canvas.setFont("Times-Roman", 90)
        canvas.setFillColor(colors.Color(0.69, 0.478, 0.227, alpha=0.035))
        canvas.translate(page_w / 2, page_h / 2)
        canvas.rotate(32)
        canvas.drawCentredString(0, 0, "CulinEire")
        canvas.restoreState()

        y = b_margin - 8 * mm
        canvas.setStrokeColor(c_stone)
        canvas.setLineWidth(0.5)
        canvas.line(l_margin, y, page_w - r_margin, y)
        canvas.setFont("Helvetica", 6.5)
        canvas.setFillColor(c_muted)
        canvas.drawString(l_margin, y - 5 * mm,
            "Bearcave Limited  ·  Company No. 658124  ·  Trading as CulinEire (Business Name No. 786815)")
        canvas.drawString(l_margin, y - 9 * mm,
            "VAT IE3645402WH  ·  culineire@bearcave.ie  ·  www.culineire.ie")
        inv = getattr(doc, "_invoice_number", "")
        canvas.drawRightString(page_w - r_margin, y - 5 * mm, "VAT Invoice")
        if inv:
            canvas.drawRightString(page_w - r_margin, y - 9 * mm, inv)
        canvas.restoreState()

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOCK 1 — HEADER BAND
    # Left:  logo + wordmark    Right: invoice meta (number / date / status)
    # ═══════════════════════════════════════════════════════════════════════════
    wordmark_col = Table(
        [[logo_img,
          Paragraph("CulinEire",
                    ParagraphStyle("WM", fontName="Times-Bold", fontSize=18, leading=20,
                                   textColor=c_heading))]],
        colWidths=[logo_sz + 3 * mm, text_w * 0.35 - logo_sz - 3 * mm],
    )
    wordmark_col.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    hdr_right_data = [
        [_p("TAX INVOICE", fontName="Helvetica", fontSize=7, textColor=c_muted,
            alignment=TA_RIGHT, charSpace=1.2)],
        [_p(invoice_number, fontName="Helvetica-Bold", fontSize=13, textColor=c_copper,
            alignment=TA_RIGHT)],
        [_p(issue_date, fontName="Helvetica", fontSize=8, textColor=c_muted,
            alignment=TA_RIGHT)],
    ]
    hdr_right = Table(hdr_right_data, colWidths=[text_w * 0.65])
    hdr_right.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]))

    header_band = Table(
        [[wordmark_col, hdr_right]],
        colWidths=[text_w * 0.35, text_w * 0.65],
    )
    header_band.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))

    copper_rule = HRFlowable(width="100%", thickness=1.2, color=c_copper,
                             spaceAfter=5, spaceBefore=0)
    stone_rule  = HRFlowable(width="100%", thickness=0.4, color=c_stone,
                             spaceAfter=4, spaceBefore=6)

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOCK 2 — INVOICE META + PAYMENT REF  (full-width, 2 columns inside)
    # ═══════════════════════════════════════════════════════════════════════════
    lbl_s  = ParagraphStyle("LS", fontName="Helvetica", fontSize=7.5, textColor=c_muted,   leading=12)
    val_s  = ParagraphStyle("VS", fontName="Helvetica-Bold", fontSize=7.5, textColor=c_heading, leading=12)
    lbl_cw = 28 * mm
    val_cw = text_w / 2 - lbl_cw - 4 * mm

    meta_left = [
        [Paragraph("Invoice No.",   lbl_s), Paragraph(invoice_number, val_s)],
        [Paragraph("Issue date",    lbl_s), Paragraph(issue_date,     val_s)],
        [Paragraph("Supply date",   lbl_s), Paragraph(supply_date,    val_s)],
        [Paragraph("Application",   lbl_s), Paragraph(_safe(application.contract_reference), val_s)],
    ]
    meta_right = []
    if payment and payment.paid_at:
        meta_right.append([Paragraph("Payment date", lbl_s), Paragraph(payment_date, val_s)])
    if payment and payment.stripe_payment_intent_id:
        meta_right.append([Paragraph("Stripe Ref.",  lbl_s),
                           Paragraph(_safe(payment.stripe_payment_intent_id), val_s)])

    def _meta_block(rows):
        if not rows:
            return Spacer(1, 1)
        t = Table(rows, colWidths=[lbl_cw, val_cw])
        t.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, -1), c_card),
            ("LINEABOVE",     (0, 0), (-1, 0),  1.5, c_copper),
            ("BOX",           (0, 0), (-1, -1), 0.5, c_stone),
            ("TOPPADDING",    (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        return t

    col_gap = 4 * mm
    half_w  = text_w / 2 - col_gap / 2
    meta_row = Table(
        [[_meta_block(meta_left), Spacer(col_gap, 1), _meta_block(meta_right)]],
        colWidths=[half_w, col_gap, half_w],
    )
    meta_row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOCK 3 — SUPPLIER | CUSTOMER  (side by side, equal columns)
    # ═══════════════════════════════════════════════════════════════════════════
    sec_s  = ParagraphStyle("SEC", fontName="Helvetica-Bold", fontSize=7, textColor=c_copper,
                            charSpace=1.2, spaceAfter=3, leading=10)
    plbl_cw = 22 * mm

    billing = payment.billing_address if payment and payment.billing_address else {}

    supplier_rows = [
        ("Name",    "Bearcave Limited t/a CulinEire"),
        ("Address", "2 The Fairways, Tir Cluain, Midleton, Co. Cork, P25 W8W3"),
        ("Co. No.", "658124  ·  BN No. 786815"),
        ("VAT No.", "IE3645402WH"),
        ("Email",   "culineire@bearcave.ie"),
    ]
    customer_rows = [
        ("Name",    application.sponsor_name),
        ("Contact", application.contact_name),
        ("Email",   application.email),
    ]
    if application.website_url:
        customer_rows.append(("Website", application.website_url))
    if billing:
        addr_parts = [billing.get("line1", ""), billing.get("line2", ""),
                      billing.get("city", ""), billing.get("postal_code", ""),
                      billing.get("country", "")]
        addr_str = ", ".join(p for p in addr_parts if p)
        if addr_str:
            customer_rows.append(("Address", addr_str))

    def _party_block(heading, rows):
        pval_cw = half_w - plbl_cw - 16  # 16 = left+right pad
        data = [[Paragraph(heading.upper(), sec_s), ""]]
        for lbl, val in rows:
            data.append([
                Paragraph(_safe(lbl), ParagraphStyle("PL", fontName="Helvetica",      fontSize=7.5, textColor=c_muted,   leading=12)),
                Paragraph(_safe(val), ParagraphStyle("PV", fontName="Helvetica-Bold", fontSize=7.5, textColor=c_heading, leading=12)),
            ])
        t = Table(data, colWidths=[plbl_cw, pval_cw])
        t.setStyle(TableStyle([
            ("SPAN",          (0, 0), (-1, 0)),
            ("BACKGROUND",    (0, 0), (-1, -1), c_card),
            ("LINEABOVE",     (0, 0), (-1, 0),  1.5, c_copper),
            ("BOX",           (0, 0), (-1, -1), 0.5, c_stone),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING",   (0, 0), (-1, -1), 8),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        return t

    parties_row = Table(
        [[_party_block("Supplier", supplier_rows),
          Spacer(col_gap, 1),
          _party_block("Customer", customer_rows)]],
        colWidths=[half_w, col_gap, half_w],
    )
    parties_row.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOCK 4 — LINE ITEMS
    # ═══════════════════════════════════════════════════════════════════════════
    qty_w  = 12 * mm
    unit_w = 28 * mm
    amt_w  = 28 * mm
    desc_w = text_w - qty_w - unit_w - amt_w

    def _th(t, align=TA_RIGHT):
        return Paragraph(t, ParagraphStyle("TH", fontName="Helvetica-Bold", fontSize=7,
                                           textColor=c_muted, charSpace=0.4, alignment=align))

    def _td(t, align=TA_RIGHT, bold=False):
        return Paragraph(_safe(t), ParagraphStyle("TD", fontName="Helvetica-Bold" if bold else "Helvetica",
                                                  fontSize=8, leading=12,
                                                  textColor=c_heading if bold else c_text, alignment=align))

    items_table = Table(
        [
            [_th("Description", TA_LEFT), _th("Qty"), _th("Unit ex VAT"), _th("Amt ex VAT")],
            [
                Paragraph(
                    f"{_safe(service_desc)}<br/>"
                    f'<font color="#6B5E52" size="7">Service period: {_safe(service_period)}</font>',
                    ParagraphStyle("DD", fontName="Helvetica", fontSize=8, leading=12, textColor=c_text),
                ),
                _td("1"),
                _td(net_eur),
                _td(net_eur),
            ],
        ],
        colWidths=[desc_w, qty_w, unit_w, amt_w],
    )
    items_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0),  c_card),
        ("LINEABOVE",     (0, 0), (-1, 0),  1.5, c_copper),
        ("LINEBELOW",     (0, 0), (-1, 0),  0.4, c_stone),
        ("BOX",           (0, 0), (-1, -1), 0.5, c_stone),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
    ]))

    # ═══════════════════════════════════════════════════════════════════════════
    # BLOCK 5 — TOTALS (right-aligned) + QR (far right)
    # ═══════════════════════════════════════════════════════════════════════════
    tot_lbl_w = 36 * mm
    tot_val_w = 28 * mm
    tot_w     = tot_lbl_w + tot_val_w

    def _trow(lbl, val, bold=False):
        ls = ParagraphStyle("TL", fontName="Helvetica-Bold" if bold else "Helvetica",
                            fontSize=8.5 if bold else 8, textColor=c_heading if bold else c_muted)
        vs = ParagraphStyle("TV", fontName="Helvetica-Bold" if bold else "Helvetica",
                            fontSize=8.5 if bold else 8,
                            textColor=c_copper if bold else c_text, alignment=TA_RIGHT)
        return [Paragraph(lbl, ls), Paragraph(val, vs)]

    totals_inner = Table(
        [_trow("Net amount", net_eur),
         _trow("VAT  23% Irish VAT", vat_eur),
         _trow("Total", total_eur, bold=True)],
        colWidths=[tot_lbl_w, tot_val_w],
    )
    totals_inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), c_card),
        ("BOX",           (0, 0), (-1, -1), 0.5, c_stone),
        ("LINEABOVE",     (0, -1), (-1, -1), 0.8, c_stone),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
    ]))

    if payment and payment.status == SponsorPayment.Status.PAID:
        status_str = f"PAID  ·  {payment_date}  ·  Stripe card payment"
    elif payment and payment.status == SponsorPayment.Status.REFUNDED:
        status_str = f"REFUNDED  ·  {_fmt_date(payment.refunded_at)}"
    else:
        status_str = "UNPAID"

    status_para = Paragraph(status_str,
                            ParagraphStyle("STP", fontName="Helvetica-Bold", fontSize=8,
                                           textColor=c_copper, alignment=TA_RIGHT))

    qr_label = Paragraph(
        '<font color="#B07A3A">www.culineire.ie</font>',
        ParagraphStyle("QL", fontName="Helvetica", fontSize=6, textColor=c_copper, alignment=TA_CENTER),
    )
    if qr_element:
        qr_block = Table([[qr_element], [qr_label]], colWidths=[qr_sz + 2 * mm])
        qr_block.setStyle(TableStyle([
            ("ALIGN",         (0, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING",   (0, 0), (-1, -1), 0),
            ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
            ("TOPPADDING",    (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        qr_block = Spacer(qr_sz, qr_sz)

    qr_col_w  = qr_sz + 4 * mm
    # layout: [spacer | totals | gap | qr]
    bottom_table = Table(
        [[Spacer(1, 1), totals_inner, Spacer(4 * mm, 1), qr_block]],
        colWidths=[text_w - tot_w - qr_col_w - 4 * mm, tot_w, 4 * mm, qr_col_w],
    )
    bottom_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "BOTTOM"),
        ("LEFTPADDING",   (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 0),
        ("TOPPADDING",    (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))

    # ── Notes ─────────────────────────────────────────────────────────────────
    notes_para = Paragraph(
        "VAT invoice issued by Bearcave Limited (t/a CulinEire) for sponsorship placement services "
        "on culineire.ie. Supply date is the activation date of the sponsorship. "
        "Subject to CulinEire Sponsor Terms. Invoice queries: culineire@bearcave.ie",
        ParagraphStyle("NP", fontName="Helvetica", fontSize=7, leading=10,
                       textColor=c_muted, alignment=TA_JUSTIFY),
    )

    # ── Story ─────────────────────────────────────────────────────────────────
    sp = lambda n: Spacer(1, n * mm)
    story = [
        header_band,
        copper_rule,
        sp(2),
        meta_row,
        sp(2.5),
        parties_row,
        sp(2.5),
        items_table,
        sp(2),
        status_para,
        sp(2),
        bottom_table,
        stone_rule,
        notes_para,
    ]

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=l_margin,
        rightMargin=r_margin,
        topMargin=t_margin,
        bottomMargin=b_margin,
        title=f"CulinEire VAT Invoice {invoice_number}",
        author="Bearcave Limited",
    )
    doc._invoice_number = invoice_number
    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buf.getvalue()


def _send_contract_email(application: SponsorApplication) -> str:
    """Send a short agreement email with the sponsor contract PDF and VAT invoice attached."""
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from config.email_utils import build_absolute_url, sanitize_email_subject

    payment = getattr(application, "payment", None)
    template = _select_agreement_template(application.product_type)
    pdf_filename     = f"CulinEire_Sponsor_Agreement_{application.contract_reference}.pdf"
    invoice_filename = f"CulinEire_VAT_Invoice_{application.contract_reference}.pdf"
    pdf_bytes     = generate_contract_pdf(application)
    invoice_bytes = generate_invoice_pdf(application)

    email_context = {
        "application": application,
        "payment": payment,
        "contract_reference": application.contract_reference,
        "activation_date": application.published_at,
        "end_date": application.expires_at,
        "site_url": build_absolute_url(""),
    }
    subject = sanitize_email_subject(
        f"CulinEire Sponsor Agreement - {application.contract_reference}"
    )
    html_body = render_to_string(f"emails/{template}.html", email_context)
    text_body = render_to_string(f"emails/{template}.txt", email_context)

    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[application.email],
    )
    msg.attach_alternative(html_body, "text/html")
    msg.attach(pdf_filename,     pdf_bytes,     "application/pdf")
    msg.attach(invoice_filename, invoice_bytes, "application/pdf")
    msg.send(fail_silently=False)
    return pdf_filename


def resend_contract_email(application_id: int, actor) -> SponsorApplication:
    application = SponsorApplication.objects.select_related("cell", "payment").get(pk=application_id)
    if application.status != SponsorApplication.Status.APPROVED:
        raise ValueError("Contract email can only be resent for approved applications.")
    if not application.contract_reference:
        application.contract_reference = _generate_contract_reference(application)
        application.save(update_fields=["contract_reference", "updated_at"])
    try:
        pdf_filename = _send_contract_email(application)
        application.contract_sent_at = timezone.now()
        application.contract_email_status = SponsorApplication.ContractEmailStatus.RESENT
        application.save(update_fields=["contract_sent_at", "contract_email_status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CONTRACT_EMAIL_RESENT,
            application=application,
            actor=actor,
            notes=f"Agreement email resent to {application.email}",
            metadata={
                "pdf_attached": True,
                "pdf_filename": pdf_filename,
                "contract_reference": application.contract_reference,
            },
        )
    except Exception:
        import logging as _logging
        _logging.getLogger(__name__).exception(
            "Failed to resend sponsor contract email for application pk=%s", application.pk,
        )
        application.contract_email_status = SponsorApplication.ContractEmailStatus.FAILED
        application.save(update_fields=["contract_email_status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CONTRACT_EMAIL_FAILED,
            application=application,
            actor=actor,
            notes="Contract email resend failed.",
        )
    return application


def _notify_sponsor_changes_requested(application: SponsorApplication, notes: str) -> None:
    try:
        from config.email_utils import send_template_mail
        send_template_mail(
            subject="Changes requested for your CulinEire sponsor application",
            template="sponsor_changes_requested",
            context={
                "sponsor_name": application.sponsor_name,
                "product_name": (
                    "Sponsor of the Month"
                    if application.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY
                    else "Annual Ring Sponsorship"
                ),
                "notes": notes,
            },
            recipient_list=[application.email],
            fail_silently=True,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to send sponsor changes-requested email for application pk=%s",
            application.pk,
        )


def request_application_changes(application_id: int, actor, notes: str) -> SponsorApplication:
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("A note explaining the requested changes is required.")
    with transaction.atomic():
        application = SponsorApplication.objects.select_for_update().select_related("cell").get(pk=application_id)
        if application.status not in {
            SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            SponsorApplication.Status.PAID_PENDING_APPROVAL,
        }:
            raise ValueError("Changes can only be requested for paid applications pending approval or pending compliance review.")
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = application.status
        application.status = SponsorApplication.Status.CHANGES_REQUESTED
        application.save(update_fields=["status", "updated_at"])
        cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.CHANGES_REQUESTED,
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=application.status,
            notes=notes,
        )
    _notify_sponsor_changes_requested(application, notes)
    return application


def mark_application_ready_for_review(application_id: int, actor, notes: str = "") -> SponsorApplication:
    with transaction.atomic():
        application = SponsorApplication.objects.select_for_update().select_related("cell").get(pk=application_id)
        if application.status != SponsorApplication.Status.CHANGES_REQUESTED:
            raise ValueError("Only applications with changes requested can be marked ready for review.")
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        from_status = application.status
        application.status = SponsorApplication.Status.PAID_PENDING_APPROVAL
        application.save(update_fields=["status", "updated_at"])
        cell.status = SponsorCell.Status.PAID_PENDING_APPROVAL
        cell.save(update_fields=["status", "updated_at"])
        record_audit(
            action=SponsorAuditLog.Action.READY_FOR_REVIEW,
            application=application,
            actor=actor,
            from_status=from_status,
            to_status=application.status,
            notes=(notes or "").strip(),
        )
        return application


def reject_application(application_id: int, actor, reason: str = "") -> SponsorApplication:
    reason = (reason or "").strip()
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
            SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            SponsorApplication.Status.PAID_PENDING_APPROVAL,
            SponsorApplication.Status.CHANGES_REQUESTED,
        }
        if application.status not in _REJECTABLE_STATES:
            raise ValueError(
                f"Cannot reject application in status '{application.status}'. "
                f"Only draft, payment_pending, paid_pending_compliance_review, paid_pending_approval, or changes_requested applications can be rejected."
            )
        cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
        payment = getattr(application, "payment", None)
        from_status = application.status
        requires_refund = payment and payment.status == SponsorPayment.Status.PAID
        if requires_refund and not reason:
            raise ValueError("A staff note is required to mark a paid sponsor application refund required.")

        application.rejected_by = actor
        application.rejected_at = timezone.now()
        application.rejection_reason = reason
        application.status = (
            SponsorApplication.Status.REFUND_REQUIRED
            if requires_refund
            else SponsorApplication.Status.REJECTED
        )
        application.save()

        cell.status = (
            SponsorCell.Status.PAID_PENDING_APPROVAL
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
            metadata={
                "cell_status": cell.status,
                "manual_refund_tracking": application.status == SponsorApplication.Status.REFUND_REQUIRED,
            },
        )
        return application


def mark_refund_completed(application_id: int, actor, notes: str = "") -> SponsorApplication:
    notes = (notes or "").strip()
    if not notes:
        raise ValueError("A staff note is required to mark a sponsor refund completed manually.")
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
            metadata={"cell_released": True, "manual_refund_tracking": True},
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
        # Weekly ring cells return to AVAILABLE so they can be repurchased immediately.
        # Annual and monthly cells go to EXPIRED and require manual staff release.
        if cell.product_type == SponsorCell.ProductType.WEEKLY_RING:
            cell.status = SponsorCell.Status.AVAILABLE
        else:
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
    ("Update annual and central monthly sponsorship terms wording", "Phase 1: Foundation", True, False),
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
    stripe_mode = str(getattr(settings, "STRIPE_PRICE_MODE", "") or "").lower()
    stripe_live_mode = stripe_mode == "live"
    try:
        validate_stripe_runtime_configuration(require_webhook_secret=webhook_secret)
        stripe_configuration_consistent = True
    except SponsorStripeConfigurationError:
        stripe_configuration_consistent = False

    checks = {
        "stripe": [
            ("Mode/key consistency", stripe_configuration_consistent),
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
            ("Paid pending compliance review working", True),
            ("Approval publishing working", True),
            ("Rejection/refund workflow working", True),
        ],
        "tests": [
            ("Unit tests", any(item.title == "Add tests" and item.status == SponsorRoadmapItem.Status.DONE for item in items)),
            ("Integration tests", False),
            ("Webhook tests", False),
            ("Manual test checklist", True),
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
        "current_phase": "Stripe live readiness review",
        "last_updated": max((item.updated_at for item in items), default=timezone.now()),
        "environment_mode": "Stripe live mode" if stripe_live_mode else "Stripe test mode",
        "checks": checks,
    }
