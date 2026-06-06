from __future__ import annotations

import re
from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from .models import SanctionsSourceSnapshot, SanctionsSubject, SponsorApplication, SponsorAuditLog, SponsorComplianceCheck, SponsorSanctionsMatch
from .sanctions_sources import latest_successful_snapshot, normalise_name


COMPANY_SUFFIXES = {
    "co",
    "company",
    "corp",
    "corporation",
    "inc",
    "incorporated",
    "limited",
    "llc",
    "ltd",
    "plc",
}
GENERIC_TOKENS = {
    "and",
    "association",
    "business",
    "community",
    "group",
    "holding",
    "holdings",
    "international",
    "ireland",
    "irish",
    "limited",
    "services",
    "the",
    "trust",
}
MIN_MATCH_SCORE = 80


@dataclass(frozen=True)
class ScreeningResult:
    subjects_checked: int
    possible_matches_count: int
    source_snapshot_ids: list[int]


def _strip_company_suffixes(value: str) -> str:
    tokens = [token for token in normalise_name(value).split() if token not in COMPANY_SUFFIXES]
    return " ".join(tokens)


def _significant_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"\s+", _strip_company_suffixes(value))
        if len(token) >= 3 and token not in GENERIC_TOKENS
    }


def _screening_values(application: SponsorApplication) -> dict[str, str]:
    values = {
        "sponsor_name": application.sponsor_name or "",
        "contact_name": application.contact_name or "",
    }
    if application.website_url:
        values["website_url"] = application.website_url
    return {key: value.strip() for key, value in values.items() if value and len(value.strip()) >= 3}


def _subject_names(subject: SanctionsSubject) -> list[tuple[str, str]]:
    names = [("primary_name", subject.primary_name)]
    for alias in subject.aliases or []:
        if isinstance(alias, str) and alias.strip():
            names.append(("alias", alias.strip()))
    return names


def _score_name(candidate: str, subject_name: str, *, is_alias: bool) -> tuple[int, list[str]]:
    candidate_norm = normalise_name(candidate)
    subject_norm = normalise_name(subject_name)
    if not candidate_norm or not subject_norm:
        return 0, []
    if len(candidate_norm) < 5 or len(subject_norm) < 5:
        return 0, []
    if candidate_norm == subject_norm:
        return (95 if is_alias else 100), ["alias exact normalised match" if is_alias else "exact normalised name match"]

    candidate_company = _strip_company_suffixes(candidate_norm)
    subject_company = _strip_company_suffixes(subject_norm)
    if candidate_company and candidate_company == subject_company and len(candidate_company) >= 5:
        return 95, ["exact normalised company name match after suffix removal"]

    candidate_tokens = _significant_tokens(candidate_norm)
    subject_tokens = _significant_tokens(subject_norm)
    if len(candidate_tokens) >= 2 and candidate_tokens == subject_tokens:
        return 80, ["strong token match"]
    if len(candidate_tokens) >= 2 and candidate_tokens.issubset(subject_tokens):
        return 80, ["all sponsor significant tokens found in sanctions subject name"]
    return 0, []


def _best_subject_match(application: SponsorApplication, subject: SanctionsSubject):
    sponsor_values = _screening_values(application)
    best = None
    for sponsor_field, sponsor_value in sponsor_values.items():
        if sponsor_field == "website_url":
            continue
        for subject_field, subject_name in _subject_names(subject):
            score, reasons = _score_name(sponsor_value, subject_name, is_alias=subject_field == "alias")
            if score >= MIN_MATCH_SCORE and (best is None or score > best["score"]):
                best = {
                    "score": score,
                    "reasons": reasons,
                    "matched_fields": [sponsor_field, subject_field],
                    "sponsor_values": sponsor_values,
                    "subject_values": {
                        "primary_name": subject.primary_name,
                        "matched_name": subject_name,
                        "aliases": subject.aliases,
                        "countries": subject.countries,
                        "identifiers": subject.identifiers,
                    },
                }
    return best


def latest_successful_source_snapshot_ids() -> list[int]:
    snapshot_ids = []
    for source_code in (SanctionsSourceSnapshot.SourceCode.EU_FSF, SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED):
        snapshot = latest_successful_snapshot(source_code)
        if snapshot:
            snapshot_ids.append(snapshot.pk)
    return snapshot_ids


def screen_sponsor_application(application: SponsorApplication, *, force=False, dry_run=False) -> ScreeningResult:
    snapshot_ids = latest_successful_source_snapshot_ids()
    if not snapshot_ids:
        return ScreeningResult(subjects_checked=0, possible_matches_count=0, source_snapshot_ids=[])

    subjects = SanctionsSubject.objects.filter(source_snapshot_id__in=snapshot_ids, is_active=True).select_related("source_snapshot")
    subjects_checked = 0
    possible_matches = []
    for subject in subjects.iterator(chunk_size=500):
        subjects_checked += 1
        match = _best_subject_match(application, subject)
        if match:
            possible_matches.append((subject, match))

    if dry_run:
        return ScreeningResult(subjects_checked=subjects_checked, possible_matches_count=len(possible_matches), source_snapshot_ids=snapshot_ids)

    with transaction.atomic():
        created_count = 0
        for subject, match in possible_matches:
            existing = SponsorSanctionsMatch.objects.filter(application=application, subject=subject).first()
            if existing and existing.match_status != SponsorSanctionsMatch.Status.POSSIBLE:
                continue
            defaults = {
                "source_code": subject.source_code,
                "source_snapshot": subject.source_snapshot,
                "match_status": SponsorSanctionsMatch.Status.POSSIBLE,
                "match_score": match["score"],
                "match_reasons": match["reasons"],
                "matched_fields": match["matched_fields"],
                "sponsor_values": match["sponsor_values"],
                "subject_values": match["subject_values"],
            }
            if existing:
                if force:
                    for key, value in defaults.items():
                        setattr(existing, key, value)
                    existing.save(update_fields=[*defaults.keys(), "updated_at"])
            else:
                SponsorSanctionsMatch.objects.create(application=application, subject=subject, **defaults)
                created_count += 1

        if created_count:
            from .services import record_audit
            record_audit(
                action=SponsorAuditLog.Action.SANCTIONS_POSSIBLE_MATCH_CREATED,
                application=application,
                notes=f"{created_count} possible sanctions match(es) created.",
                metadata={"created_count": created_count, "source_snapshot_ids": snapshot_ids},
            )

        summary = (
            f"Sanctions screening completed. Subjects checked: {subjects_checked}. "
            f"Possible matches: {len(possible_matches)}."
        )
        SponsorComplianceCheck.objects.create(
            application=application,
            status=SponsorComplianceCheck.Status.SCREENING_REQUIRED,
            checked_at=timezone.now(),
            source_summary=summary,
            checked_payload={"source_snapshot_ids": snapshot_ids, "possible_matches_count": len(possible_matches)},
        )
        from .services import record_audit
        record_audit(
            action=SponsorAuditLog.Action.SANCTIONS_SCREENING_COMPLETED,
            application=application,
            notes=summary,
            metadata={"subjects_checked": subjects_checked, "possible_matches_count": len(possible_matches), "source_snapshot_ids": snapshot_ids},
        )
    return ScreeningResult(subjects_checked=subjects_checked, possible_matches_count=len(possible_matches), source_snapshot_ids=snapshot_ids)


def unresolved_sanctions_matches(application: SponsorApplication):
    return application.sanctions_matches.filter(match_status=SponsorSanctionsMatch.Status.POSSIBLE)


def has_unresolved_sanctions_matches(application: SponsorApplication) -> bool:
    return unresolved_sanctions_matches(application).exists()


def has_blocked_sanctions_match(application: SponsorApplication) -> bool:
    return application.sanctions_matches.filter(match_status=SponsorSanctionsMatch.Status.BLOCKED).exists()


def review_sanctions_match(match: SponsorSanctionsMatch, *, status: str, actor, note: str) -> SponsorSanctionsMatch:
    note = (note or "").strip()
    if not note:
        raise ValueError("A staff note is required for sanctions match review decisions.")
    if status not in {
        SponsorSanctionsMatch.Status.FALSE_POSITIVE,
        SponsorSanctionsMatch.Status.MANUALLY_CLEARED,
        SponsorSanctionsMatch.Status.BLOCKED,
    }:
        raise ValueError("Unsupported sanctions match review decision.")
    match.match_status = status
    match.reviewed_by = actor
    match.reviewed_at = timezone.now()
    match.staff_note = note
    match.save(update_fields=["match_status", "reviewed_by", "reviewed_at", "staff_note", "updated_at"])

    action = {
        SponsorSanctionsMatch.Status.FALSE_POSITIVE: SponsorAuditLog.Action.SANCTIONS_MATCH_FALSE_POSITIVE,
        SponsorSanctionsMatch.Status.MANUALLY_CLEARED: SponsorAuditLog.Action.SANCTIONS_MATCH_MANUALLY_CLEARED,
        SponsorSanctionsMatch.Status.BLOCKED: SponsorAuditLog.Action.SANCTIONS_MATCH_BLOCKED,
    }[status]
    if status == SponsorSanctionsMatch.Status.BLOCKED:
        SponsorComplianceCheck.objects.create(
            application=match.application,
            status=SponsorComplianceCheck.Status.BLOCKED,
            checked_at=timezone.now(),
            source_summary="Blocked for compliance after possible sanctions match review.",
            matched_name=match.subject.primary_name,
            matched_source=match.source_code,
            match_score=match.match_score,
            staff_notes=note,
            reviewed_by=actor,
            reviewed_at=timezone.now(),
        )

    from .services import record_audit
    record_audit(
        action=action,
        application=match.application,
        actor=actor,
        to_status=status,
        notes=note,
        metadata={"match_id": match.pk, "subject_id": match.subject_id, "match_score": match.match_score},
    )
    return match
