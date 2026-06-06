from __future__ import annotations

import re
from datetime import timedelta
from difflib import SequenceMatcher
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

from .models import SanctionsEntry, SponsorAuditLog, SponsorComplianceCheck


ALLOWED_STATUSES = {
    SponsorComplianceCheck.Status.CLEAR,
    SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED,
}


def normalize_name(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", (value or "").casefold()))


def latest_compliance_check(application):
    return application.compliance_checks.order_by("-created_at").first()


def compliance_allows_progress(application) -> bool:
    check = latest_compliance_check(application)
    if not check:
        return False
    if check.status == SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED:
        return True
    max_age_hours = getattr(settings, "SPONSOR_SANCTIONS_MAX_AGE_HOURS", 48)
    return bool(
        check.status == SponsorComplianceCheck.Status.CLEAR
        and check.checked_at
        and check.checked_at >= timezone.now() - timedelta(hours=max_age_hours)
    )


def _audit(check, actor=None):
    actions = {
        SponsorComplianceCheck.Status.CLEAR: SponsorAuditLog.Action.COMPLIANCE_CHECK_CLEAR,
        SponsorComplianceCheck.Status.POSSIBLE_MATCH: SponsorAuditLog.Action.COMPLIANCE_POSSIBLE_MATCH,
        SponsorComplianceCheck.Status.CONFIRMED_MATCH: SponsorAuditLog.Action.COMPLIANCE_BLOCKED,
        SponsorComplianceCheck.Status.BLOCKED: SponsorAuditLog.Action.COMPLIANCE_BLOCKED,
        SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED: SponsorAuditLog.Action.COMPLIANCE_FALSE_POSITIVE_CLEARED,
        SponsorComplianceCheck.Status.ERROR: SponsorAuditLog.Action.COMPLIANCE_ERROR,
    }
    from .services import record_audit
    record_audit(
        action=actions.get(check.status, SponsorAuditLog.Action.COMPLIANCE_ERROR),
        application=check.application,
        actor=actor,
        to_status=check.status,
        notes=check.staff_notes or check.source_summary,
        metadata={"matched_name": check.matched_name, "matched_source": check.matched_source},
    )


def run_compliance_check(application, actor=None):
    now = timezone.now()
    entries = SanctionsEntry.objects.filter(active=True)
    max_age_hours = getattr(settings, "SPONSOR_SANCTIONS_MAX_AGE_HOURS", 48)
    fresh_entries = entries.filter(updated_at__gte=now - timedelta(hours=max_age_hours))
    if not fresh_entries.exists():
        status = (
            SponsorComplianceCheck.Status.CLEAR
            if getattr(settings, "SPONSOR_COMPLIANCE_ALLOW_EMPTY_DATA", False)
            else SponsorComplianceCheck.Status.ERROR
        )
        check = SponsorComplianceCheck.objects.create(
            application=application,
            status=status,
            checked_at=now,
            source_summary="No current sanctions data is available." if status == SponsorComplianceCheck.Status.ERROR else "Test-mode empty sanctions dataset.",
            checked_payload={"sponsor_name": application.sponsor_name, "contact_name": application.contact_name},
        )
        _audit(check, actor)
        return check

    candidates = [
        application.sponsor_name,
        application.contact_name,
        urlparse(application.website_url).hostname or "",
        application.email.rsplit("@", 1)[-1] if "@" in application.email else "",
    ]
    normalized_candidates = [normalize_name(value) for value in candidates if normalize_name(value)]
    matches = []
    for entry in fresh_entries:
        for listed_name in [entry.name, *entry.aliases]:
            normalized_listed = normalize_name(listed_name)
            if not normalized_listed:
                continue
            score = max(SequenceMatcher(None, candidate, normalized_listed).ratio() for candidate in normalized_candidates)
            if score >= 0.82:
                matches.append({"name": listed_name, "source": entry.source, "score": round(score, 4)})
    best = max(matches, key=lambda match: match["score"], default=None)
    status = SponsorComplianceCheck.Status.POSSIBLE_MATCH if best else SponsorComplianceCheck.Status.CLEAR
    check = SponsorComplianceCheck.objects.create(
        application=application,
        status=status,
        checked_at=now,
        source_summary=f"Screened against {fresh_entries.count()} current cached sanctions entries.",
        matched_name=best["name"] if best else "",
        matched_source=best["source"] if best else "",
        match_score=best["score"] if best else None,
        checked_payload={"sponsor_name": application.sponsor_name, "contact_name": application.contact_name},
        raw_matches=matches,
    )
    _audit(check, actor)
    return check


def staff_set_compliance_status(application, status, actor, note):
    note = (note or "").strip()
    if not getattr(actor, "is_staff", False):
        raise ValueError("Staff access is required.")
    if not note:
        raise ValueError("A staff note is required for compliance decisions.")
    if status not in {
        SponsorComplianceCheck.Status.FALSE_POSITIVE_CLEARED,
        SponsorComplianceCheck.Status.CONFIRMED_MATCH,
        SponsorComplianceCheck.Status.BLOCKED,
        SponsorComplianceCheck.Status.POSSIBLE_MATCH,
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
    _audit(check, actor)
    return check
