from django.utils import timezone

from .models import SponsorAuditLog, SponsorComplianceCheck


ALLOWED_STATUSES = {
    SponsorComplianceCheck.Status.CLEAR,
    SponsorComplianceCheck.Status.MANUALLY_CLEARED,
}


def latest_compliance_check(application):
    return application.compliance_checks.order_by("-created_at").first()


def compliance_allows_progress(application):
    check = latest_compliance_check(application)
    return bool(check and check.status in ALLOWED_STATUSES)


def mark_screening_required(application):
    return SponsorComplianceCheck.objects.create(
        application=application,
        status=SponsorComplianceCheck.Status.SCREENING_REQUIRED,
        source_summary="Payment received. Manual compliance review is required before approval.",
    )


def staff_set_compliance_status(application, status, actor, note):
    note = (note or "").strip()
    if not getattr(actor, "is_staff", False):
        raise ValueError("Staff access is required.")
    if not note:
        raise ValueError("A staff note is required for compliance decisions.")
    if status not in {
        SponsorComplianceCheck.Status.MANUALLY_CLEARED,
        SponsorComplianceCheck.Status.BLOCKED,
        SponsorComplianceCheck.Status.SCREENING_REQUIRED,
    }:
        raise ValueError("Unsupported compliance decision.")
    check = SponsorComplianceCheck.objects.create(
        application=application,
        status=status,
        checked_at=timezone.now(),
        staff_notes=note,
        reviewed_by=actor,
        reviewed_at=timezone.now(),
        source_summary="Manual staff compliance decision.",
    )
    from .services import record_audit
    action = (
        SponsorAuditLog.Action.MANUAL_COMPLIANCE_CLEAR
        if status == SponsorComplianceCheck.Status.MANUALLY_CLEARED
        else SponsorAuditLog.Action.COMPLIANCE_BLOCKED
    )
    record_audit(
        action=action,
        application=application,
        actor=actor,
        to_status=status,
        notes=note,
    )
    return check
