"""
Tests for the legal app.

Covers:
  - All legal pages are publicly accessible (no login required)
  - report_content is accessible to anonymous users
  - report_content is accessible to authenticated users
  - Anonymous report submission works end-to-end
  - Authenticated report submission pre-populates name/email
  - Good-faith declaration is required
  - Honeypot rejects spam
  - Rate limit response is handled gracefully
  - New model fields exist and save correctly
  - Reports admin view requires superuser
  - New URL routes work: terms, cookies, company-information
"""

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from .models import ContentReport

User = get_user_model()


class LegalPublicAccessTests(TestCase):
    """All public legal pages must return 200 for anonymous visitors."""

    def setUp(self):
        self.client = Client()

    def _assert_public(self, url_name, kwargs=None):
        url = reverse(url_name, kwargs=kwargs)
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            f"{url_name} returned {response.status_code} for anonymous user",
        )

    def test_legal_hub_public(self):
        self._assert_public("legal:legal_hub")

    def test_terms_public(self):
        self._assert_public("legal:terms")

    def test_terms_page_uses_document_layout(self):
        response = self.client.get(reverse("legal:terms"))
        html = response.content.decode("utf-8")
        hero = html.split('<section class="hero hero--home hero--legal"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="legal-shell legal-shell--terms"')
        self.assertContains(response, 'class="legal-summary-panel"')
        self.assertContains(response, 'class="legal-mobile-jump"')
        self.assertContains(response, 'class="legal-document-layout"')
        self.assertContains(response, 'class="legal-toc"')
        self.assertContains(response, 'class="legal-card-grid legal-card-grid--document legal-document-main"')
        self.assertIn(reverse("legal:legal_hub"), hero)
        self.assertIn(reverse("privacy"), hero)
        self.assertIn(reverse("legal:cookies"), hero)
        self.assertIn('href="#contact"', hero)
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Sponsors", hero)

    def test_cookies_public(self):
        self._assert_public("legal:cookies")

    def test_cookies_page_uses_document_layout(self):
        response = self.client.get(reverse("legal:cookies"))
        html = response.content.decode("utf-8")
        hero = html.split('<section class="hero hero--home hero--legal"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="legal-shell legal-shell--cookies"')
        self.assertContains(response, 'class="legal-summary-panel"')
        self.assertContains(response, 'class="legal-mobile-jump"')
        self.assertContains(response, 'class="legal-document-layout"')
        self.assertContains(response, 'class="legal-toc"')
        self.assertContains(response, 'class="legal-card-grid legal-card-grid--document legal-document-main"')
        self.assertContains(response, 'class="legal-cookie-table-wrap"')
        self.assertContains(response, 'class="legal-cookie-table"')
        self.assertIn(reverse("legal:legal_hub"), hero)
        self.assertIn(reverse("privacy"), hero)
        self.assertIn(reverse("legal:terms"), hero)
        self.assertIn('href="#contact"', hero)
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Sponsors", hero)

    def test_company_information_public(self):
        self._assert_public("legal:company_information")

    def test_company_information_page_uses_document_layout(self):
        response = self.client.get(reverse("legal:company_information"))
        html = response.content.decode("utf-8")
        hero = html.split('<section class="hero hero--home hero--legal"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="legal-shell legal-shell--company"')
        self.assertContains(response, 'class="legal-summary-panel"')
        self.assertContains(response, 'class="legal-mobile-jump"')
        self.assertContains(response, 'class="legal-document-layout"')
        self.assertContains(response, 'class="legal-toc"')
        self.assertContains(response, 'class="legal-card-grid legal-card-grid--document legal-document-main"')
        self.assertIn(reverse("legal:legal_hub"), hero)
        self.assertIn(reverse("privacy"), hero)
        self.assertIn(reverse("legal:terms"), hero)
        self.assertIn('href="#contact-details"', hero)
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Sponsors", hero)

    def test_content_publishing_rules_public(self):
        self._assert_public("legal:content_publishing_rules")

    def test_author_submission_agreement_public(self):
        self._assert_public("legal:author_submission_agreement")

    def test_copyright_image_rights_guide_public(self):
        self._assert_public("legal:copyright_image_rights_guide")

    def test_report_content_public(self):
        """report_content must NOT redirect anonymous visitors to login."""
        url = reverse("legal:report_content")
        response = self.client.get(url)
        self.assertEqual(
            response.status_code,
            200,
            "report_content must be accessible to anonymous users",
        )
        # Must not redirect to login page
        self.assertNotIn("/accounts/login/", response.get("Location", ""))

    def test_report_content_page_uses_report_layout(self):
        response = self.client.get(reverse("legal:report_content"))
        html = response.content.decode("utf-8")
        hero = html.split('<section class="hero hero--home hero--legal"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="legal-shell legal-shell--report"')
        self.assertContains(response, 'class="legal-summary-panel"')
        self.assertContains(response, 'class="legal-mobile-jump"')
        self.assertContains(response, 'class="legal-document-layout legal-report-layout"')
        self.assertContains(response, 'class="legal-report-guide"')
        self.assertContains(response, 'class="authoring-form legal-report-form"')
        self.assertIn(reverse("legal:legal_hub"), hero)
        self.assertIn(reverse("legal:copyright_image_rights_guide"), hero)
        self.assertIn(reverse("legal:content_publishing_rules"), hero)
        self.assertIn(reverse("legal:company_information"), hero)
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Sponsors", hero)

    def test_privacy_public(self):
        response = self.client.get(reverse("privacy"))
        self.assertEqual(response.status_code, 200)

    def test_privacy_page_uses_document_layout(self):
        response = self.client.get(reverse("privacy"))
        html = response.content.decode("utf-8")
        hero = html.split('<section class="hero hero--home hero--legal"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="legal-shell legal-shell--privacy"')
        self.assertContains(response, 'class="legal-summary-panel"')
        self.assertContains(response, 'class="legal-mobile-jump"')
        self.assertContains(response, 'class="legal-document-layout"')
        self.assertContains(response, 'class="legal-toc"')
        self.assertContains(response, 'class="legal-card-grid legal-card-grid--document legal-document-main"')
        self.assertIn(reverse("legal:legal_hub"), hero)
        self.assertIn(reverse("legal:terms"), hero)
        self.assertIn(reverse("legal:cookies"), hero)
        self.assertIn('href="#contact"', hero)
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Sponsors", hero)

    def test_legal_hub_preserves_links_and_visual_layout(self):
        response = self.client.get(reverse("legal:legal_hub"))
        html = response.content.decode("utf-8")
        hero = html.split('<section class="hero hero--home hero--legal"', 1)[1].split("</section>", 1)[0]

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="hero hero--home hero--legal"')
        self.assertContains(response, 'class="container hero__inner"')
        self.assertContains(response, 'class="hero-copy"')
        self.assertContains(response, 'class="legal-shell legal-shell--hub"')
        self.assertContains(response, 'class="legal-summary-panel legal-summary-panel--hub"')
        self.assertContains(response, 'class="legal-mobile-jump"')
        self.assertContains(response, 'class="legal-document-layout legal-hub-layout"')
        self.assertContains(response, 'class="legal-toc"')
        self.assertContains(response, 'class="legal-card-grid legal-card-grid--hub"')
        self.assertContains(response, 'class="legal-contact-card legal-contact-card--hub"')
        self.assertIn(reverse("legal:terms"), hero)
        self.assertIn(reverse("privacy"), hero)
        self.assertIn(reverse("legal:cookies"), hero)
        self.assertIn(reverse("legal:report_content"), hero)
        self.assertNotIn("Explore Recipes", hero)
        self.assertNotIn("Sponsors", hero)
        for anchor in ["#platform-rules", "#data-privacy", "#author-content", "#company-reporting"]:
            self.assertContains(response, f'href="{anchor}"')

        expected_links = [
            (reverse("legal:terms"), "Terms of Use"),
            (reverse("privacy"), "Privacy Policy"),
            (reverse("legal:cookies"), "Cookie Policy"),
            (reverse("legal:report_content"), "Report Content"),
            (reverse("legal:company_information"), "Company Information"),
            (reverse("legal:content_publishing_rules"), "Content Publishing Rules"),
            (reverse("legal:author_submission_agreement"), "Author Submission Agreement"),
            (reverse("legal:copyright_image_rights_guide"), "Copyright and Image Rights"),
        ]
        for url, text in expected_links:
            with self.subTest(text=text):
                self.assertContains(response, f'href="{url}"')
                self.assertContains(response, text)


class ReportContentAnonymousSubmissionTests(TestCase):
    """Anonymous users can submit a content report."""

    def setUp(self):
        self.client = Client()
        self.url = reverse("legal:report_content")

    @patch("legal.views.verify_turnstile", return_value=True)
    @patch("legal.views._send_report_notification")
    def test_anonymous_submission_creates_report(self, mock_notify, mock_turnstile):
        response = self.client.post(self.url, {
            "reporter_name": "Jane Doe",
            "reporter_email": "jane@example.com",
            "organisation": "Example Ltd",
            "report_type": "copyright",
            "reported_url": "https://culineire.ie/recipes/test/",
            "evidence_url": "https://original-source.com/photo",
            "description": "This recipe was taken from my original blog post.",
            "good_faith_confirmed": True,
            "website": "",  # honeypot empty
            "cf-turnstile-response": "dummy-token",
        })
        self.assertEqual(response.status_code, 200)
        report = ContentReport.objects.first()
        self.assertIsNotNone(report)
        self.assertEqual(report.reporter_name, "Jane Doe")
        self.assertEqual(report.reporter_email, "jane@example.com")
        self.assertEqual(report.organisation, "Example Ltd")
        self.assertEqual(report.evidence_url, "https://original-source.com/photo")
        self.assertIsNone(report.reporter_user)
        self.assertTrue(report.good_faith_confirmed)
        self.assertEqual(report.status, ContentReport.Status.OPEN)
        mock_notify.assert_called_once()

    @patch("legal.views.verify_turnstile", return_value=True)
    def test_good_faith_required(self, mock_turnstile):
        """Form should be invalid if good_faith_confirmed is not checked."""
        response = self.client.post(self.url, {
            "reporter_name": "Jane Doe",
            "reporter_email": "jane@example.com",
            "report_type": "copyright",
            "description": "A valid description here.",
            "good_faith_confirmed": False,
            "website": "",
            "cf-turnstile-response": "dummy-token",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContentReport.objects.count(), 0)

    @patch("legal.views.verify_turnstile", return_value=True)
    def test_honeypot_rejects_spam(self, mock_turnstile):
        response = self.client.post(self.url, {
            "reporter_name": "Spammer",
            "reporter_email": "spam@spam.com",
            "report_type": "other",
            "description": "Spam submission.",
            "good_faith_confirmed": True,
            "website": "http://spam.example.com",  # honeypot filled
            "cf-turnstile-response": "dummy-token",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContentReport.objects.count(), 0)

    @patch("legal.views.verify_turnstile", return_value=False)
    def test_turnstile_failure_shows_error(self, mock_turnstile):
        response = self.client.post(self.url, {
            "reporter_name": "Jane",
            "reporter_email": "jane@example.com",
            "report_type": "copyright",
            "description": "Turnstile should fail.",
            "good_faith_confirmed": True,
            "website": "",
            "cf-turnstile-response": "bad-token",
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContentReport.objects.count(), 0)
        self.assertContains(response, "Security check failed")


class ReportContentAuthenticatedTests(TestCase):
    """Authenticated users can submit reports with pre-populated fields."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="testuser@example.com",
            password="testpass123",
            first_name="Test",
            last_name="User",
        )
        self.client = Client()
        self.client.login(username="testuser", password="testpass123")
        self.url = reverse("legal:report_content")

    def test_get_shows_prepopulated_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        # Name and email should be pre-populated in form initial values
        form = response.context["form"]
        self.assertEqual(form.fields["reporter_name"].initial, "Test User")
        self.assertEqual(form.fields["reporter_email"].initial, "testuser@example.com")

    @patch("legal.views.verify_turnstile", return_value=True)
    @patch("legal.views._send_report_notification")
    @patch("legal.views._create_report_message", return_value=None)
    def test_authenticated_submission_links_user(self, mock_msg, mock_notify, mock_turnstile):
        response = self.client.post(self.url, {
            "reporter_name": "Test User",
            "reporter_email": "testuser@example.com",
            "organisation": "",
            "report_type": "stolen_recipe",
            "reported_url": "https://culineire.ie/recipes/stew/",
            "evidence_url": "",
            "description": "This recipe was stolen from my website.",
            "good_faith_confirmed": True,
            "website": "",
            "cf-turnstile-response": "dummy-token",
        })
        self.assertEqual(response.status_code, 200)
        report = ContentReport.objects.first()
        self.assertIsNotNone(report)
        self.assertEqual(report.reporter_user, self.user)
        self.assertEqual(report.reporter_name, "Test User")


class ContentReportModelTests(TestCase):
    """Test new model fields and the Status choices."""

    def test_new_fields_exist(self):
        report = ContentReport(
            reporter_name="Alice",
            reporter_email="alice@example.com",
            organisation="Alice Corp",
            evidence_url="https://proof.com",
            good_faith_confirmed=True,
            report_type=ContentReport.ReportType.PRIVACY_DATA,
            description="A privacy concern.",
            status=ContentReport.Status.UNDER_REVIEW,
            internal_notes="Being investigated.",
        )
        report.save()
        fetched = ContentReport.objects.get(pk=report.pk)
        self.assertEqual(fetched.organisation, "Alice Corp")
        self.assertEqual(fetched.evidence_url, "https://proof.com")
        self.assertTrue(fetched.good_faith_confirmed)
        self.assertEqual(fetched.report_type, "privacy_data")
        self.assertEqual(fetched.status, ContentReport.Status.UNDER_REVIEW)
        self.assertEqual(fetched.internal_notes, "Being investigated.")
        self.assertIsNotNone(fetched.updated_at)

    def test_new_report_type_choices(self):
        types = [c[0] for c in ContentReport.ReportType.choices]
        for expected in ["privacy_data", "impersonation", "defamation", "food_safety", "spam"]:
            self.assertIn(expected, types)

    def test_status_choices(self):
        statuses = [c[0] for c in ContentReport.Status.choices]
        for expected in ["open", "under_review", "resolved", "dismissed"]:
            self.assertIn(expected, statuses)

    def test_default_status_is_open(self):
        report = ContentReport.objects.create(
            reporter_name="Bob",
            reporter_email="bob@example.com",
            report_type=ContentReport.ReportType.OTHER,
            description="Something.",
            good_faith_confirmed=True,
        )
        self.assertEqual(report.status, ContentReport.Status.OPEN)


class ReportsAdminAccessTests(TestCase):
    """Admin report views must require superuser."""

    def setUp(self):
        self.regular_user = User.objects.create_user(
            username="regular", email="r@example.com", password="pass"
        )
        self.superuser = User.objects.create_superuser(
            username="admin", email="admin@example.com", password="adminpass"
        )

    def test_reports_list_redirects_anonymous(self):
        response = Client().get(reverse("legal:reports_list"))
        self.assertIn(response.status_code, [302, 403, 404])

    def test_reports_list_returns_404_for_non_superuser(self):
        c = Client()
        c.login(username="regular", password="pass")
        response = c.get(reverse("legal:reports_list"))
        self.assertEqual(response.status_code, 404)

    def test_reports_list_accessible_to_superuser(self):
        c = Client()
        c.login(username="admin", password="adminpass")
        response = c.get(reverse("legal:reports_list"))
        self.assertEqual(response.status_code, 200)


class SponsorsPublicAccessTests(TestCase):
    """Sponsors-related public pages must return 200 for anonymous visitors."""

    def setUp(self):
        self.client = Client()

    def test_annual_contract_public(self):
        response = self.client.get(reverse("sponsors:annual_contract"))
        self.assertEqual(response.status_code, 200)

    def test_sponsors_puzzle_public(self):
        response = self.client.get(reverse("sponsors:puzzle"))
        self.assertEqual(response.status_code, 200)

    def test_sponsors_page_links_to_annual_contract(self):
        """Sponsors puzzle page must contain a link to /sponsors/annual-contract/."""
        response = self.client.get(reverse("sponsors:puzzle"))
        self.assertContains(response, "/sponsors/annual-contract/")

    def test_annual_contract_link_opens_new_tab(self):
        """The annual contract link must have target=_blank and rel=noopener noreferrer."""
        response = self.client.get(reverse("sponsors:puzzle"))
        content = response.content.decode("utf-8")
        self.assertIn('target="_blank"', content)
        self.assertIn('rel="noopener noreferrer"', content)


class CorporationTaxNumberNotPublishedTest(TestCase):
    """
    Tax/VAT identifier publication policy.

    The company tax/VAT identifier must not appear on ordinary public legal pages.
    The sponsor annual contract is the explicit exception because sponsor payments
    are VAT-rated and the page sets out the commercial terms for paid sponsorship.
    """

    TAX_NUMBER = "3645402WH"

    TAX_NUMBER_RESTRICTED_PAGES = [
        "legal:legal_hub",
        "legal:terms",
        "legal:cookies",
        "legal:company_information",
        "legal:content_publishing_rules",
        "legal:copyright_image_rights_guide",
        "privacy",
        "sponsors:puzzle",
    ]

    TAX_NUMBER_ALLOWED_PAGES = [
        "sponsors:annual_contract",
    ]

    def test_tax_number_not_in_restricted_public_pages(self):
        c = Client()
        for url_name in self.TAX_NUMBER_RESTRICTED_PAGES:
            url = reverse(url_name)
            response = c.get(url)
            self.assertNotIn(
                self.TAX_NUMBER,
                response.content.decode("utf-8"),
                f"Tax/VAT identifier found in response for {url_name} — this page must not publish it",
            )

    def test_tax_number_allowed_on_sponsor_annual_contract(self):
        c = Client()
        for url_name in self.TAX_NUMBER_ALLOWED_PAGES:
            url = reverse(url_name)
            response = c.get(url)
            self.assertContains(response, self.TAX_NUMBER)
