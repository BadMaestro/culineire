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
        else "CulinEire Weekly Ring Sponsor Spot" if is_weekly
        else "CulinEire Annual Sponsor Spot"
    )
    product_description = (
        "Monthly central sponsor placement on the CulinEire Sponsor Puzzle" if is_central
        else "Weekly ring sponsor placement on the CulinEire Sponsor Puzzle" if is_weekly
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
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.styles import ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            HRFlowable, KeepTogether, Paragraph, SimpleDocTemplate,
            Spacer, Table, TableStyle,
        )
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    except ImportError as exc:
        raise RuntimeError("reportlab is not installed. Add reportlab to requirements.txt.") from exc

    # ── colours ──────────────────────────────────────────────────────────────
    C_DARK    = colors.HexColor("#1f2c25")   # near-black green
    C_BRAND   = colors.HexColor("#184c3a")   # CulinEire dark green
    C_MUTED   = colors.HexColor("#6b5e52")   # warm grey-brown
    C_RULE    = colors.HexColor("#c8beb4")   # light warm border
    C_ROW_A   = colors.HexColor("#f5f0eb")   # table alternate row
    C_FOOT    = colors.HexColor("#8a7d74")   # footer text

    PAGE_W, PAGE_H = A4
    L_MARGIN = R_MARGIN = 22 * mm
    T_MARGIN = 22 * mm
    B_MARGIN = 26 * mm          # extra room for canvas footer
    TEXT_W   = PAGE_W - L_MARGIN - R_MARGIN

    # ── per-page canvas footer ────────────────────────────────────────────────
    footer_line1 = (
        "Bearcave Limited  •  Company No. 658124  •  "
        "2 The Fairways, Tir Cluain, Midleton, Co. Cork, Ireland  •  VAT IE3645402WH"
    )
    footer_line2 = (
        "Trading as CulinEire (Business Name No. 786815)  •  culineire@bearcave.ie"
    )

    def _draw_page(canvas, doc):
        canvas.saveState()
        y_rule = B_MARGIN - 6 * mm
        canvas.setStrokeColor(C_RULE)
        canvas.setLineWidth(0.4)
        canvas.line(L_MARGIN, y_rule, PAGE_W - R_MARGIN, y_rule)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(C_FOOT)
        canvas.drawCentredString(PAGE_W / 2, y_rule - 5 * mm, footer_line1)
        canvas.drawCentredString(PAGE_W / 2, y_rule - 9 * mm, footer_line2)
        canvas.setFont("Helvetica", 7)
        canvas.drawRightString(PAGE_W - R_MARGIN, y_rule - 5 * mm, f"Page {doc.page}")
        canvas.restoreState()

    # ── styles ────────────────────────────────────────────────────────────────
    title_style = ParagraphStyle(
        "DocTitle",
        fontName="Helvetica-Bold",
        fontSize=11,
        leading=14,
        textColor=colors.white,
        alignment=TA_CENTER,
    )
    ref_style = ParagraphStyle(
        "DocRef",
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=colors.white,
        alignment=TA_CENTER,
        spaceAfter=0,
    )
    section_kicker = ParagraphStyle(
        "SectionKicker",
        fontName="Helvetica",
        fontSize=8,
        leading=10,
        spaceAfter=2,
        textColor=C_MUTED,
        alignment=TA_CENTER,
    )
    sum_heading = ParagraphStyle(
        "SumHeading",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        spaceBefore=14,
        spaceAfter=5,
        textColor=C_BRAND,
        alignment=TA_LEFT,
        charSpace=0.6,
    )
    sec_heading = ParagraphStyle(
        "SecHeading",
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=11,
        spaceBefore=0,
        spaceAfter=4,
        textColor=C_BRAND,
        charSpace=0.6,
    )
    body_style = ParagraphStyle(
        "Body",
        fontName="Helvetica",
        fontSize=9,
        leading=13.5,
        spaceAfter=0,
        alignment=TA_JUSTIFY,
    )
    t_label = ParagraphStyle(
        "TLabel",
        fontName="Helvetica",
        fontSize=8.5,
        leading=12,
        textColor=C_MUTED,
    )
    t_value = ParagraphStyle(
        "TValue",
        fontName="Helvetica-Bold",
        fontSize=8.5,
        leading=12,
        textColor=C_DARK,
    )

    # ── helpers ───────────────────────────────────────────────────────────────
    def _cents_display(cents):
        return f"€{cents / 100:.2f}" if cents else "-"

    def _fmt_date(dt):
        return dt.strftime("%-d %B %Y") if dt else "-"

    def _rule():
        return HRFlowable(
            width="100%", thickness=0.5, color=C_RULE, spaceAfter=4, spaceBefore=10,
        )

    def _section(title, *paragraphs):
        """Return a KeepTogether block: rule + heading + first paragraph, then remaining."""
        head = [_rule(), Paragraph(title.upper(), sec_heading)]
        if paragraphs:
            head.append(Paragraph(paragraphs[0], body_style))
        items = [KeepTogether(head)]
        for text in paragraphs[1:]:
            items.append(Paragraph(text, body_style))
        return items

    # ── data ──────────────────────────────────────────────────────────────────
    payment = getattr(application, "payment", None)
    cell = application.cell

    if cell.is_centre:
        placement_label = "Central Sponsor of the Month"
    elif application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        placement_label = f"Weekly Ring Sponsor Slot — Ring {cell.ring}, Cell #{cell.cell_number}"
    else:
        placement_label = f"Annual Ring Sponsor Slot — Ring {cell.ring}, Cell #{cell.cell_number}"

    if application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        term_label = "Weekly — 7 calendar days from activation"
        net_label  = f"{_cents_display(application.price_net_cents)} EUR per week"
    elif application.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY:
        term_label = "Monthly — 30 calendar days from activation"
        net_label  = f"{_cents_display(application.price_net_cents)} EUR per month"
    else:
        term_label = "Annual — 12 months from activation"
        net_label  = f"{_cents_display(application.price_net_cents)} EUR per year"

    activation_str  = _fmt_date(application.published_at)
    end_str         = _fmt_date(application.expires_at)
    terms_date_str  = _fmt_date(application.terms_accepted_at)

    summary_rows = [
        ["Reference",       application.contract_reference],
        ["Application ID",  str(application.reference)],
        ["Sponsor",         application.sponsor_name],
        ["Contact",         application.contact_name],
        ["Email",           application.email],
    ]
    if application.website_url:
        summary_rows.append(["Website / Profile", application.website_url])
    summary_rows += [
        ["Sponsor slot",    placement_label],
        ["Service term",    term_label],
        ["Net amount",      net_label],
    ]
    if payment and payment.vat_amount_cents:
        summary_rows.append(["VAT", f"{payment.vat_amount_cents} cents (reported by Stripe at checkout)"])
    if payment and payment.total_amount_cents:
        summary_rows.append(["Total paid", f"{payment.total_amount_cents} cents (reported by Stripe at checkout)"])
    summary_rows += [
        ["Activation date", activation_str],
        ["End date",        end_str],
    ]

    table_data = [
        [Paragraph(r[0], t_label), Paragraph(r[1], t_value)]
        for r in summary_rows
    ]
    nrows = len(table_data)
    row_bgs = []
    for i in range(nrows):
        bg = C_ROW_A if i % 2 == 0 else colors.white
        row_bgs += [("BACKGROUND", (0, i), (-1, i), bg)]
    summary_table = Table(table_data, colWidths=[52 * mm, TEXT_W - 52 * mm])
    summary_table.setStyle(TableStyle([
        ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING",    (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING",   (0, 0), (-1, -1), 7),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 7),
        ("BOX",           (0, 0), (-1, -1), 0.5, C_RULE),
        ("LINEBELOW",     (0, 0), (-1, -2), 0.3, C_RULE),
    ] + row_bgs))

    # ── title banner ──────────────────────────────────────────────────────────
    banner_inner = Table(
        [
            [Paragraph("CulinEire Sponsor Agreement", title_style)],
            [Paragraph(f"Reference: {application.contract_reference}", ref_style)],
        ],
        colWidths=[TEXT_W],
    )
    banner_inner.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), C_BRAND),
        ("TOPPADDING",    (0, 0), (-1, 0),  14),
        ("BOTTOMPADDING", (0, 0), (-1, 0),  4),
        ("TOPPADDING",    (0, 1), (-1, 1),  2),
        ("BOTTOMPADDING", (0, 1), (-1, 1),  14),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 12),
    ]))

    # ── story ─────────────────────────────────────────────────────────────────
    if cell.is_centre:
        service_slot = "a Central Sponsor of the Month placement"
    elif application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        service_slot = f"a Weekly Ring Sponsor Slot at Ring {cell.ring}, Cell #{cell.cell_number}"
    else:
        service_slot = f"an Annual Ring Sponsor Slot at Ring {cell.ring}, Cell #{cell.cell_number}"

    if application.product_type == SponsorCell.ProductType.WEEKLY_RING:
        renewal_note  = "This is a one-time weekly placement with no automatic renewal."
        duration_note = "7 calendar days from the activation date stated above"
    elif application.product_type == SponsorCell.ProductType.CENTRAL_MONTHLY:
        renewal_note  = "This is a one-time monthly placement with no automatic renewal."
        duration_note = "30 calendar days from the activation date stated above"
    else:
        renewal_note  = "This is a one-year annual placement with no automatic renewal."
        duration_note = "12 months from the activation date stated above"

    story = [
        banner_inner,
        Spacer(1, 5 * mm),
        Paragraph("AGREEMENT SUMMARY", sum_heading),
        summary_table,
        Spacer(1, 2 * mm),
    ]

    story += _section(
        "Parties",
        "<b>Service provider:</b> Bearcave Limited, Company No. 658124, 2 The Fairways, Tir Cluain, "
        "Midleton, Co. Cork, P25 W8W3, Ireland. Trading as CulinEire (Business Name No. 786815). "
        "VAT number: IE3645402WH.",
        f"<b>Client / Sponsor:</b> {application.sponsor_name}, {application.contact_name}, {application.email}",
    )
    story += _section(
        "Service",
        f"Bearcave Limited has approved and activated {service_slot} on the CulinEire Sponsor Puzzle. "
        f"The sponsor logo or avatar will be displayed on the CulinEire website for {duration_note}, "
        f"subject to the terms below. {renewal_note}",
    )
    story += _section(
        "Payment and VAT",
        "The net sponsor fee is quoted exclusive of VAT. VAT was calculated at Stripe Checkout where "
        "applicable. Payment reserved the selected sponsor spot for review only. Payment did not guarantee "
        "approval, publication or activation. The sponsorship term starts from the activation date confirmed "
        "above. There is no automatic renewal for this placement.",
    )
    story += _section(
        "Approval Before Publication",
        "All sponsorship applications are subject to review and approval by Bearcave Limited. Payment does "
        "not guarantee acceptance, approval, publication or activation of a sponsor slot. Bearcave Limited "
        "may refuse, delay, cancel, suspend or reject a sponsorship application where legal, payment, "
        "compliance, sanctions, fraud, content, reputational, technical or policy concerns arise. A paid "
        "sponsor spot is not published automatically. The submitted logo or avatar becomes visible only "
        "after Bearcave Limited approves and publishes it.",
    )
    story += _section(
        "Sponsor Materials Licence",
        "The sponsor confirms they have the right to use the submitted logo, avatar, website or profile "
        "link and related materials. The sponsor grants Bearcave Limited a non-exclusive licence to display "
        "those materials on CulinEire for the sponsorship term.",
    )
    story += _section(
        "Content Standards",
        "The sponsor must not use the sponsorship slot to promote unlawful goods or services, defamatory "
        "content, misleading claims, infringing materials or anything that violates Irish or EU law. The "
        "sponsor must not imply editorial endorsement by CulinEire or Bearcave Limited unless expressly "
        "agreed in writing.",
    )
    story += _section(
        "No Guarantee of Results",
        "Bearcave Limited does not guarantee any particular level of traffic, impressions, clicks or "
        "commercial results from the sponsorship placement.",
    )
    story += _section(
        "Website Changes and Availability",
        "CulinEire is provided on a best-efforts basis. Bearcave Limited may update the website design, "
        "layout or features at any time without affecting the sponsor’s right to display their approved "
        "logo or avatar for the agreed term, except where required by law, safety or compliance obligations.",
    )
    story += _section(
        "Refunds and Compliance",
        "If Bearcave Limited declines a paid placement before publication, the application enters the "
        "refund-required workflow and Bearcave Limited will process a refund through Stripe. Once a sponsor "
        "image has been published, refunds are not guaranteed unless required by applicable law or agreed "
        "in writing by Bearcave Limited. Bearcave Limited may suspend, cancel or remove a sponsorship "
        "placement where compliance, sanctions, legal or policy concerns arise.",
    )
    story += _section(
        "Sanctions and Compliance Declaration",
        "By submitting the sponsor application, the sponsor confirmed that, to the best of their knowledge, "
        "neither the sponsor, nor the company or organisation represented, nor any relevant owner, director, "
        "beneficial owner or controlling person, is subject to EU, UN, Irish or other applicable financial "
        "sanctions. The applicant also confirmed that they are not applying for sponsorship on behalf of, "
        "for the benefit of, or under the control of any sanctioned person, entity or body. Bearcave Limited "
        "cannot accept sponsorship from persons or entities subject to applicable sanctions, asset freezes "
        "or restrictive measures.",
    )
    story += _section(
        "Governing Law",
        "This agreement is governed by the laws of Ireland. Any disputes are subject to the exclusive "
        "jurisdiction of the Irish courts, without prejudice to any statutory rights that may apply under "
        "Irish or EU law.",
    )
    story += _section(
        "Electronic Acceptance",
        f"This agreement was entered into electronically when the sponsor submitted their application and "
        f"accepted the CulinEire sponsorship terms via the website on {terms_date_str}. This document is "
        f"the provider copy issued on behalf of Bearcave Limited upon activation of the sponsorship.",
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=L_MARGIN,
        rightMargin=R_MARGIN,
        topMargin=T_MARGIN,
        bottomMargin=B_MARGIN,
        title=f"CulinEire Sponsor Agreement {application.contract_reference}",
        author="Bearcave Limited",
    )
    doc.build(story, onFirstPage=_draw_page, onLaterPages=_draw_page)
    return buf.getvalue()


def _send_contract_email(application: SponsorApplication) -> str:
    """Generate contract PDF and send short agreement email with PDF attached.

    Returns the PDF filename used as the attachment name.
    Raises on any failure so the caller can record the failure status.
    """
    from django.conf import settings
    from django.core.mail import EmailMultiAlternatives
    from django.template.loader import render_to_string
    from config.email_utils import build_absolute_url, sanitize_email_subject

    payment = getattr(application, "payment", None)
    template = _select_agreement_template(application.product_type)
    pdf_filename = f"CulinEire_Sponsor_Agreement_{application.contract_reference}.pdf"
    pdf_bytes = generate_contract_pdf(application)

    site_url = build_absolute_url("")
    email_context = {
        "application": application,
        "payment": payment,
        "contract_reference": application.contract_reference,
        "activation_date": application.published_at,
        "end_date": application.expires_at,
        "site_url": site_url,
    }
    subject = sanitize_email_subject(
        f"CulinEire Sponsor Agreement — {application.contract_reference}"
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
    msg.attach(pdf_filename, pdf_bytes, "application/pdf")
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
