"""Arena acceptance measurements — GreenBear, 2026-08-15.

The Owner's instruction: audit and accept THE ARENA so its frontend can be
built. These are the measurements an acceptance needs and the existing suite
does not take: the shape of the payload a frontend must bind to, the query and
size budget it costs to produce, and the honesty of an empty hall.

Nothing here writes to production and nothing renders through the shell.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.db import connection
from django.urls import reverse
from django.utils import timezone

from recipes.models import RecipeAuthor

from .models import ChefBattleProfile
from .views import PUBLIC_ARENA_STATE_KEYS


def _seed(chefs=24, spectators=40, tag="a"):
    """A populated hall: enrolled online chefs plus logged-in spectators."""
    User = get_user_model()
    now = timezone.now()
    ranks = list(ChefBattleProfile.Rank)
    made = []
    for i in range(chefs):
        author = RecipeAuthor.objects.create(
            user=User.objects.create_user(f"aa-{tag}-chef-{i}", password="pw"),
            name=f"AA Chef {tag}{i}", slug=f"aa-{tag}-chef-{i}")
        ChefBattleProfile.objects.create(
            author=author, enrolled_at=now, last_seen_at=now,
            rank=ranks[i % len(ranks)].value, rating=1000 + i)
        made.append(author)
    for i in range(spectators):
        author = RecipeAuthor.objects.create(
            user=User.objects.create_user(f"aa-{tag}-fan-{i}", password="pw"),
            name=f"AA Fan {tag}{i}", slug=f"aa-{tag}-fan-{i}")
        ChefBattleProfile.objects.create(author=author, last_seen_at=now)
    return made


@override_settings(CHEF_BATTLE_ENABLED=True)
class ArenaPayloadIsAStableFrontendContractTests(TestCase):
    """What a frontend binds to, stated as a test rather than as a document."""

    def test_the_poll_and_the_first_paint_carry_the_same_keys(self):
        from .views import _build_arena_payload

        payload = _build_arena_payload(viewer_author=None)
        missing = [k for k in PUBLIC_ARENA_STATE_KEYS if k not in payload]
        self.assertEqual(missing, [], "the poll advertises keys the builder never produces")

    def test_every_documented_key_has_its_documented_type(self):
        from .views import _build_arena_payload

        payload = _build_arena_payload(viewer_author=None)
        expected = {
            "rings": dict, "spectators": list, "center": dict, "upcoming": list,
            "latest_result": (dict, type(None)), "crown_streak": int,
            "crown_ladder": list, "recent_gifts": list,
            "metrics": dict, "phase_rail": list, "geometry": dict,
            "vip_sponsors": list, "spirit_count": int, "server_time": str,
        }
        for key, kind in expected.items():
            with self.subTest(key=key):
                self.assertIsInstance(payload[key], kind)

    def test_an_empty_hall_says_so_instead_of_inventing_a_battle(self):
        """A17's rule, checked at the payload rather than in the pixels."""
        from .views import _build_arena_payload

        payload = _build_arena_payload(viewer_author=None)
        # "empty" is what the code says and the spec's word was "open";
        # the code is the decision (Owner, standing rule) - what matters for a
        # frontend is that the honest empty state is DECLARED, not drawn as a
        # battle. Pinned here so the word cannot drift again unnoticed.
        self.assertEqual(payload["center"]["type"], "empty")
        self.assertEqual(payload["upcoming"], [])
        self.assertEqual(payload["spirit_count"], 0)
        self.assertEqual(sum(len(v) for v in payload["rings"].values()), 0)

    def test_the_geometry_is_the_eleven_ring_octagon_the_plan_froze(self):
        from .selectors import get_arena_geometry

        geometry = get_arena_geometry()
        self.assertEqual(geometry["sides"], 8)
        ranks = [r for r in geometry["rings"] if r["kind"] == "rank"]
        self.assertEqual(len(ranks), 8, "the eight rank rings are the frozen floor")
        self.assertEqual([r["index"] for r in ranks], list(range(1, 9)))
        self.assertEqual(geometry["rings"][0]["kind"], "stage")
        self.assertGreater(geometry["spectator_oval"]["capacity"], 0)
        self.assertGreater(geometry["balconies"]["capacity"], 0)


@override_settings(CHEF_BATTLE_ENABLED=True)
class ArenaCostsWhatAFrontendCanAffordTests(TestCase):
    """The poll runs every twenty seconds for every viewer at once. Its cost is
    a product decision, so it is measured and pinned rather than assumed."""

    QUERY_BUDGET_POLL = 60
    QUERY_BUDGET_PAGE = 80
    SIZE_BUDGET_KB = 250

    @classmethod
    def setUpTestData(cls):
        cls.chefs = _seed(chefs=24, spectators=40)

    def _poll(self, client):
        return client.post(reverse("chef_battle:arena_state"))

    def test_the_poll_does_not_scale_its_queries_with_the_crowd(self):
        """The real N+1 test: measure at two crowd sizes and compare, so a
        constant-but-large number does not read as a leak and a leak cannot
        hide behind a generous budget."""
        User = get_user_model()
        client = Client()
        user = User.objects.create_user("aa-watcher", password="pw")
        RecipeAuthor.objects.create(user=user, name="AA Watcher", slug="aa-watcher")
        client.force_login(user)

        with CaptureQueriesContext(connection) as small:
            self._poll(client)
        before = len(small.captured_queries)

        _seed(chefs=24, spectators=40, tag="b")   # double the hall

        with CaptureQueriesContext(connection) as large:
            self._poll(client)
        after = len(large.captured_queries)

        print(f"[MEASURED] poll queries: {before} (24 chefs/40 fans) -> {after} (48/80)")
        self.assertLessEqual(
            after, before + 5,
            f"the poll costs {before} queries with one hall and {after} with two - "
            "it scales with the crowd")

    def test_the_poll_stays_inside_its_query_budget(self):
        User = get_user_model()
        client = Client()
        user = User.objects.create_user("aa-watcher-2", password="pw")
        RecipeAuthor.objects.create(user=user, name="AA Watcher 2", slug="aa-watcher-2")
        client.force_login(user)

        with CaptureQueriesContext(connection) as captured:
            response = self._poll(client)
        self.assertEqual(response.status_code, 200)
        print(f"[MEASURED] poll queries: {len(captured.captured_queries)}")
        self.assertLessEqual(
            len(captured.captured_queries), self.QUERY_BUDGET_POLL,
            f"the arena poll now costs {len(captured.captured_queries)} queries")

    def test_the_payload_stays_inside_its_size_budget(self):
        client = Client()
        response = self._poll(client)
        size_kb = len(response.content) / 1024
        import json
        data = json.loads(response.content)
        parts = sorted(((len(json.dumps(v)) / 1024, k) for k, v in data.items()), reverse=True)
        print(f"[MEASURED] poll payload: {size_kb:.1f} KB; "
              + ", ".join(f"{k}={kb:.1f}KB" for kb, k in parts[:6]))
        self.assertLess(
            size_kb, self.SIZE_BUDGET_KB,
            f"the arena poll returns {size_kb:.1f} KB every twenty seconds")

    def test_the_page_stays_inside_its_query_budget(self):
        client = Client()
        with CaptureQueriesContext(connection) as captured:
            response = client.get(reverse("chef_battle:arena"))
        self.assertEqual(response.status_code, 200)
        print(f"[MEASURED] page queries: {len(captured.captured_queries)}, html {len(response.content)/1024:.0f} KB")
        self.assertLessEqual(
            len(captured.captured_queries), self.QUERY_BUDGET_PAGE,
            f"the arena page now costs {len(captured.captured_queries)} queries")


class ArenaStaysInvisibleUntilTheOwnerOpensItTests(TestCase):
    """The launch latch is one-way, and every Arena surface sits behind it."""

    def test_every_arena_endpoint_is_a_404_while_the_latch_is_shut(self):
        client = Client()
        with override_settings(CHEF_BATTLE_ENABLED=False):
            for name, method in (
                ("chef_battle:arena", "get"),
                ("chef_battle:arena_battle_popup", "get"),
                ("chef_battle:arena_state", "post"),
                ("chef_battle:arena_ping", "post"),
                ("chef_battle:arena_take_seat", "post"),
            ):
                with self.subTest(endpoint=name):
                    response = getattr(client, method)(reverse(name))
                    self.assertEqual(
                        response.status_code, 404,
                        f"{name} answered {response.status_code}, which confirms it exists")
