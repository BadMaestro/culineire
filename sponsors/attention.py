from __future__ import annotations

from django.db import DatabaseError

from .models import SponsorApplication


ATTENTION_STATUSES = {
    SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
    SponsorApplication.Status.PAID_PENDING_APPROVAL,
    SponsorApplication.Status.CHANGES_REQUESTED,
    SponsorApplication.Status.REFUND_REQUIRED,
}


def get_sponsor_moderation_attention_count() -> int:
    try:
        return SponsorApplication.objects.filter(status__in=ATTENTION_STATUSES).count()
    except DatabaseError:
        return 0


def get_sponsor_moderation_attention_breakdown() -> dict[str, int]:
    try:
        return {
            "paid_pending_compliance_review": SponsorApplication.objects.filter(
                status=SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            ).count(),
            "paid_pending_approval": SponsorApplication.objects.filter(
                status=SponsorApplication.Status.PAID_PENDING_APPROVAL,
            ).count(),
            "changes_requested": SponsorApplication.objects.filter(
                status=SponsorApplication.Status.CHANGES_REQUESTED,
            ).count(),
            "refund_required": SponsorApplication.objects.filter(
                status=SponsorApplication.Status.REFUND_REQUIRED,
            ).count(),
        }
    except DatabaseError:
        return {
            "paid_pending_compliance_review": 0,
            "paid_pending_approval": 0,
            "changes_requested": 0,
            "refund_required": 0,
        }
