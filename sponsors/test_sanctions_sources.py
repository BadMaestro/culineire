from datetime import timedelta
from unittest.mock import patch
from urllib.error import HTTPError

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import SanctionsSourceSnapshot, SanctionsSubject, SponsorApplication, SponsorCell, SponsorComplianceCheck, SponsorPayment
from .sanctions_sources import source_is_stale
from .tests import SPONSOR_TEST_SETTINGS, png_upload


EU_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<export>
  <sanctionEntity euReferenceNumber="EU.123" subjectType="person">
    <nameAlias wholeName="Example Person" />
    <nameAlias wholeName="E Person" />
    <birthdate>1970-01-01</birthdate>
    <countryDescription>Ireland</countryDescription>
    <programme>Example regime</programme>
    <regulationSummary>Asset freeze</regulationSummary>
  </sanctionEntity>
</export>
"""
EU_CSV = b"""euReferenceNumber,wholeName,subjectType,countryDescription,birthdate,programme,regulationSummary
EU.456,CSV Entity Ltd,entity,Ireland,,CSV regime,Asset freeze
"""


UN_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<CONSOLIDATED_LIST>
  <INDIVIDUALS>
    <INDIVIDUAL>
      <REFERENCE_NUMBER>UNi.001</REFERENCE_NUMBER>
      <FIRST_NAME>United</FIRST_NAME>
      <SECOND_NAME>Person</SECOND_NAME>
      <UN_LIST_TYPE>Example list</UN_LIST_TYPE>
      <INDIVIDUAL_ALIAS><ALIAS_NAME>U Person</ALIAS_NAME></INDIVIDUAL_ALIAS>
      <INDIVIDUAL_DATE_OF_BIRTH><DATE>1980-02-02</DATE></INDIVIDUAL_DATE_OF_BIRTH>
      <NATIONALITY><VALUE>IE</VALUE></NATIONALITY>
      <COMMENTS1>Example comment</COMMENTS1>
    </INDIVIDUAL>
  </INDIVIDUALS>
  <ENTITIES>
    <ENTITY>
      <REFERENCE_NUMBER>UNe.001</REFERENCE_NUMBER>
      <FIRST_NAME>United Entity Ltd</FIRST_NAME>
      <ENTITY_ALIAS><ALIAS_NAME>UE Ltd</ALIAS_NAME></ENTITY_ALIAS>
    </ENTITY>
  </ENTITIES>
</CONSOLIDATED_LIST>
"""


class MockHTTPResponse:
    def __init__(self, payload, content_type="application/xml"):
        self.payload = payload
        self.headers = {
            "ETag": '"test"',
            "Last-Modified": "Sat, 06 Jun 2026 00:00:00 GMT",
            "Content-Type": content_type,
        }

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.payload


@override_settings(**SPONSOR_TEST_SETTINGS)
class SanctionsSourceUpdateTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user("source-staff", password="pass", is_staff=True)

    @patch("sponsors.sanctions_sources.urlopen", return_value=MockHTTPResponse(EU_XML))
    def test_successful_eu_update_creates_snapshot_and_subject(self, _urlopen):
        call_command("update_sanctions_sources", source="eu")

        snapshot = SanctionsSourceSnapshot.objects.get(source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF)
        subject = SanctionsSubject.objects.get(source_snapshot=snapshot)
        self.assertEqual(snapshot.status, SanctionsSourceSnapshot.Status.SUCCESS)
        self.assertEqual(snapshot.record_count, 1)
        self.assertEqual(subject.primary_name, "Example Person")
        self.assertEqual(subject.normalised_name, "example person")
        self.assertIn("E Person", subject.aliases)

    @patch("sponsors.sanctions_sources.urlopen")
    def test_eu_primary_403_tries_official_fallback_url(self, mock_urlopen):
        mock_urlopen.side_effect = [
            HTTPError("https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content", 403, "Forbidden", {}, None),
            MockHTTPResponse(EU_XML),
        ]

        call_command("update_sanctions_sources", source="eu")

        snapshot = SanctionsSourceSnapshot.objects.get(source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF)
        self.assertEqual(snapshot.status, SanctionsSourceSnapshot.Status.SUCCESS)
        self.assertEqual(snapshot.record_count, 1)
        self.assertEqual(mock_urlopen.call_count, 2)

    @patch("sponsors.sanctions_sources.urlopen")
    def test_eu_csv_fallback_works_when_xml_unavailable(self, mock_urlopen):
        mock_urlopen.side_effect = [
            HTTPError("https://webgate.ec.europa.eu/europeaid/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content", 403, "Forbidden", {}, None),
            HTTPError("https://webgate.ec.europa.eu/fsd/fsf/public/files/xmlFullSanctionsList_1_1/content", 403, "Forbidden", {}, None),
            MockHTTPResponse(EU_CSV, content_type="text/csv"),
        ]

        call_command("update_sanctions_sources", source="eu")

        snapshot = SanctionsSourceSnapshot.objects.get(source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF)
        subject = SanctionsSubject.objects.get(source_snapshot=snapshot)
        self.assertEqual(snapshot.file_format, "csv")
        self.assertEqual(subject.primary_name, "CSV Entity Ltd")
        self.assertEqual(subject.subject_type, SanctionsSubject.SubjectType.ENTITY)

    @patch("sponsors.sanctions_sources.urlopen", return_value=MockHTTPResponse(b"<html>Forbidden</html>", content_type="text/html"))
    def test_html_error_response_is_recorded_as_failure(self, _urlopen):
        with self.assertRaises(Exception):
            call_command("update_sanctions_sources", source="eu")

        snapshot = SanctionsSourceSnapshot.objects.get(source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF)
        self.assertEqual(snapshot.status, SanctionsSourceSnapshot.Status.FAILED)
        self.assertIn("HTML error page", snapshot.error_message)

    @patch("sponsors.sanctions_sources.urlopen", return_value=MockHTTPResponse(UN_XML))
    def test_successful_un_update_creates_snapshot_and_subjects(self, _urlopen):
        call_command("update_sanctions_sources", source="un")

        snapshot = SanctionsSourceSnapshot.objects.get(source_code=SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED)
        self.assertEqual(snapshot.status, SanctionsSourceSnapshot.Status.SUCCESS)
        self.assertEqual(snapshot.record_count, 2)
        self.assertTrue(SanctionsSubject.objects.filter(primary_name="United Person").exists())
        self.assertTrue(SanctionsSubject.objects.filter(primary_name="United Entity Ltd").exists())

    @patch("sponsors.sanctions_sources.urlopen")
    def test_allow_partial_succeeds_when_eu_fails_and_un_succeeds(self, mock_urlopen):
        mock_urlopen.side_effect = [
            OSError("eu down"),
            OSError("eu fallback down"),
            OSError("eu csv down"),
            MockHTTPResponse(UN_XML),
        ]

        call_command("update_sanctions_sources", source="all", allow_partial=True)

        self.assertTrue(SanctionsSourceSnapshot.objects.filter(source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF, status=SanctionsSourceSnapshot.Status.FAILED).exists())
        self.assertTrue(SanctionsSourceSnapshot.objects.filter(source_code=SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED, status=SanctionsSourceSnapshot.Status.SUCCESS).exists())

    @patch("sponsors.sanctions_sources.urlopen", side_effect=OSError("all down"))
    def test_allow_partial_raises_when_all_requested_sources_fail(self, _urlopen):
        with self.assertRaises(Exception):
            call_command("update_sanctions_sources", source="all", allow_partial=True)

    @patch("sponsors.sanctions_sources.urlopen", side_effect=OSError("network down"))
    def test_failed_fetch_does_not_delete_latest_successful_snapshot(self, _urlopen):
        successful = SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            source_name="EU Financial Sanctions Files",
            source_url="https://example.test/eu.xml",
            fetched_at=timezone.now(),
            source_sha256="abc",
            record_count=1,
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )

        with self.assertRaises(Exception):
            call_command("update_sanctions_sources", source="eu")

        self.assertTrue(SanctionsSourceSnapshot.objects.filter(pk=successful.pk).exists())
        self.assertTrue(SanctionsSourceSnapshot.objects.filter(status=SanctionsSourceSnapshot.Status.FAILED).exists())

    @patch("sponsors.sanctions_sources.urlopen", return_value=MockHTTPResponse(EU_XML))
    def test_same_sha_without_force_records_skipped_not_modified(self, _urlopen):
        call_command("update_sanctions_sources", source="eu")
        call_command("update_sanctions_sources", source="eu")

        self.assertEqual(SanctionsSourceSnapshot.objects.filter(status=SanctionsSourceSnapshot.Status.SUCCESS).count(), 1)
        self.assertEqual(SanctionsSourceSnapshot.objects.filter(status=SanctionsSourceSnapshot.Status.SKIPPED_NOT_MODIFIED).count(), 1)
        self.assertEqual(SanctionsSubject.objects.count(), 1)

    def test_staleness_helper_detects_old_or_missing_successful_update(self):
        self.assertTrue(source_is_stale(SanctionsSourceSnapshot.SourceCode.EU_FSF))
        SanctionsSourceSnapshot.objects.create(
            source_code=SanctionsSourceSnapshot.SourceCode.EU_FSF,
            source_name="EU Financial Sanctions Files",
            source_url="https://example.test/eu.xml",
            fetched_at=timezone.now() - timedelta(hours=72),
            status=SanctionsSourceSnapshot.Status.SUCCESS,
        )
        self.assertTrue(source_is_stale(SanctionsSourceSnapshot.SourceCode.EU_FSF))

    def test_source_status_view_is_staff_only(self):
        response = self.client.get(reverse("sponsors:sanctions_source_status"))
        self.assertEqual(response.status_code, 404)

        self.client.force_login(self.staff)
        response = self.client.get(reverse("sponsors:sanctions_source_status"))
        self.assertContains(response, "Official Sanctions Source Status")
        self.assertContains(response, "stale or unavailable")

    def test_sponsor_moderation_detail_warns_when_sources_missing(self):
        cell = SponsorCell.objects.create(cell_number=250, ring=6, position_in_ring=0)
        application = SponsorApplication.objects.create(
            cell=cell,
            status=SponsorApplication.Status.PAID_PENDING_COMPLIANCE_REVIEW,
            sponsor_name="Review Sponsor",
            contact_name="Contact",
            email="review@example.com",
            logo=png_upload("review.png"),
            price_net_cents=cell.price_net_cents,
        )
        SponsorPayment.objects.create(application=application, status=SponsorPayment.Status.PAID)
        SponsorComplianceCheck.objects.create(application=application, status=SponsorComplianceCheck.Status.SCREENING_REQUIRED)
        self.client.force_login(self.staff)

        response = self.client.get(reverse("sponsors:moderation_application_detail", args=[application.pk]))

        self.assertContains(response, "Official sanctions source data is stale or unavailable")
