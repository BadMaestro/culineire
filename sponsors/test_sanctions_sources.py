from datetime import timedelta
from unittest.mock import patch

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
    def __init__(self, payload):
        self.payload = payload
        self.headers = {"ETag": '"test"', "Last-Modified": "Sat, 06 Jun 2026 00:00:00 GMT"}

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

    @patch("sponsors.sanctions_sources.urlopen", return_value=MockHTTPResponse(UN_XML))
    def test_successful_un_update_creates_snapshot_and_subjects(self, _urlopen):
        call_command("update_sanctions_sources", source="un")

        snapshot = SanctionsSourceSnapshot.objects.get(source_code=SanctionsSourceSnapshot.SourceCode.UN_SC_CONSOLIDATED)
        self.assertEqual(snapshot.status, SanctionsSourceSnapshot.Status.SUCCESS)
        self.assertEqual(snapshot.record_count, 2)
        self.assertTrue(SanctionsSubject.objects.filter(primary_name="United Person").exists())
        self.assertTrue(SanctionsSubject.objects.filter(primary_name="United Entity Ltd").exists())

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
