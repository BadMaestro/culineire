import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from newsfeed.launch_copy import PINCH_LAUNCH_EVENT_KEY, PINCH_LAUNCH_TITLE
from newsfeed.models import NewsFeedEntry, SocialPostLog
from newsfeed.telegram import TelegramResult

User = get_user_model()


def _make_author():
    from recipes.models import RecipeAuthor
    user = User.objects.create_user(username="testauthor", password="pass", email="a@a.com")
    author, _ = RecipeAuthor.objects.get_or_create(user=user, defaults={"name": "Test Author"})
    return author


def _make_recipe(author, title="Test Recipe", status="pending"):
    from recipes.models import Recipe
    return Recipe.objects.create(
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        status=status,
        category=Recipe.Category.IRISH_CUISINE,
        ingredients="Eggs",
        method="Cook",
    )


def _make_article(author, title="Test Article", status="pending"):
    from articles.models import Article
    from django.utils import timezone
    return Article.objects.create(
        title=title,
        slug=title.lower().replace(" ", "-"),
        author=author,
        status=status,
        body="Body text.",
        published=timezone.localdate(),
    )


class RecipeFeedEntryTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    def test_recipe_approval_creates_entry(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            1,
        )

    def test_recipe_edit_does_not_duplicate_entry(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        recipe.title = "Updated Title"
        recipe.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            1,
        )

    def test_recipe_rejection_hides_auto_entry_and_reapproval_restores_it(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        event_key = f"recipe_published:{recipe.pk}"

        recipe.status = "rejected"
        recipe.save()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

        recipe.title = "Approved Again"
        recipe.status = "approved"
        recipe.save()

        entry.refresh_from_db()
        self.assertTrue(entry.is_public)
        self.assertEqual(entry.title, "New recipe published: Approved Again")

    def test_recipe_delete_hides_auto_entry(self):
        recipe = _make_recipe(self.author)
        recipe.status = "approved"
        recipe.save()
        event_key = f"recipe_published:{recipe.pk}"

        recipe.delete()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

    def test_pending_recipe_creates_no_entry(self):
        recipe = _make_recipe(self.author)
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"recipe_published:{recipe.pk}").count(),
            0,
        )


@override_settings(IS_TESTING=False, DISABLE_EXTERNAL_NOTIFICATIONS=False)
class RecipeTelegramPublishTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    @override_settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHANNEL_ID="@culineire_test",
        SITE_DOMAIN="culineire.test",
        SITE_SCHEME="https",
    )
    @patch("newsfeed.telegram.send_telegram_message")
    def test_recipe_approval_posts_to_telegram_once(self, send_telegram_message):
        send_telegram_message.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        recipe = _make_recipe(self.author)

        recipe.status = "approved"
        recipe.save()
        recipe.title = "Edited After Approval"
        recipe.save()

        self.assertEqual(send_telegram_message.call_count, 1)
        self.assertEqual(
            SocialPostLog.objects.filter(
                platform=SocialPostLog.Platform.TELEGRAM,
                event_key=f"recipe_published:{recipe.pk}",
                status=SocialPostLog.Status.SENT,
            ).count(),
            1,
        )

    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="")
    @patch("newsfeed.telegram.send_telegram_message")
    def test_missing_telegram_settings_create_no_log_or_request(self, send_telegram_message):
        recipe = _make_recipe(self.author)

        recipe.status = "approved"
        recipe.save()

        send_telegram_message.assert_not_called()
        self.assertFalse(SocialPostLog.objects.exists())

    @override_settings(TELEGRAM_BOT_TOKEN="test-token", TELEGRAM_CHANNEL_ID="@culineire_test")
    @patch("newsfeed.telegram.send_telegram_message")
    def test_pending_recipe_does_not_post_to_telegram(self, send_telegram_message):
        _make_recipe(self.author)

        send_telegram_message.assert_not_called()
        self.assertFalse(SocialPostLog.objects.exists())


@override_settings(IS_TESTING=False, DISABLE_EXTERNAL_NOTIFICATIONS=False)
class ArticleTelegramPublishTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    @override_settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHANNEL_ID="@culineire_test",
        SITE_DOMAIN="culineire.test",
        SITE_SCHEME="https",
    )
    @patch("newsfeed.telegram.send_telegram_message")
    def test_article_approval_posts_to_telegram_once(self, send_telegram_message):
        send_telegram_message.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        article = _make_article(self.author)

        article.status = "approved"
        article.save()
        article.title = "Edited After Approval"
        article.save()

        self.assertEqual(send_telegram_message.call_count, 1)
        self.assertEqual(
            SocialPostLog.objects.filter(
                platform=SocialPostLog.Platform.TELEGRAM,
                event_key=f"article_published:{article.pk}",
                status=SocialPostLog.Status.SENT,
            ).count(),
            1,
        )

    @override_settings(TELEGRAM_BOT_TOKEN="", TELEGRAM_CHANNEL_ID="")
    @patch("newsfeed.telegram.send_telegram_message")
    def test_missing_telegram_settings_create_no_article_log_or_request(self, send_telegram_message):
        article = _make_article(self.author)

        article.status = "approved"
        article.save()

        send_telegram_message.assert_not_called()
        self.assertFalse(SocialPostLog.objects.exists())


class ArticleFeedEntryTest(TestCase):
    def setUp(self):
        self.author = _make_author()

    def test_article_approval_creates_entry(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"article_published:{article.pk}").count(),
            1,
        )

    def test_article_edit_does_not_duplicate_entry(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        article.title = "Updated Article Title"
        article.save()
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"article_published:{article.pk}").count(),
            1,
        )

    def test_article_rejection_hides_auto_entry_and_reapproval_restores_it(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        event_key = f"article_published:{article.pk}"

        article.status = "rejected"
        article.save()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

        article.title = "Approved Again"
        article.status = "approved"
        article.save()

        entry.refresh_from_db()
        self.assertTrue(entry.is_public)
        self.assertEqual(entry.title, "New article published: Approved Again")

    def test_article_delete_hides_auto_entry(self):
        article = _make_article(self.author)
        article.status = "approved"
        article.save()
        event_key = f"article_published:{article.pk}"

        article.delete()

        entry = NewsFeedEntry.objects.get(event_key=event_key)
        self.assertFalse(entry.is_public)

    def test_pending_article_creates_no_entry(self):
        article = _make_article(self.author)
        self.assertEqual(
            NewsFeedEntry.objects.filter(event_key=f"article_published:{article.pk}").count(),
            0,
        )


@override_settings(
    SECURE_SSL_REDIRECT=False,
    SECURE_HSTS_SECONDS=0,
    SESSION_COOKIE_SECURE=False,
    CSRF_COOKIE_SECURE=False,
)
class FeedPageTest(TestCase):
    def setUp(self):
        self.client = Client()
        self.url = reverse("newsfeed:feed")

    def test_public_entries_visible(self):
        NewsFeedEntry.objects.create(
            entry_type="admin_note",
            title="Public note",
            is_public=True,
        )
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Public note")

    def test_private_entries_hidden(self):
        NewsFeedEntry.objects.create(
            entry_type="admin_note",
            title="Private note",
            is_public=False,
        )
        response = self.client.get(self.url)
        self.assertNotContains(response, "Private note")

    def test_manual_admin_entry_displayed(self):
        NewsFeedEntry.objects.create(
            entry_type="version_release",
            title="Version 1.4.3 released",
            version="1.4.3",
            is_public=True,
            is_auto=False,
        )
        response = self.client.get(self.url)
        self.assertContains(response, "Version 1.4.3 released")

    def test_news_feed_uses_ledger_layout_and_filters(self):
        NewsFeedEntry.objects.create(
            entry_type="recipe_published",
            title="Recipe update",
            is_public=True,
        )
        NewsFeedEntry.objects.create(
            entry_type="battle_event",
            title="Battle update",
            is_public=True,
        )

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="nf-summary"')
        self.assertContains(response, 'class="nf-toolbar"')
        self.assertContains(response, 'class="nf-filter')
        self.assertContains(response, 'class="nf-ledger"')
        self.assertContains(response, 'href="?type=recipes"')
        self.assertContains(response, 'href="?type=battle"')
        self.assertContains(response, "Chef Battle")
        self.assertContains(response, "Recipe update")
        self.assertContains(response, "Battle update")
        self.assertNotContains(response, "Back to My Dashboard")

    def test_news_feed_type_filter_limits_entries(self):
        NewsFeedEntry.objects.create(
            entry_type="recipe_published",
            title="Recipe update",
            is_public=True,
        )
        for index in range(31):
            NewsFeedEntry.objects.create(
                entry_type="battle_event",
                title=f"Battle update {index}",
                is_public=True,
            )

        response = self.client.get(self.url, {"type": "battle"})

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Battle update")
        self.assertNotContains(response, "Recipe update")
        self.assertContains(response, 'href="?type=battle" aria-current="page"')
        self.assertContains(response, 'href="?type=battle&amp;page=2"')

    def test_long_news_feed_collapses_extra_entries(self):
        for index in range(6):
            NewsFeedEntry.objects.create(
                entry_type="admin_note",
                title=f"Public note {index}",
                is_public=True,
            )

        response = self.client.get(self.url)

        self.assertContains(response, "View All News")
        self.assertContains(response, "nf-entry--extra")
        self.assertContains(response, "data-news-toggle")


def _make_ab(author, title="Test Bite", status="approved"):
    from pinch.models import Pinch
    return Pinch.objects.create(
        author=author,
        title=title,
        slug=title.lower().replace(" ", "-"),
        short_description="A short culinary note.",
        status=status,
    )


@override_settings(SITE_DOMAIN="culineire.ie", SITE_SCHEME="https")
class PinchTelegramMessageTest(TestCase):
    """Tests for the compact AB Telegram formatter."""

    def setUp(self):
        self.author = _make_author()

    def _make_entry(self, title="Tuna, Egg and Potato Salad", url="/pinch/tuna-egg-and-potato-salad/"):
        from newsfeed.models import NewsFeedEntry
        return NewsFeedEntry(
            entry_type=NewsFeedEntry.EntryType.PINCH_PUBLISHED,
            title=title,
            message="GreenBear: A simple layered salad of tender potatoes.",
            url=url,
        )

    def test_ab_message_contains_title(self):
        from newsfeed.telegram import build_ab_telegram_message
        entry = self._make_entry()
        msg = build_ab_telegram_message(entry)
        self.assertIn("Tuna, Egg and Potato Salad", msg)

    def test_ab_message_contains_absolute_url(self):
        from newsfeed.telegram import build_ab_telegram_message
        entry = self._make_entry()
        msg = build_ab_telegram_message(entry)
        self.assertIn("https://culineire.ie/pinch/tuna-egg-and-potato-salad/", msg)

    def test_pinch_message_has_pinch_prefix(self):
        from newsfeed.telegram import build_ab_telegram_message
        entry = self._make_entry()
        msg = build_ab_telegram_message(entry)
        self.assertTrue(msg.startswith("Pinch: "))

    def test_ab_message_does_not_contain_author_prefix(self):
        from newsfeed.telegram import build_ab_telegram_message
        entry = self._make_entry()
        msg = build_ab_telegram_message(entry)
        self.assertNotIn("GreenBear:", msg)

    def test_ab_message_does_not_contain_long_description(self):
        from newsfeed.telegram import build_ab_telegram_message
        entry = self._make_entry()
        msg = build_ab_telegram_message(entry)
        self.assertNotIn("simple layered salad", msg)


@override_settings(
    IS_TESTING=False,
    DISABLE_EXTERNAL_NOTIFICATIONS=False,
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_CHANNEL_ID="@culineire_test",
    SITE_DOMAIN="culineire.ie",
    SITE_SCHEME="https",
    PINCH_PUBLIC=True,
)
class PinchTelegramPublishTest(TestCase):
    """Tests that AB notifications use sendMessage (not sendPhoto) and are not duplicated."""

    def setUp(self):
        self.author = _make_author()

    @patch("newsfeed.telegram.send_telegram_message_with_link_preview")
    def test_ab_approval_uses_compact_link_preview(self, mock_send):
        """AB uses sendMessage with compact link preview options, not sendPhoto."""
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        ab = _make_ab(self.author, status="pending")
        ab.status = "approved"
        ab.save()
        self.assertEqual(mock_send.call_count, 1)

    @patch("newsfeed.telegram.send_telegram_photo")
    def test_ab_approval_does_not_use_send_photo(self, mock_photo):
        with patch("newsfeed.telegram.send_telegram_message_with_link_preview") as mock_send:
            mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
            ab = _make_ab(self.author, status="pending")
            ab.status = "approved"
            ab.save()
        mock_photo.assert_not_called()

    @patch("newsfeed.telegram.send_telegram_message_with_link_preview")
    def test_ab_telegram_message_is_compact(self, mock_send):
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        ab = _make_ab(self.author, title="Boxty Bite", status="pending")
        ab.status = "approved"
        ab.save()
        self.assertEqual(mock_send.call_count, 1)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("Pinch: Boxty Bite", sent_text)
        self.assertNotIn("short culinary note", sent_text)

    @patch("newsfeed.telegram.send_telegram_message_with_link_preview")
    def test_ab_notification_not_duplicated_after_edit(self, mock_send):
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        ab = _make_ab(self.author, status="pending")
        ab.status = "approved"
        ab.save()
        ab.short_description = "Updated description."
        ab.save()
        self.assertEqual(mock_send.call_count, 1)

    @patch("newsfeed.telegram.send_telegram_message")
    def test_recipe_notification_still_uses_send_message_not_link_preview(self, mock_send):
        """Recipe notifications go through publish_recipe_to_telegram (direct signal)."""
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        recipe = _make_recipe(self.author, status="pending")
        recipe.status = "approved"
        recipe.save()
        self.assertEqual(mock_send.call_count, 1)
        sent_text = mock_send.call_args[0][0]
        self.assertIn("New recipe on CulinEire:", sent_text)

    @patch("newsfeed.telegram._call_telegram_api")
    def test_compact_link_preview_payload_prefers_small_media(self, mock_call):
        from newsfeed.telegram import send_telegram_message_with_link_preview
        mock_call.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')

        send_telegram_message_with_link_preview("Pinch: Test\n\nhttps://culineire.ie/pinch/test/")

        token, method, payload = mock_call.call_args[0]
        self.assertEqual(token, "test-token")
        self.assertEqual(method, "sendMessage")
        options = json.loads(payload["link_preview_options"])
        self.assertFalse(options["is_disabled"])
        self.assertTrue(options["prefer_small_media"])
        self.assertFalse(options["show_above_text"])

    @patch("newsfeed.telegram._call_telegram_api")
    def test_compact_link_preview_payload_accepts_preview_url(self, mock_call):
        from newsfeed.telegram import send_telegram_message_with_link_preview
        mock_call.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')

        send_telegram_message_with_link_preview(
            "Pinch: Test\n\nhttps://culineire.ie/pinch/test/",
            preview_url="https://culineire.ie/pinch/test/?tg=1-123",
        )

        payload = mock_call.call_args[0][2]
        options = json.loads(payload["link_preview_options"])
        self.assertEqual(options["url"], "https://culineire.ie/pinch/test/?tg=1-123")

    @patch("newsfeed.telegram.send_telegram_message_with_link_preview")
    def test_ab_publish_uses_cache_busted_preview_url(self, mock_send):
        mock_send.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        ab = _make_ab(self.author, title="Cache Bite", status="pending")

        ab.status = "approved"
        ab.save()

        sent_text = mock_send.call_args[0][0]
        preview_url = mock_send.call_args.kwargs["preview_url"]
        self.assertIn("https://culineire.ie/pinch/cache-bite/", sent_text)
        self.assertRegex(preview_url, r"https://culineire\.ie/pinch/cache-bite/\?tg=\d+-\d+")


@override_settings(IS_TESTING=False, DISABLE_EXTERNAL_NOTIFICATIONS=False)
class PinchLaunchNewsCommandTest(TestCase):
    @override_settings(
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHANNEL_ID="@culineire_test",
        SITE_SCHEME="https",
        SITE_DOMAIN="culineire.ie",
    )
    @patch("newsfeed.telegram.send_telegram_message")
    def test_command_creates_public_news_and_pushes_telegram_once(self, send_telegram_message):
        send_telegram_message.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')

        call_command("publish_pinch_launch_news")

        entry = NewsFeedEntry.objects.get(event_key=PINCH_LAUNCH_EVENT_KEY)
        self.assertEqual(entry.title, PINCH_LAUNCH_TITLE)
        self.assertTrue(entry.is_public)
        self.assertFalse(entry.is_auto)
        self.assertIn("mobile-first feed", entry.message)

        self.assertEqual(send_telegram_message.call_count, 1)
        self.assertTrue(
            SocialPostLog.objects.filter(
                platform=SocialPostLog.Platform.TELEGRAM,
                event_key=f"newsfeed_launch:{PINCH_LAUNCH_EVENT_KEY}",
                status=SocialPostLog.Status.SENT,
            ).exists()
        )

        call_command("publish_pinch_launch_news")

        self.assertEqual(send_telegram_message.call_count, 1)


class TelegramNotificationGuardTests(TestCase):
    """Verify the IS_TESTING / DISABLE_EXTERNAL_NOTIFICATIONS guard prevents real sends."""

    # ------------------------------------------------------------------ #
    # Helpers                                                              #
    # ------------------------------------------------------------------ #

    def _call_api(self):
        from newsfeed.telegram import _call_telegram_api
        return _call_telegram_api("tok", "sendMessage", {"chat_id": "@c", "text": "hi"})

    # ------------------------------------------------------------------ #
    # Guard active: IS_TESTING=True (default during the test suite)       #
    # ------------------------------------------------------------------ #

    @patch("newsfeed.telegram.urlopen")
    def test_call_telegram_api_is_skipped_when_is_testing_true(self, mock_urlopen):
        """_call_telegram_api must never open a network connection during tests."""
        result = self._call_api()

        mock_urlopen.assert_not_called()
        self.assertEqual(result.status, "skipped")
        self.assertFalse(result.ok)

    @patch("newsfeed.telegram.urlopen")
    @override_settings(IS_TESTING=True)
    def test_no_urllib_call_possible_when_is_testing_true(self, mock_urlopen):
        """Belt-and-braces: patching urlopen AND checking it stays uncalled."""
        self._call_api()
        mock_urlopen.assert_not_called()

    # ------------------------------------------------------------------ #
    # Guard active: DISABLE_EXTERNAL_NOTIFICATIONS=True                   #
    # ------------------------------------------------------------------ #

    @patch("newsfeed.telegram.urlopen")
    @override_settings(IS_TESTING=False, DISABLE_EXTERNAL_NOTIFICATIONS=True)
    def test_call_telegram_api_is_skipped_when_disable_external_notifications_true(self, mock_urlopen):
        result = self._call_api()

        mock_urlopen.assert_not_called()
        self.assertEqual(result.status, "skipped")

    @patch("newsfeed.telegram.urlopen")
    @override_settings(IS_TESTING=False, DISABLE_EXTERNAL_NOTIFICATIONS=True,
                       TELEGRAM_BOT_TOKEN="sk_real", TELEGRAM_CHANNEL_ID="@real")
    def test_publish_to_telegram_skipped_without_creating_social_post_log(self, mock_urlopen):
        """_publish_to_telegram must return early and not create a SocialPostLog entry."""
        from newsfeed.telegram import _publish_to_telegram

        result = _publish_to_telegram(
            event_key="guard_test:1",
            message="Should not send",
            target_url="/test/",
        )

        mock_urlopen.assert_not_called()
        self.assertEqual(result.status, "skipped")
        self.assertFalse(SocialPostLog.objects.exists())


    # ------------------------------------------------------------------ #
    # Guard inactive: production path exercises _call_telegram_api        #
    # ------------------------------------------------------------------ #

    @override_settings(
        IS_TESTING=False,
        DISABLE_EXTERNAL_NOTIFICATIONS=False,
        TELEGRAM_BOT_TOKEN="test-token",
        TELEGRAM_CHANNEL_ID="@culineire_test",
    )
    @patch("newsfeed.telegram.urlopen")
    def test_production_path_calls_telegram_api_when_guard_is_false(self, mock_urlopen):
        """When guard is off and tokens are present, _call_telegram_api reaches urlopen."""
        import io
        mock_urlopen.return_value.__enter__ = lambda s: s
        mock_urlopen.return_value.__exit__ = lambda s, *a: False
        mock_urlopen.return_value.read.return_value = b'{"ok": true}'

        result = self._call_api()

        mock_urlopen.assert_called_once()
        self.assertTrue(result.ok)
        self.assertEqual(result.status, "sent")


class BattleEventFeedTest(TestCase):
    """NewsFeedEntry creation and sub_type propagation via create_battle_event."""

    def setUp(self):
        self.author = _make_author()

    def _make_battle(self):
        from django.utils import timezone
        from chef_battle.models import BattleChallenge
        from chef_battle.services import accept_challenge
        User = get_user_model()
        from recipes.models import RecipeAuthor
        user2 = User.objects.create_user(username="opponent", password="pass", email="b@b.com")
        opponent = RecipeAuthor.objects.create(user=user2, name="Opponent", slug="opponent")
        challenge = BattleChallenge.objects.create(
            challenger=self.author,
            opponent=opponent,
            expires_at=timezone.now() + timezone.timedelta(hours=24),
        )
        return accept_challenge(challenge)

    @override_settings(CHEF_BATTLE_ENABLED=True)
    def test_create_battle_event_with_publish_creates_newsfeed_entry(self):
        from chef_battle.services import create_battle_event
        from chef_battle.models import BattleEvent
        battle = self._make_battle()
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_COMPLETED,
            message="Battle finished",
            battle=battle,
            publish_to_news=True,
        )
        entry = NewsFeedEntry.objects.get(
            entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
            sub_type=BattleEvent.EventType.BATTLE_COMPLETED,
        )
        self.assertEqual(entry.title, "Battle finished")

    @override_settings(CHEF_BATTLE_ENABLED=True)
    def test_crown_awarded_event_gets_crown_sub_type(self):
        from chef_battle.services import create_battle_event
        from chef_battle.models import BattleEvent
        battle = self._make_battle()
        create_battle_event(
            event_type=BattleEvent.EventType.CROWN_AWARDED,
            message="New crown holder",
            battle=battle,
            publish_to_news=True,
        )
        entry = NewsFeedEntry.objects.get(
            entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
            sub_type=BattleEvent.EventType.CROWN_AWARDED,
        )
        self.assertEqual(entry.title, "New crown holder")

    @override_settings(CHEF_BATTLE_ENABLED=True)
    def test_publish_false_does_not_create_newsfeed_entry(self):
        from chef_battle.services import create_battle_event
        from chef_battle.models import BattleEvent
        battle = self._make_battle()
        create_battle_event(
            event_type=BattleEvent.EventType.CROWN_AWARDED,
            message="Hidden crown event",
            battle=battle,
            publish_to_news=False,
        )
        self.assertFalse(
            NewsFeedEntry.objects.filter(
                entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
                sub_type=BattleEvent.EventType.CROWN_AWARDED,
            ).exists()
        )

    @override_settings(CHEF_BATTLE_ENABLED=False)
    def test_publish_to_news_ignored_when_chef_battle_flag_off(self):
        from chef_battle.services import create_battle_event
        from chef_battle.models import BattleEvent
        battle = self._make_battle()
        create_battle_event(
            event_type=BattleEvent.EventType.BATTLE_COMPLETED,
            message="Should not appear",
            battle=battle,
            publish_to_news=True,
        )
        self.assertFalse(NewsFeedEntry.objects.filter(entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT).exists())

    @override_settings(CHEF_BATTLE_ENABLED=True, SECURE_SSL_REDIRECT=False)
    def test_feed_page_renders_crown_awarded_badge(self):
        NewsFeedEntry.objects.create(
            entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
            title="Crown awarded to GreenBear",
            sub_type="crown_awarded",
            is_public=True,
        )
        client = Client()
        response = client.get(reverse("newsfeed:feed"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Crown Awarded")
        self.assertContains(response, "nf-badge--crown_awarded")

    @override_settings(CHEF_BATTLE_ENABLED=True, SECURE_SSL_REDIRECT=False)
    def test_feed_page_renders_rank_promoted_badge(self):
        NewsFeedEntry.objects.create(
            entry_type=NewsFeedEntry.EntryType.BATTLE_EVENT,
            title="Chef promoted to rank 2",
            sub_type="rank_promoted",
            is_public=True,
        )
        client = Client()
        response = client.get(reverse("newsfeed:feed"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Rank Change")
        self.assertContains(response, "nf-badge--rank_promoted")


@override_settings(
    IS_TESTING=False,
    DISABLE_EXTERNAL_NOTIFICATIONS=False,
    TELEGRAM_BOT_TOKEN="test-token",
    TELEGRAM_CHANNEL_ID="@culineire_test",
)
class TelegramPhotoUploadTests(TestCase):
    @patch("newsfeed.telegram._call_telegram_api")
    def test_text_fallback_disables_link_preview(self, mock_call):
        from newsfeed.telegram import send_telegram_message_without_link_preview

        mock_call.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')

        result = send_telegram_message_without_link_preview("Sponsor announcement")

        self.assertTrue(result.ok)
        self.assertEqual(mock_call.call_args.args[1], "sendMessage")
        self.assertEqual(mock_call.call_args.args[2]["disable_web_page_preview"], "true")

    @patch("newsfeed.telegram._call_telegram_multipart_api")
    def test_photo_upload_sends_binary_file_as_multipart(self, mock_call):
        import io
        from PIL import Image
        from django.core.files.base import ContentFile
        from django.core.files.storage import default_storage
        from newsfeed.telegram import send_telegram_photo_upload

        mock_call.return_value = TelegramResult(ok=True, status="sent", response='{"ok": true}')
        source = io.BytesIO()
        Image.new("RGB", (12, 600), "#123c2d").save(source, format="PNG")
        name = default_storage.save("telegram-tests/sponsor.png", ContentFile(source.getvalue()))
        try:
            with default_storage.open(name, "rb") as image:
                result = send_telegram_photo_upload(image, "Sponsor caption")
        finally:
            default_storage.delete(name)

        self.assertTrue(result.ok)
        kwargs = mock_call.call_args.kwargs
        self.assertEqual(kwargs["file_field"], "photo")
        self.assertEqual(kwargs["filename"], "culineire-sponsor.jpg")
        self.assertEqual(kwargs["content_type"], "image/jpeg")
        with Image.open(io.BytesIO(kwargs["file_bytes"])) as uploaded:
            self.assertEqual(uploaded.size, (1200, 630))
