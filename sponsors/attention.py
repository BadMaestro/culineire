from __future__ import annotations

from django.db import DatabaseError

from .models import SponsorApplication, SponsorSanctionsMatch


ATTENTION_STATUSES = {
    SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
    SponsorApplication.Status.PAID_PENDING_APPROVAL,
    SponsorApplication.Status.CHANGES_REQUESTED,
    SponsorApplication.Status.REFUND_REQUIRED,
}


def get_sponsor_moderation_attention_count() -> int:
    try:
        status_count = SponsorApplication.objects.filter(status__in=ATTENTION_STATUSES).count()
        match_count = SponsorApplication.objects.filter(
            sanctions_matches__match_status=SponsorSanctionsMatch.Status.POSSIBLE,
        ).exclude(status__in=ATTENTION_STATUSES).distinct().count()
        blocked_count = SponsorApplication.objects.filter(
            sanctions_matches__match_status=SponsorSanctionsMatch.Status.BLOCKED,
        ).exclude(
            status__in={
                *ATTENTION_STATUSES,
                SponsorApplication.Status.APPROVED,
                SponsorApplication.Status.REJECTED,
                SponsorApplication.Status.REFUNDED,
                SponsorApplication.Status.CANCELLED,
                SponsorApplication.Status.EXPIRED,
            },
        ).distinct().count()
        return status_count + match_count + blocked_count
    except DatabaseError:
        return 0


def get_sponsor_moderation_attention_breakdown() -> dict[str, int]:
    try:
        possible_match = SponsorApplication.objects.filter(
            sanctions_matches__match_status=SponsorSanctionsMatch.Status.POSSIBLE,
        ).distinct().count()
        blocked_compliance = SponsorApplication.objects.filter(
            sanctions_matches__match_status=SponsorSanctionsMatch.Status.BLOCKED,
        ).exclude(
            status__in={
                SponsorApplication.Status.APPROVED,
                SponsorApplication.Status.REJECTED,
                SponsorApplication.Status.REFUNDED,
                SponsorApplication.Status.CANCELLED,
                SponsorApplication.Status.EXPIRED,
            },
        ).distinct().count()
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
            "possible_sanctions_match": possible_match,
            "blocked_compliance": blocked_compliance,
        }
    except DatabaseError:
        return {
            "paid_pending_compliance_review": 0,
            "paid_pending_approval": 0,
            "changes_requested": 0,
            "refund_required": 0,
            "possible_sanctions_match": 0,
            "blocked_compliance": 0,
        }
