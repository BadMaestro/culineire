from __future__ import annotations

import hashlib
import csv
import io
import re
import unicodedata
from dataclasses import dataclass
from datetime import timedelta
from email.utils import parsedate_to_datetime
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from django.db import transaction
from django.utils import timezone

from .models import SanctionsSourceSnapshot, SanctionsSubject


PARSER_VERSION = "phase2-xml-v1"
DEFAULT_STALE_AFTER_HOURS = 48
OFFICIAL_SOURCES = {
    "eu": {
        "source_code": SanctionsSourceSnapshot.SourceCode.EU_FSF,
        "source_name": "EU Financial Sanctions Files",
        "source_url": "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
        "fallback_urls": [
            "https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content",
            "https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/csvFullSanctionsList/content",
        ],
    },
    "un": {
        "source_code": SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED,
        "source_name": "UN Security Council Consolidated List",
        "source_url": "https://scsanctions.un.org/resources/xml/en/consolidated.xml",
    },
}
REQUEST_HEADERS = {
    "User-Agent": "CulinEire Compliance Source Updater",
    "Accept": "application/xml,text/xml,text/csv,application/octet-stream,*/*",
}


@dataclass(frozen=True)
class ParsedSubject:
    external_reference: str
    subject_type: str
    primary_name: str
    aliases: list[str]
    countries: list[str]
    dates_of_birth: list[str]
    identifiers: list[str]
    regimes: list[str]
    measures: list[str]
    raw_payload: dict


def normalise_name(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "").casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def latest_successful_snapshot(source_code: str):
    return SanctionsSourceSnapshot.objects.filter(
        source_code=source_code,
        status=SanctionsSourceSnapshot.Status.SUCCESS,
    ).order_by("-fetched_at", "-created_at").first()


def source_is_stale(source_code: str, *, stale_after_hours: int = DEFAULT_STALE_AFTER_HOURS) -> bool:
    snapshot = latest_successful_snapshot(source_code)
    if not snapshot or not snapshot.fetched_at:
        return True
    return snapshot.fetched_at < timezone.now() - timedelta(hours=stale_after_hours)


def source_statuses(*, stale_after_hours: int = DEFAULT_STALE_AFTER_HOURS) -> list[dict]:
    statuses = []
    for config in OFFICIAL_SOURCES.values():
        latest = SanctionsSourceSnapshot.objects.filter(source_code=config["source_code"]).order_by("-created_at").first()
        latest_success = latest_successful_snapshot(config["source_code"])
        stale = not latest_success or source_is_stale(config["source_code"], stale_after_hours=stale_after_hours)
        statuses.append({
            "source_code": config["source_code"],
            "source_name": config["source_name"],
            "latest": latest,
            "latest_success": latest_success,
            "is_stale": stale,
            "record_count": latest_success.record_count if latest_success else 0,
            "last_error": latest.error_message if latest and latest.status == SanctionsSourceSnapshot.Status.FAILED else "",
        })
    return statuses


def sanctions_sources_unavailable_or_stale() -> bool:
    return any(item["is_stale"] for item in source_statuses())


def _text(element, path: str) -> str:
    found = element.find(path)
    return (found.text or "").strip() if found is not None and found.text else ""


def _all_text(element, local_name: str) -> list[str]:
    values = []
    for child in element.iter():
        if child.tag.split("}")[-1].lower() == local_name.lower() and child.text:
            value = child.text.strip()
            if value and value not in values:
                values.append(value)
    return values


def parse_eu_xml(payload: bytes) -> list[ParsedSubject]:
    root = ElementTree.fromstring(payload)
    subjects = []
    for entity in [node for node in root.iter() if node.tag.split("}")[-1] == "sanctionEntity"]:
        names = []
        for name_alias in [node for node in entity.iter() if node.tag.split("}")[-1] == "nameAlias"]:
            whole_name = name_alias.attrib.get("wholeName", "").strip()
            if whole_name and whole_name not in names:
                names.append(whole_name)
        if not names:
            continue
        subject_type = SanctionsSubject.SubjectType.ENTITY if entity.attrib.get("subjectType", "").lower() == "entity" else SanctionsSubject.SubjectType.INDIVIDUAL
        subjects.append(ParsedSubject(
            external_reference=entity.attrib.get("euReferenceNumber", "") or entity.attrib.get("logicalId", ""),
            subject_type=subject_type,
            primary_name=names[0],
            aliases=names[1:],
            countries=_all_text(entity, "countryDescription"),
            dates_of_birth=_all_text(entity, "birthdate"),
            identifiers=_all_text(entity, "number"),
            regimes=_all_text(entity, "programme"),
            measures=_all_text(entity, "regulationSummary"),
            raw_payload={"attributes": dict(entity.attrib), "names": names},
        ))
    return subjects


def parse_eu_csv(payload: bytes) -> list[ParsedSubject]:
    text = payload.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    subjects = []
    for row in reader:
        lowered = {str(key or "").strip().lower(): (value or "").strip() for key, value in row.items()}
        primary_name = (
            lowered.get("wholename")
            or lowered.get("whole name")
            or lowered.get("name")
            or lowered.get("namealias")
            or lowered.get("alias")
            or ""
        )
        if not primary_name:
            continue
        subject_type_value = (lowered.get("subjecttype") or lowered.get("subject type") or "").lower()
        subject_type = SanctionsSubject.SubjectType.ENTITY if "entity" in subject_type_value else SanctionsSubject.SubjectType.INDIVIDUAL
        external_reference = lowered.get("eureferencenumber") or lowered.get("eu reference number") or lowered.get("logicalid") or ""
        countries = [value for key, value in lowered.items() if "country" in key and value]
        dates_of_birth = [value for key, value in lowered.items() if ("birth" in key or "date" in key) and value]
        identifiers = [value for key, value in lowered.items() if ("number" in key or "identifier" in key) and value]
        regimes = [value for key, value in lowered.items() if ("programme" in key or "regime" in key) and value]
        measures = [value for key, value in lowered.items() if ("measure" in key or "regulation" in key) and value]
        subjects.append(ParsedSubject(
            external_reference=external_reference,
            subject_type=subject_type,
            primary_name=primary_name,
            aliases=[],
            countries=list(dict.fromkeys(countries)),
            dates_of_birth=list(dict.fromkeys(dates_of_birth)),
            identifiers=list(dict.fromkeys(identifiers)),
            regimes=list(dict.fromkeys(regimes)),
            measures=list(dict.fromkeys(measures)),
            raw_payload=row,
        ))
    return subjects


def parse_un_xml(payload: bytes) -> list[ParsedSubject]:
    root = ElementTree.fromstring(payload)
    subjects = []
    for tag_name, subject_type in (("INDIVIDUAL", SanctionsSubject.SubjectType.INDIVIDUAL), ("ENTITY", SanctionsSubject.SubjectType.ENTITY)):
        for item in [node for node in root.iter() if node.tag.split("}")[-1] == tag_name]:
            names = []
            for part in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME"):
                value = _text(item, part)
                if value:
                    names.append(value)
            primary_name = " ".join(names).strip() or _text(item, "NAME_ORIGINAL_SCRIPT")
            aliases = _all_text(item, "ALIAS_NAME")
            if not primary_name and aliases:
                primary_name = aliases.pop(0)
            if not primary_name:
                continue
            subjects.append(ParsedSubject(
                external_reference=_text(item, "REFERENCE_NUMBER"),
                subject_type=subject_type,
                primary_name=primary_name,
                aliases=aliases,
                countries=_all_text(item, "NATIONALITY") + _all_text(item, "COUNTRY"),
                dates_of_birth=_all_text(item, "DATE"),
                identifiers=_all_text(item, "NUMBER"),
                regimes=[_text(item, "UN_LIST_TYPE")] if _text(item, "UN_LIST_TYPE") else [],
                measures=[],
                raw_payload={"reference": _text(item, "REFERENCE_NUMBER"), "comments": _text(item, "COMMENTS1")},
            ))
    return subjects


def _looks_like_html(payload: bytes) -> bool:
    sample = payload[:512].lstrip().lower()
    return sample.startswith(b"<!doctype html") or sample.startswith(b"<html") or b"<html" in sample[:128]


def detect_format(payload: bytes, content_type: str = "") -> str:
    if _looks_like_html(payload):
        raise ValueError("Downloaded sanctions source appears to be an HTML error page.")
    sample = payload[:512].lstrip()
    content_type = (content_type or "").lower()
    if sample.startswith(b"<") or "xml" in content_type:
        return "xml"
    if b"," in sample or "csv" in content_type:
        return "csv"
    raise ValueError("Downloaded sanctions source is not recognised as XML or CSV.")


def parse_source(source_key: str, payload: bytes, file_format: str) -> list[ParsedSubject]:
    if source_key == "eu":
        return parse_eu_csv(payload) if file_format == "csv" else parse_eu_xml(payload)
    if file_format != "xml":
        raise ValueError("UN sanctions source must be XML.")
    return parse_un_xml(payload)


def _header_datetime(headers, name: str):
    value = headers.get(name)
    if not value:
        return None
    try:
        parsed = parsedate_to_datetime(value)
        return parsed if timezone.is_aware(parsed) else timezone.make_aware(parsed)
    except (TypeError, ValueError):
        return None


def fetch_source(source_key: str, *, timeout: int) -> tuple[bytes, dict]:
    config = OFFICIAL_SOURCES[source_key]
    urls = [config["source_url"], *config.get("fallback_urls", [])]
    errors = []
    for url in urls:
        request = Request(url, headers=REQUEST_HEADERS)
        try:
            with urlopen(request, timeout=timeout) as response:
                payload = response.read()
                content_type = response.headers.get("Content-Type", "")
                file_format = detect_format(payload, content_type)
                return payload, {
                    "etag": response.headers.get("ETag", ""),
                    "last_modified": _header_datetime(response.headers, "Last-Modified"),
                    "source_url": url,
                    "file_format": file_format,
                }
        except (HTTPError, URLError, TimeoutError, OSError, ValueError) as exc:
            errors.append(f"{url}: {exc}")
            continue
    raise URLError("; ".join(errors))


def update_source(source_key: str, *, dry_run=False, force=False, timeout=30) -> SanctionsSourceSnapshot:
    config = OFFICIAL_SOURCES[source_key]
    now = timezone.now()
    try:
        payload, metadata = fetch_source(source_key, timeout=timeout)
        sha256 = hashlib.sha256(payload).hexdigest()
        latest = latest_successful_snapshot(config["source_code"])
        if latest and latest.source_sha256 == sha256 and not force:
            return SanctionsSourceSnapshot.objects.create(
                source_code=config["source_code"],
                source_name=config["source_name"],
                source_url=metadata.get("source_url", config["source_url"]),
                file_format=metadata.get("file_format", "xml"),
                fetched_at=now,
                source_last_modified_at=metadata.get("last_modified"),
                source_etag=metadata.get("etag", ""),
                source_sha256=sha256,
                record_count=latest.record_count,
                status=SanctionsSourceSnapshot.Status.SKIPPED_NOT_MODIFIED,
                parser_version=PARSER_VERSION,
            )
        file_format = metadata.get("file_format", "xml")
        parsed_subjects = parse_source(source_key, payload, file_format)
        if dry_run:
            return SanctionsSourceSnapshot(
                source_code=config["source_code"],
                source_name=config["source_name"],
                source_url=metadata.get("source_url", config["source_url"]),
                file_format=file_format,
                fetched_at=now,
                source_sha256=sha256,
                record_count=len(parsed_subjects),
                status=SanctionsSourceSnapshot.Status.SUCCESS,
                parser_version=PARSER_VERSION,
            )
        with transaction.atomic():
            snapshot = SanctionsSourceSnapshot.objects.create(
                source_code=config["source_code"],
                source_name=config["source_name"],
                source_url=metadata.get("source_url", config["source_url"]),
                file_format=file_format,
                fetched_at=now,
                source_last_modified_at=metadata.get("last_modified"),
                source_etag=metadata.get("etag", ""),
                source_sha256=sha256,
                record_count=len(parsed_subjects),
                status=SanctionsSourceSnapshot.Status.SUCCESS,
                parser_version=PARSER_VERSION,
            )
            SanctionsSubject.objects.bulk_create([
                SanctionsSubject(
                    source_snapshot=snapshot,
                    source_code=config["source_code"],
                    external_reference=subject.external_reference,
                    subject_type=subject.subject_type,
                    primary_name=subject.primary_name,
                    normalised_name=normalise_name(subject.primary_name),
                    aliases=subject.aliases,
                    countries=subject.countries,
                    dates_of_birth=subject.dates_of_birth,
                    identifiers=subject.identifiers,
                    regimes=subject.regimes,
                    measures=subject.measures,
                    raw_payload=subject.raw_payload,
                )
                for subject in parsed_subjects
            ])
            return snapshot
    except (ElementTree.ParseError, URLError, TimeoutError, OSError, ValueError) as exc:
        return SanctionsSourceSnapshot.objects.create(
            source_code=config["source_code"],
            source_name=config["source_name"],
            source_url=config["source_url"],
            file_format="xml",
            fetched_at=now,
            status=SanctionsSourceSnapshot.Status.FAILED,
            error_message=str(exc)[:2000],
            parser_version=PARSER_VERSION,
        )
