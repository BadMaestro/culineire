from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from articles.models import Article
from collection.models import ContentReaction, SavedContent
from recipes.models import Recipe, RecipeAuthor
from .models import AmuseBouche


class AmuseBouchePublicTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="reader", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")

    def create_item(self, title, status):
        return AmuseBouche.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_feed_is_hidden_until_public_launch(self):
        self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        response = self.client.get(reverse("amuse_bouche:feed"))
        self.assertEqual(response.status_code, 404)

    def test_staff_can_preview_feed_before_public_launch(self):
        self.user.is_staff = True
        self.user.save(update_fields=["is_staff"])
        approved = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.client.force_login(self.user)

        response = self.client.get(reverse("amuse_bouche:feed"))

        self.assertContains(response, approved.title)

    @override_settings(AMUSE_BOUCHE_PUBLIC=True)
    def test_feed_shows_only_approved_items_when_public(self):
        approved = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.create_item("Pending Bite", AmuseBouche.Status.PENDING)
        response = self.client.get(reverse("amuse_bouche:feed"))
        self.assertContains(response, approved.title)
        self.assertNotContains(response, "Pending Bite")

    @override_settings(AMUSE_BOUCHE_PUBLIC=True)
    def test_detail_hides_unapproved_item(self):
        pending = self.create_item("Pending Bite", AmuseBouche.Status.PENDING)
        response = self.client.get(reverse("amuse_bouche:detail", kwargs={"slug": pending.slug}))
        self.assertEqual(response.status_code, 404)

    @override_settings(AMUSE_BOUCHE_PUBLIC=True)
    def test_authenticated_user_can_like_and_save(self):
        item = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.client.force_login(self.user)

        self.client.post(reverse("amuse_bouche:toggle_like", kwargs={"slug": item.slug}))
        self.client.post(reverse("amuse_bouche:toggle_save", kwargs={"slug": item.slug}))

        self.assertEqual(ContentReaction.objects.count(), 1)
        self.assertEqual(SavedContent.objects.count(), 1)


class AmuseBoucheGatingTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="author", password="pass")
        self.other_user = user_model.objects.create_user(username="other", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Test Author",
            slug="test-author",
        )

    def create_item(self, title="Pending Bite", status=AmuseBouche.Status.PENDING):
        return AmuseBouche.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_author_can_open_create_form_before_public_launch(self):
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("amuse_bouche:create"))

        self.assertContains(response, "Submit Amuse-Bouche")

    def test_author_can_submit_bite_before_public_launch(self):
        self.client.force_login(self.author_user)

        response = self.client.post(
            reverse("amuse_bouche:create"),
            {
                "title": "Tiny Soda Bread Trick",
                "short_description": "Toast the heel and rub it with salted butter.",
                "content_type": AmuseBouche.ContentType.CHEF_TRICK,
                "cover_image_alt": "",
                "linked_recipe": "",
                "linked_article": "",
                "allow_comments": "on",
                "seo_title": "",
                "seo_description": "",
                "confirm_own_work": "on",
                "confirm_image_rights": "on",
                "confirm_rules": "on",
            },
        )

        item = AmuseBouche.objects.get(title="Tiny Soda Bread Trick")
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.author, self.author)
        self.assertEqual(item.status, AmuseBouche.Status.PENDING)

    def test_author_can_preview_own_pending_bite_before_public_launch(self):
        item = self.create_item()
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("amuse_bouche:detail", kwargs={"slug": item.slug}))

        self.assertContains(response, item.title)

    def test_author_profile_workspace_shows_own_bites_before_public_launch(self):
        item = self.create_item()
        self.client.force_login(self.author_user)

        response = self.client.get(reverse("recipes:author_detail", kwargs={"slug": self.author.slug}))

        self.assertIn(item, response.context["dashboard_amuse_bouche"])
        self.assertContains(response, item.title)

    def test_other_authenticated_user_cannot_preview_approved_bite_before_public_launch(self):
        item = self.create_item("Approved Bite", AmuseBouche.Status.APPROVED)
        self.client.force_login(self.other_user)

        response = self.client.get(reverse("amuse_bouche:detail", kwargs={"slug": item.slug}))

        self.assertEqual(response.status_code, 404)


class AmuseBoucheModerationTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.moderator = user_model.objects.create_user(
            username="moderator",
            password="pass",
            is_staff=True,
        )
        self.reader = user_model.objects.create_user(username="reader", password="pass")
        self.author = RecipeAuthor.objects.create(name="Test Author", slug="test-author")

    def create_item(self, title="Pending Bite", status=AmuseBouche.Status.PENDING):
        return AmuseBouche.objects.create(
            author=self.author,
            title=title,
            short_description="A quick bite.",
            status=status,
        )

    def test_moderation_panel_lists_amuse_bouche_items(self):
        pending = self.create_item("Pending Bite", AmuseBouche.Status.PENDING)
        needs_changes = self.create_item("Needs Work Bite", AmuseBouche.Status.NEEDS_CHANGES)
        rejected = self.create_item("Rejected Bite", AmuseBouche.Status.REJECTED)
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("recipes:moderation_panel"))

        self.assertContains(response, "Amuse-Bouche")
        self.assertIn(pending, response.context["pending_amuse_bouche"])
        self.assertIn(needs_changes, response.context["needs_changes_amuse_bouche"])
        self.assertIn(rejected, response.context["rejected_amuse_bouche"])

    def test_moderator_can_preview_pending_detail(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        response = self.client.get(reverse("amuse_bouche:detail", kwargs={"slug": item.slug}))

        self.assertContains(response, item.title)

    def test_moderator_can_approve_item(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}), {"action": "approve"})
        item.refresh_from_db()

        self.assertEqual(item.status, AmuseBouche.Status.APPROVED)
        self.assertEqual(item.moderation_note, "")
        self.assertEqual(item.moderated_by, self.moderator)
        self.assertIsNotNone(item.moderated_at)
        self.assertIsNotNone(item.published_at)

    def test_reject_requires_note(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        response = self.client.post(
            reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}),
            {"action": "reject"},
        )
        item.refresh_from_db()

        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.status, AmuseBouche.Status.PENDING)

    def test_moderator_can_request_changes(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(
            reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}),
            {"action": "request_changes", "moderation_note": "Clarify image rights."},
        )
        item.refresh_from_db()

        self.assertEqual(item.status, AmuseBouche.Status.NEEDS_CHANGES)
        self.assertEqual(item.moderation_note, "Clarify image rights.")
        self.assertEqual(item.moderated_by, self.moderator)

    def test_moderator_archive_hides_item_from_moderation_queue(self):
        item = self.create_item()
        self.client.force_login(self.moderator)

        self.client.post(reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}), {"action": "delete"})
        item.refresh_from_db()

        self.assertEqual(item.status, AmuseBouche.Status.ARCHIVED)
        response = self.client.get(reverse("recipes:moderation_panel"))
        self.assertNotIn(item, response.context["pending_amuse_bouche"])

    def test_non_moderator_cannot_moderate(self):
        item = self.create_item()
        self.client.force_login(self.reader)

        response = self.client.post(reverse("amuse_bouche:moderate", kwargs={"slug": item.slug}), {"action": "approve"})

        self.assertEqual(response.status_code, 404)


class AmuseBoucheGenerateFromRecipeTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="chef", password="pass")
        self.other_user = user_model.objects.create_user(username="other", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Chef Author",
            slug="chef-author",
        )
        self.recipe = Recipe.objects.create(
            author=self.author,
            title="Boxty Pancakes",
            slug="boxty-pancakes",
            short_description="A classic Irish potato pancake.",
            hero_image_alt_text="Golden boxty on a plate",
            category=Recipe.Category.IRISH_CULINARY_HERITAGE,
            ingredients="500g potatoes",
            method="Grate the potatoes.",
            status=Recipe.Status.APPROVED,
        )
        self.url = reverse("amuse_bouche:generate_from_recipe", kwargs={"slug": self.recipe.slug})

    def test_author_can_generate_bite_from_approved_recipe(self):
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)

        item = AmuseBouche.objects.get(linked_recipe=self.recipe)
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.title, self.recipe.title)
        self.assertEqual(item.author, self.author)
        self.assertEqual(item.status, AmuseBouche.Status.PENDING)
        self.assertEqual(item.content_type, AmuseBouche.ContentType.BEHIND_THE_DISH)
        self.assertEqual(item.linked_recipe, self.recipe)
        self.assertEqual(item.cover_image_alt, self.recipe.hero_image_alt_text)

    def test_duplicate_generation_redirects_to_existing_bite(self):
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.client.post(self.url)

        self.assertEqual(AmuseBouche.objects.filter(linked_recipe=self.recipe).count(), 1)

    def test_unauthenticated_user_cannot_generate(self):
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(AmuseBouche.objects.filter(linked_recipe=self.recipe).exists())

    def test_unrelated_user_cannot_generate(self):
        self.client.force_login(self.other_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_method_not_allowed(self):
        self.client.force_login(self.author_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_draft_recipe_returns_404(self):
        self.recipe.status = Recipe.Status.DRAFT
        self.recipe.save(update_fields=["status"])
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_archived_bite_does_not_block_new_generation(self):
        AmuseBouche.objects.create(
            author=self.author,
            title=self.recipe.title,
            linked_recipe=self.recipe,
            status=AmuseBouche.Status.ARCHIVED,
        )
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.assertEqual(
            AmuseBouche.objects.filter(linked_recipe=self.recipe).exclude(status=AmuseBouche.Status.ARCHIVED).count(),
            1,
        )


class AmuseBoucheGenerateFromArticleTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.author_user = user_model.objects.create_user(username="writer", password="pass")
        self.other_user = user_model.objects.create_user(username="other2", password="pass")
        self.author = RecipeAuthor.objects.create(
            user=self.author_user,
            name="Writer Author",
            slug="writer-author",
        )
        self.article = Article.objects.create(
            author=self.author,
            title="The History of Irish Soda Bread",
            slug="history-irish-soda-bread",
            excerpt="A deep dive into the origins of Irish soda bread.",
            hero_image_alt_text="A golden loaf of soda bread",
            category=Article.Category.BAKING,
            body="Soda bread is a staple of Irish cuisine.",
            status=Article.Status.APPROVED,
            published=timezone.now(),
        )
        self.url = reverse("amuse_bouche:generate_from_article", kwargs={"slug": self.article.slug})

    def test_author_can_generate_bite_from_approved_article(self):
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)

        item = AmuseBouche.objects.get(linked_article=self.article)
        self.assertRedirects(response, item.get_absolute_url())
        self.assertEqual(item.title, self.article.title)
        self.assertEqual(item.author, self.author)
        self.assertEqual(item.status, AmuseBouche.Status.PENDING)
        self.assertEqual(item.content_type, AmuseBouche.ContentType.BEHIND_THE_DISH)
        self.assertEqual(item.linked_article, self.article)
        self.assertEqual(item.cover_image_alt, self.article.hero_image_alt_text)

    def test_duplicate_generation_redirects_to_existing_bite(self):
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.client.post(self.url)

        self.assertEqual(AmuseBouche.objects.filter(linked_article=self.article).count(), 1)

    def test_unauthenticated_user_cannot_generate(self):
        response = self.client.post(self.url)
        self.assertNotEqual(response.status_code, 200)
        self.assertFalse(AmuseBouche.objects.filter(linked_article=self.article).exists())

    def test_unrelated_user_cannot_generate(self):
        self.client.force_login(self.other_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_get_method_not_allowed(self):
        self.client.force_login(self.author_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 405)

    def test_draft_article_returns_404(self):
        self.article.status = Article.Status.DRAFT
        self.article.save(update_fields=["status"])
        self.client.force_login(self.author_user)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 404)

    def test_archived_bite_does_not_block_new_generation(self):
        AmuseBouche.objects.create(
            author=self.author,
            title=self.article.title,
            linked_article=self.article,
            status=AmuseBouche.Status.ARCHIVED,
        )
        self.client.force_login(self.author_user)
        self.client.post(self.url)
        self.assertEqual(
            AmuseBouche.objects.filter(linked_article=self.article).exclude(status=AmuseBouche.Status.ARCHIVED).count(),
            1,
        )
