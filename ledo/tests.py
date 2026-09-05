import uuid
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone, translation

from .forms import BookingRequestForm, OsloDateTimeField
from .models import AuditEvent, Booking, CustomerContact, Fare, Route
from .services import QuoteUnavailable, quote_for_route, transition_booking


@override_settings(LEDO_ENABLED=True, LEDO_PREVIEW_STAFF_ONLY=True)
class LedoAccessTests(TestCase):
    def setUp(self):
        self.staff = get_user_model().objects.create_user(
            username="ledo-staff",
            password="test-password",
            is_staff=True,
        )

    def test_preview_is_hidden_from_anonymous_users(self):
        self.assertEqual(self.client.get(reverse("ledo:home")).status_code, 404)

    def test_preview_is_hidden_from_regular_users(self):
        user = get_user_model().objects.create_user(
            username="ledo-customer",
            password="test-password",
        )
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("ledo:home")).status_code, 404)

    def test_staff_user_can_open_preview(self):
        self.client.force_login(self.staff)
        response = self.client.get(reverse("ledo:home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "LEDO Drive")

    @override_settings(LEDO_ENABLED=False)
    def test_disabled_application_returns_not_found(self):
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse("ledo:home")).status_code, 404)
        self.assertEqual(self.client.get(reverse("ledo:health")).status_code, 404)

    def test_health_endpoint_reports_ready(self):
        response = self.client.get(reverse("ledo:health"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"application": "LEDO", "status": "ok"})


@override_settings(LEDO_ENABLED=True, LEDO_PREVIEW_STAFF_ONLY=False)
class BookingRequestTests(TestCase):
    def setUp(self):
        cache.clear()
        self.route = Route.objects.create(
            name="Kongsberg → Gardermoen",
            origin="Kongsberg",
            destination="Oslo lufthavn Gardermoen",
            direction=Route.Direction.TO_AIRPORT,
        )
        self.fare = Fare.objects.create(
            route=self.route,
            vehicle_class="Standard",
            one_way_price=Decimal("1490.00"),
            return_price=Decimal("2790.00"),
            currency="NOK",
            vat_included=True,
            valid_from=timezone.localdate() - timedelta(days=1),
        )

    def booking_payload(self, **changes):
        pickup = timezone.localtime(timezone.now() + timedelta(days=2))
        data = {
            "route": str(self.route.pk),
            "pickup_at": pickup.strftime("%Y-%m-%dT%H:%M"),
            "adults": "2",
            "children": "0",
            "luggage": "2",
            "flight_number": "SK123",
            "notes": "",
            "name": "Test Kunde",
            "email": "kunde@example.no",
            "phone": "+47 900 00 000",
            "accept_terms": "on",
            "idempotency_key": str(uuid.uuid4()),
            "website": "",
        }
        data.update(changes)
        return data

    def test_landing_displays_current_server_price(self):
        response = self.client.get(reverse("ledo:home"))
        self.assertContains(response, "1490 NOK")
        self.assertContains(response, "Kongsberg → Gardermoen")

    def test_valid_request_creates_booking_contact_and_audit_event(self):
        response = self.client.post(reverse("ledo:booking_create"), self.booking_payload())
        booking = Booking.objects.get()
        self.assertRedirects(
            response,
            reverse("ledo:booking_confirmation", args=(booking.public_id,)),
        )
        self.assertEqual(booking.quoted_price, Decimal("1490.00"))
        self.assertEqual(booking.fare_snapshot["amount"], "1490.00")
        self.assertEqual(CustomerContact.objects.get().email, "kunde@example.no")
        self.assertTrue(AuditEvent.objects.filter(event_type="booking.requested").exists())

    def test_duplicate_submission_creates_one_booking(self):
        payload = self.booking_payload()
        first = self.client.post(reverse("ledo:booking_create"), payload)
        second = self.client.post(reverse("ledo:booking_create"), payload)
        self.assertEqual(first.status_code, 302)
        self.assertEqual(second.status_code, 302)
        self.assertEqual(Booking.objects.count(), 1)
        self.assertEqual(CustomerContact.objects.count(), 1)

    def test_translated_booking_flow_all_languages(self):
        for code, heading, label, error in [
            ('nb', 'Forespørsel mottatt', 'Navn', 'Velg et tidspunkt i fremtiden.'),
            ('en', 'Request received', 'Name', 'Choose a future date and time.'),
            ('lt', 'Užklausa gauta', 'Vardas', 'Pasirinkite laiką ateityje.'),
            ('ru', 'Заявка получена', 'Имя', 'Выберите дату и время в будущем.'),
        ]:
            with self.subTest(language=code):
                cache.clear()
                page = self.client.get(f'/ledo/?lang={code}')
                self.assertContains(page, label)
                invalid = self.client.post(f'/ledo/bestill/?lang={code}',
                    self.booking_payload(pickup_at='2020-01-01T12:00'))
                self.assertContains(invalid, error, status_code=400)
                result = self.client.post(f'/ledo/bestill/?lang={code}',
                    self.booking_payload(), follow=True)
                self.assertContains(result, heading)
                self.assertEqual(result['Content-Language'], code)

    def test_return_trip_uses_return_price(self):
        pickup = timezone.localtime(timezone.now() + timedelta(days=2))
        return_at = pickup + timedelta(days=7)
        payload = self.booking_payload(
            return_trip="on",
            return_at=return_at.strftime("%Y-%m-%dT%H:%M"),
        )
        self.client.post(reverse("ledo:booking_create"), payload)
        self.assertEqual(Booking.objects.get().quoted_price, Decimal("2790.00"))

    def test_price_sent_by_browser_is_ignored(self):
        payload = self.booking_payload(quoted_price="1.00", currency="EUR")
        self.client.post(reverse("ledo:booking_create"), payload)
        booking = Booking.objects.get()
        self.assertEqual(booking.quoted_price, Decimal("1490.00"))
        self.assertEqual(booking.currency, "NOK")

    def test_past_pickup_is_rejected(self):
        pickup = timezone.localtime(timezone.now() - timedelta(hours=1))
        response = self.client.post(
            reverse("ledo:booking_create"),
            self.booking_payload(pickup_at=pickup.strftime("%Y-%m-%dT%H:%M")),
        )
        self.assertEqual(response.status_code, 400)
        self.assertContains(response, "Velg et tidspunkt i fremtiden", status_code=400)
        self.assertFalse(Booking.objects.exists())

    def test_honeypot_submission_is_rejected(self):
        response = self.client.post(
            reverse("ledo:booking_create"),
            self.booking_payload(website="spam.example"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertFalse(Booking.objects.exists())

    def test_confirmation_is_not_visible_to_another_session(self):
        self.client.post(reverse("ledo:booking_create"), self.booking_payload())
        booking = Booking.objects.get()
        self.client.cookies.clear()
        response = self.client.get(reverse("ledo:booking_confirmation", args=(booking.public_id,)))
        self.assertEqual(response.status_code, 404)

    def test_expired_fare_is_not_used(self):
        self.fare.valid_to = timezone.localdate() - timedelta(days=1)
        self.fare.save(update_fields=("valid_to",))
        with self.assertRaises(QuoteUnavailable):
            quote_for_route(self.route, return_trip=False)


class BookingStatusTests(TestCase):
    def setUp(self):
        route = Route.objects.create(
            name="Test route",
            origin="A",
            destination="B",
            direction=Route.Direction.TO_AIRPORT,
        )
        self.booking = Booking.objects.create(
            route=route,
            pickup_at=timezone.now() + timedelta(days=1),
            quoted_price=Decimal("100.00"),
            currency="NOK",
            fare_snapshot={},
            terms_version="test",
            terms_accepted_at=timezone.now(),
            idempotency_key=uuid.uuid4(),
        )

    def test_valid_status_transition_writes_audit_event(self):
        booking, changed = transition_booking(self.booking, Booking.Status.CONFIRMED)
        self.assertTrue(changed)
        self.assertEqual(booking.status, Booking.Status.CONFIRMED)
        event = AuditEvent.objects.get()
        self.assertEqual(event.metadata["from"], Booking.Status.PENDING_CONFIRMATION)
        self.assertEqual(event.metadata["to"], Booking.Status.CONFIRMED)

    def test_invalid_status_transition_is_rejected(self):
        with self.assertRaises(ValidationError):
            transition_booking(self.booking, Booking.Status.COMPLETED)
        self.booking.refresh_from_db()
        self.assertEqual(self.booking.status, Booking.Status.PENDING_CONFIRMATION)


class BookingFormTests(TestCase):
    @override_settings(TIME_ZONE="Europe/Dublin")
    def test_oslo_time_is_not_rejected_by_dublin_dst_gap(self):
        value = OsloDateTimeField().clean("2027-03-28T01:30")
        self.assertEqual(value.hour, 1)
        self.assertEqual(value.utcoffset(), timedelta(hours=1))

    def test_route_queryset_excludes_routes_without_active_fares(self):
        route = Route.objects.create(
            name="No fare",
            origin="A",
            destination="B",
            direction=Route.Direction.TO_AIRPORT,
        )
        form = BookingRequestForm()
        self.assertNotIn(route, form.fields["route"].queryset)

    def test_nonexistent_oslo_dst_time_is_rejected(self):
        route = Route.objects.create(
            name="DST route",
            origin="A",
            destination="B",
            direction=Route.Direction.TO_AIRPORT,
        )
        Fare.objects.create(
            route=route,
            one_way_price=Decimal("100.00"),
            currency="NOK",
            valid_from=timezone.localdate(),
        )
        form = BookingRequestForm(
            {
                "route": route.pk,
                "pickup_at": "2027-03-28T02:30",
                "adults": 1,
                "children": 0,
                "luggage": 0,
                "name": "Test",
                "email": "test@example.no",
                "phone": "+47 90000000",
                "accept_terms": True,
                "idempotency_key": uuid.uuid4(),
            },
        )
        with translation.override('nb'):
            self.assertFalse(form.is_valid())
            self.assertIn("sommertid", form.errors["pickup_at"][0])


@override_settings(LEDO_ENABLED=True, LEDO_PREVIEW_STAFF_ONLY=False)
class LedoLanguageTests(TestCase):
    def test_all_languages_and_switcher(self):
        headings = {'nb': 'uten stress.', 'en': 'without the stress.',
                    'lt': 'be rūpesčių.', 'ru': 'без лишних забот.'}
        for code, heading in headings.items():
            with self.subTest(language=code):
                response = self.client.get('/ledo/', {'lang': code})
                self.assertContains(response, heading)
                self.assertContains(response, f'<html lang="{code}">')
                self.assertEqual(response['Content-Language'], code)
                for label in ('NO', 'EN', 'LT', 'RU'):
                    self.assertContains(response, f'>{label}</a>')

    def test_language_cookie_is_scoped_and_does_not_change_host_language(self):
        with translation.override('en'):
            response = self.client.get('/ledo/?lang=ru')
            self.assertEqual(translation.get_language(), 'en')
        self.assertEqual(response.cookies['ledo_language']['path'], '/ledo/')
        self.assertNotIn('django_language', response.cookies)
        self.assertContains(self.client.get('/ledo/'), 'без лишних забот.')

    def test_unknown_language_falls_back_and_is_not_reflected(self):
        response = self.client.get('/ledo/', {'lang': '<script>alert(1)</script>'})
        self.assertEqual(response['Content-Language'], 'nb')
        self.assertNotContains(response, '<script>alert(1)</script>')

    def test_invalid_form_and_rate_limit_are_translated(self):
        cache.clear()
        for code, expected in [('en', 'This field is required.'),
                               ('ru', 'Обязательное поле.')]:
            response = self.client.post(f'/ledo/bestill/?lang={code}', {})
            self.assertEqual(response.status_code, 400)
            # No active fare: inspect form errors even though the form is closed.
            with translation.override(code):
                self.assertEqual(str(response.context['form'].errors['name'][0]), expected)
        session = self.client.session
        cache.set(f'ledo:booking-rate:{session.session_key}', 5, 60)
        response = self.client.post('/ledo/bestill/?lang=ru', {})
        self.assertEqual(response.status_code, 429)
        with translation.override('ru'):
            self.assertIn('Слишком много попыток', str(response.context['form'].non_field_errors()))

    def test_catalog_complete_and_template_keys_known(self):
        import re
        from pathlib import Path
        from .i18n import CATALOG
        for source, translations in CATALOG.items():
            self.assertEqual(set(translations), {'nb', 'en', 'lt', 'ru'})
            self.assertTrue(all(translations.values()), source)
        for path in (Path(__file__).parent / 'templates/ledo').glob('*.html'):
            for key in re.findall(r"\{% t '([^']+)' %\}", path.read_text(encoding='utf-8')):
                self.assertIn(key, CATALOG, str(path))
