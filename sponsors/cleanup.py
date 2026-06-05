from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from .models import ProcessedStripeEvent, SponsorApplication, SponsorAuditLog, SponsorCell, SponsorPayment


PROTECTED_APPLICATION_STATUSES = {
    SponsorApplication.Status.PAID_PENDING_APPROVAL,
    SponsorApplication.Status.CHANGES_REQUESTED,
    SponsorApplication.Status.APPROVED,
    SponsorApplication.Status.REFUND_REQUIRED,
    SponsorApplication.Status.REFUNDED,
}

SAFE_CELL_RESET_STATUSES = {
    SponsorCell.Status.AVAILABLE,
    SponsorCell.Status.PAYMENT_PENDING,
    SponsorCell.Status.REJECTED,
    SponsorCell.Status.EXPIRED,
    SponsorCell.Status.RESERVED,
}


@dataclass(frozen=True)
class DeletionAssessment:
    allowed: bool
    reasons: tuple[str, ...]


def assess_safe_unpaid_deletion(application: SponsorApplication) -> DeletionAssessment:
    reasons: list[str] = []
    payment = getattr(application, "payment", None)

    if application.status in PROTECTED_APPLICATION_STATUSES:
        reasons.append(f"protected application status: {application.status}")
    if application.published_at or application.expires_at or application.approved_at:
        reasons.append("application has publication/approval term history")
    if payment:
        if payment.status in {
            SponsorPayment.Status.PAID,
            SponsorPayment.Status.REFUNDED,
            SponsorPayment.Status.PARTIALLY_REFUNDED,
        }:
            reasons.append(f"financial payment status: {payment.status}")
        if payment.stripe_payment_intent_id:
            reasons.append("Stripe PaymentIntent ID exists")
        if payment.stripe_checkout_session_id and payment.status not in {
            SponsorPayment.Status.FAILED,
        }:
            reasons.append("Stripe Checkout Session ID exists without a clearly failed payment")
        if payment.paid_at or payment.refunded_at or payment.total_amount_cents or payment.vat_amount_cents:
            reasons.append("payment contains financial history")
    if application.stripe_events.exists():
        reasons.append("processed Stripe webhook history exists")
    if application.cell.status not in SAFE_CELL_RESET_STATUSES:
        reasons.append(f"cell status is not safely resettable: {application.cell.status}")

    return DeletionAssessment(allowed=not reasons, reasons=tuple(reasons))


def reset_sponsor_cell(cell: SponsorCell) -> None:
    cell.status = SponsorCell.Status.AVAILABLE
    cell.sponsor_name = ""
    cell.sponsor_logo = None
    cell.sponsor_url = ""
    cell.sponsor_tagline = ""
    cell.logo_pending = None
    cell.logo_offset_x = 0.0
    cell.logo_offset_y = 0.0
    cell.logo_scale = 1.0
    cell.logo_rotation = 0.0
    cell.enquiry_name = ""
    cell.enquiry_email = ""
    cell.enquiry_company = ""
    cell.enquiry_website = ""
    cell.enquiry_message = ""
    cell.enquiry_submitted_at = None
    cell.purchased_at = None
    cell.admin_notes = ""
    cell.save()


@transaction.atomic
def delete_application_records(application: SponsorApplication, *, force_cell_reset: bool = False) -> None:
    cell = SponsorCell.objects.select_for_update().get(pk=application.cell_id)
    application = SponsorApplication.objects.select_for_update().get(pk=application.pk)
    SponsorAuditLog.objects.filter(application=application).delete()
    ProcessedStripeEvent.objects.filter(application=application).delete()
    application.delete()

    other_applications_exist = SponsorApplication.objects.filter(cell=cell).exists()
    if force_cell_reset or not other_applications_exist:
        reset_sponsor_cell(cell)
