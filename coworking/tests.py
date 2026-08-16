from io import StringIO

from django.core.management import call_command
from django.db import connection
from django.test import TestCase, TransactionTestCase

from coworking.models import COWORK_INBOX_CHANNEL, CoworkingAgent, CoworkingMessage


class CoworkingMessageTests(TestCase):
    def setUp(self):
        self.bolt = CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        self.gb = CoworkingAgent.objects.create(agent_id="greenbear", label="GreenBear")

    def test_send_with_instances(self):
        m = CoworkingMessage.send(
            from_agent=self.gb, to_agent=self.bolt, body="hook please", subject="Phase 6"
        )
        self.assertEqual(m.from_agent, self.gb)
        self.assertEqual(m.to_agent, self.bolt)
        self.assertFalse(m.is_read)

    def test_send_with_agent_id_strings(self):
        m = CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="hi")
        self.assertEqual(m.from_agent_id, "greenbear")
        self.assertEqual(m.to_agent_id, "bolt")

    def test_unread_for_and_mark_read(self):
        CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="one")
        m2 = CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="two")
        # A message addressed elsewhere must not leak into bolt's inbox.
        CoworkingMessage.send(from_agent="bolt", to_agent="greenbear", body="not for bolt")

        unread = list(CoworkingMessage.unread_for("bolt"))
        self.assertEqual(len(unread), 2)
        self.assertEqual([m.body for m in unread], ["one", "two"])  # oldest first

        m2.mark_read()
        self.assertTrue(CoworkingMessage.objects.get(pk=m2.pk).is_read)
        self.assertEqual(CoworkingMessage.unread_for("bolt").count(), 1)


class AgentInboxCommandTests(TestCase):
    def setUp(self):
        CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        CoworkingAgent.objects.create(agent_id="greenbear", label="GreenBear")
        self.m1 = CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="first")
        self.m2 = CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="second")

    def _run(self, *args):
        out = StringIO()
        call_command("agent_inbox", "bolt", *args, stdout=out)
        return out.getvalue()

    def test_since_watermark_returns_only_newer(self):
        out = self._run("--since", str(self.m1.id))
        self.assertNotIn("first", out)
        self.assertIn("second", out)
        # Each line starts with the message id for the poller's watermark.
        self.assertTrue(out.strip().startswith(str(self.m2.id) + "\t"))

    def test_unread_lists_all_unread(self):
        out = self._run("--unread")
        self.assertIn("first", out)
        self.assertIn("second", out)

    def test_mark_read_clears_inbox(self):
        self._run("--unread", "--mark-read")
        self.assertEqual(CoworkingMessage.unread_for("bolt").count(), 0)


class OwnerPasteBoxTests(TestCase):
    """The owner paste-box view: any-length paste routed to an agent's inbox."""

    def setUp(self):
        from django.contrib.auth import get_user_model
        from django.test import Client
        CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        CoworkingAgent.objects.create(agent_id="greenbear", label="GreenBear")
        U = get_user_model()
        self.owner = U.objects.create_superuser("paste-owner", "o@o.com", "pw")
        self.client = Client()
        self.client.force_login(self.owner)

    def test_dashboard_shows_paste_form(self):
        r = self.client.get("/coworking/")
        self.assertEqual(r.status_code, 200)
        h = r.content.decode()
        self.assertIn('/coworking/send-message/', h)
        self.assertIn('name="body"', h)
        self.assertIn('name="to_agent"', h)

    def test_paste_creates_message_no_truncation(self):
        big = "GB transcript line\n" * 5000  # ~95k chars, far beyond any Telegram limit
        r = self.client.post("/coworking/send-message/", {
            "to_agent": "bolt", "subject": "GB last transcript", "body": big,
        })
        self.assertEqual(r.status_code, 302)
        m = CoworkingMessage.objects.get(to_agent_id="bolt", subject="GB last transcript")
        self.assertEqual(m.from_agent_id, "owner")
        self.assertEqual(m.body, big.strip())  # only surrounding whitespace trimmed, body intact

    def test_paste_requires_recipient_and_body(self):
        r = self.client.post("/coworking/send-message/", {"to_agent": "", "body": ""})
        self.assertEqual(r.status_code, 302)
        self.assertFalse(CoworkingMessage.objects.exists())

    def test_non_moderator_blocked(self):
        from django.contrib.auth import get_user_model
        from django.test import Client
        U = get_user_model()
        U.objects.create_user("nobody", "n@n.com", "pw")
        c = Client(); c.login(username="nobody", password="pw")
        self.assertEqual(c.get("/coworking/").status_code, 404)
        self.assertEqual(c.post("/coworking/send-message/", {"to_agent": "bolt", "body": "x"}).status_code, 404)


class CoworkingAgentListCoercionTests(TestCase):
    """A string in a list-typed JSON field made the dashboard render it one
    character per <li>. save() must coerce a stray string/None into a list."""

    def test_string_blocker_is_coerced_to_a_single_item_list(self):
        a = CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        a.blockers = "Weekly usage limit"
        a.key_facts = ""
        a.save()
        a.refresh_from_db()
        self.assertEqual(a.blockers, ["Weekly usage limit"])
        self.assertEqual(a.key_facts, [])

    def test_proper_list_is_left_untouched(self):
        a = CoworkingAgent.objects.create(
            agent_id="greenbear", label="GB",
            key_facts=["one", "two"], blockers=[],
        )
        a.save()
        a.refresh_from_db()
        self.assertEqual(a.key_facts, ["one", "two"])
        self.assertEqual(a.blockers, [])


class InboxWaitTests(TestCase):
    """agent_inbox --wait: return immediately when mail is already waiting, and
    return empty (not hang) when the timeout elapses with nothing."""

    def setUp(self):
        CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        CoworkingAgent.objects.create(agent_id="greenbear", label="GreenBear")

    def test_wait_returns_immediately_when_unread_exists(self):
        import time as _t
        CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="already here")
        out = StringIO()
        start = _t.monotonic()
        # A pre-existing unread short-circuits before any LISTEN connection, so
        # this must return at once, well under the 30s timeout.
        call_command("agent_inbox", "bolt", "--wait", "--timeout", "30", stdout=out)
        self.assertLess(_t.monotonic() - start, 5.0)
        self.assertIn("already here", out.getvalue())

    def test_wait_returns_empty_after_timeout(self):
        import time as _t
        out = StringIO()
        start = _t.monotonic()
        call_command("agent_inbox", "bolt", "--wait", "--timeout", "1", stdout=out)
        elapsed = _t.monotonic() - start
        self.assertGreaterEqual(elapsed, 1.0)
        self.assertLess(elapsed, 6.0)
        self.assertEqual(out.getvalue().strip(), "")


class InboxNotifyTests(TransactionTestCase):
    """The doorbell itself: a LISTENer wakes on the NOTIFY that send() fires,
    carrying the recipient's agent_id as the payload."""

    def test_send_fires_notify_to_recipient_channel(self):
        if connection.vendor != "postgresql":
            self.skipTest("LISTEN/NOTIFY is Postgres-only")
        import psycopg
        CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        CoworkingAgent.objects.create(agent_id="greenbear", label="GreenBear")

        sd = connection.settings_dict
        conninfo = psycopg.conninfo.make_conninfo(
            dbname=sd["NAME"], user=sd.get("USER") or None,
            password=sd.get("PASSWORD") or None, host=sd.get("HOST") or None,
            port=str(sd["PORT"]) if sd.get("PORT") else None,
        )
        with psycopg.connect(conninfo, autocommit=True) as listener:
            listener.execute(f'LISTEN "{COWORK_INBOX_CHANNEL}"')
            # LISTEN is live before the message is sent, so its on_commit NOTIFY
            # is delivered to this connection.
            CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="wake up")
            payloads = []
            for note in listener.notifies(timeout=5):
                payloads.append(note.payload)
                break
        self.assertEqual(payloads, ["bolt"])


class AgentSendCommandTests(TestCase):
    """The sender must refuse everything that silently loses a message."""

    def _run(self, **kwargs):
        from io import StringIO

        out = StringIO()
        call_command("agent_send", stdout=out, **kwargs)
        return out.getvalue()

    def _body(self, text):
        import tempfile

        handle = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        handle.write(text)
        handle.close()
        return handle.name

    def _json_body(self, **fields):
        import json

        payload = json.dumps({"from": "GreenBear", "to": "Bolt", **fields})
        return self._body(payload), payload

    def test_sends_a_message_from_a_file(self):
        path, payload = self._json_body(subject="Subj", message="hello from a file")
        out = self._run(from_agent="greenbear", to_agent="bolt", body_file=path, subject="Subj")
        self.assertIn("SENT", out)
        message = CoworkingMessage.objects.latest("id")
        self.assertEqual(message.from_agent.agent_id, "greenbear")
        self.assertEqual(message.to_agent.agent_id, "bolt")
        self.assertEqual(message.body, payload)

    def test_prose_is_refused_because_a_body_is_a_json_object(self):
        """AGENTS.md 5. A JSON body satisfies the ASCII rule by construction."""
        from django.core.management.base import CommandError

        path = self._body("hello from a file")
        with self.assertRaises(CommandError) as caught:
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        self.assertIn("not JSON", str(caught.exception))
        self.assertFalse(CoworkingMessage.objects.exists())

    def test_a_bare_json_string_is_refused(self):
        """Valid JSON, no field names — the reader would have to guess."""
        from django.core.management.base import CommandError

        path = self._body('"just a string"')
        with self.assertRaises(CommandError) as caught:
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        self.assertIn("not a JSON object", str(caught.exception))

    def test_cyrillic_between_agents_is_refused_and_the_field_is_named(self):
        """AGENTS.md 5: the language between agents is English."""
        from django.core.management.base import CommandError

        path, _ = self._json_body(subject="Subj", message="Привет")
        with self.assertRaises(CommandError) as caught:
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        message = str(caught.exception)
        self.assertIn("language between agents is English", message)
        self.assertIn("body.message", message)      # WHERE, not just THAT
        self.assertFalse(CoworkingMessage.objects.exists())

    def test_the_owner_may_be_quoted_verbatim_in_russian(self):
        """Translating his instruction would change it, so one field is exempt."""
        path, payload = self._json_body(
            message="Relaying his exact wording below.",
            owner_verbatim="верни 42",
        )
        self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        self.assertEqual(CoworkingMessage.objects.latest("id").body, payload)

    def test_cyrillic_is_still_refused_alongside_a_legitimate_quote(self):
        """The exemption is one field, not an amnesty for the whole message."""
        from django.core.management.base import CommandError

        path, _ = self._json_body(
            message="Это мой текст",
            owner_verbatim="верни 42",
        )
        with self.assertRaises(CommandError) as caught:
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        self.assertIn("body.message", str(caught.exception))
        self.assertNotIn("owner_verbatim", str(caught.exception).split("If this is")[0])

    def test_a_raw_non_ascii_body_is_refused(self):
        """AGENTS.md 5: the body reaches the wire as pure ASCII.

        This test used to assert the opposite — that "Привет, шеф" written to a
        file arrives intact — and it passed, because the file path really does
        protect the bytes from the shell's codepage. That is a true fact about
        the file, and it was the wrong acceptance criterion: section 5 does not
        ask for non-ASCII to survive the shell, it asks for non-ASCII not to be
        on the wire at all, carried as \\uXXXX escapes instead. The old test let
        message #3473 go out on 2026-08-04 with a stray character in it.

        The file is still the right transport, and the test below proves it:
        the escaped form arrives byte for byte.
        """
        from django.core.management.base import CommandError

        path = self._body("Привет, шеф")
        with self.assertRaises(CommandError) as caught:
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        message = str(caught.exception)
        self.assertIn("not ASCII", message)
        self.assertIn("NOTHING WAS SENT", message)
        # The refusal names where to look, not just that it refused.
        self.assertIn("line 1", message)
        self.assertIn("\\u041f", message)  # П
        self.assertFalse(CoworkingMessage.objects.exists())

    def test_one_stray_character_anywhere_is_refused(self):
        """The real defect was a single character inside a code sample."""
        from django.core.management.base import CommandError

        path = self._body(
            "All ASCII here.\nAnd here.\ndocument.body.innerHTML.indexOf('â')\n"
        )
        with self.assertRaises(CommandError) as caught:
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        self.assertIn("line 3", str(caught.exception))
        self.assertFalse(CoworkingMessage.objects.exists())

    def test_the_escaped_form_goes_through_the_file_intact(self):
        """Escaping is necessary and no longer sufficient.

        This asserted the compliant path when ASCII was the only rule: json.dumps
        emits \\uXXXX by default, so Russian could ride through legally. The Owner
        added the language rule on 2026-08-04 and it is not legal any more —
        between agents the language is English, and Russian survives only as his
        own words in `owner_verbatim`. The transport half of the claim is still
        true and still worth pinning: the escaped form crosses the file byte for
        byte and decodes back to the original.
        """
        import json

        payload = json.dumps({"message": "Owner said this, verbatim:",
                              "owner_verbatim": "Привет, шеф"})
        self.assertTrue(payload.isascii())
        path = self._body(payload)
        self._run(from_agent="greenbear", to_agent="bolt", body_file=path)
        stored = CoworkingMessage.objects.latest("id").body
        self.assertEqual(stored, payload)
        self.assertEqual(json.loads(stored)["owner_verbatim"], "Привет, шеф")

    def test_a_capitalised_id_is_refused(self):
        from django.core.management.base import CommandError

        path = self._body("body")
        with self.assertRaises(CommandError):
            self._run(from_agent="GreenBear", to_agent="bolt", body_file=path)

    def test_an_empty_body_is_refused(self):
        from django.core.management.base import CommandError

        path = self._body("   \n  ")
        with self.assertRaises(CommandError):
            self._run(from_agent="greenbear", to_agent="bolt", body_file=path)

    def test_sending_to_yourself_is_refused(self):
        from django.core.management.base import CommandError

        path = self._body("body")
        with self.assertRaises(CommandError):
            self._run(from_agent="greenbear", to_agent="greenbear", body_file=path)


class CoworkingListSyncTests(TestCase):
    """coworking_list is the one command an agent runs to see who is working on
    what right now. It exists because a stale status row and unread mail both
    read as silence, and silence was mistaken for synchronisation on
    2026-08-16: four messages sat unread while their sender believed the
    recipient had read them and was working alongside him, not in parallel on
    the same ground."""

    def setUp(self):
        self.bolt = CoworkingAgent.objects.create(agent_id="bolt", label="Bolt")
        self.gb = CoworkingAgent.objects.create(agent_id="greenbear", label="GreenBear")

    def _run(self, **kwargs):
        out = StringIO()
        call_command("coworking_list", stdout=out, **kwargs)
        return out.getvalue()

    def test_unread_mail_is_reported_per_recipient_not_globally(self):
        CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="one")
        CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="two")
        out = self._run()
        self.assertIn("bolt", out)
        self.assertIn("2 UNREAD", out)
        # greenbear received nothing, so his line must say zero, not be silent.
        self.assertRegex(out, r"greenbear\s+0 unread")

    def test_a_read_message_stops_counting_as_unread(self):
        m = CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="one")
        m.mark_read()
        out = self._run()
        self.assertRegex(out, r"bolt\s+0 unread")

    def test_stale_active_row_is_flagged_rather_than_trusted(self):
        from datetime import timedelta

        from django.utils import timezone

        self.bolt.status = CoworkingAgent.Status.ACTIVE
        self.bolt.last_seen = timezone.now() - timedelta(hours=6)
        self.bolt.save()
        out = self._run()
        self.assertIn("STALE", out)

    def test_a_recently_active_row_is_not_flagged(self):
        self.bolt.status = CoworkingAgent.Status.ACTIVE
        self.bolt.save()  # last_seen defaults to auto_now-adjacent recent value
        from django.utils import timezone

        self.bolt.last_seen = timezone.now()
        self.bolt.save()
        out = self._run()
        self.assertNotIn("STALE", out)

    def test_idle_agent_is_never_flagged_stale_regardless_of_age(self):
        from datetime import timedelta

        from django.utils import timezone

        self.bolt.status = CoworkingAgent.Status.IDLE
        self.bolt.last_seen = timezone.now() - timedelta(days=30)
        self.bolt.save()
        out = self._run()
        self.assertNotIn("STALE", out)

    def test_no_lock_file_reports_free_rather_than_crashing(self):
        # The test settings BASE_DIR points at the real repo, whose lock file
        # this session already released - so this exercises the true no-lock
        # path rather than a synthetic one.
        out = self._run()
        self.assertIn("DEPLOY LOCK:", out)

    def test_deploy_lock_holder_is_shown_when_the_file_exists(self):
        import tempfile
        from pathlib import Path
        from unittest import mock

        with tempfile.TemporaryDirectory() as tmp:
            lock_dir = Path(tmp) / ".agent-chat"
            lock_dir.mkdir()
            (lock_dir / "deploy.lock").write_text(
                "agent: Bolt\nstarted_utc: 2026-08-16T00:00Z\nversion: 2.5.9999\n"
                "commit: pending\ntask: testing the lock reader\n",
                encoding="utf-8",
            )
            with mock.patch("django.conf.settings.BASE_DIR", Path(tmp)):
                out = self._run()
        self.assertIn("HELD BY Bolt", out)
        self.assertIn("2.5.9999", out)

    def test_agent_filter_narrows_the_agent_list_only(self):
        CoworkingMessage.send(from_agent="greenbear", to_agent="bolt", body="one")
        out = self._run(agent="greenbear")
        agents_section, _, mail_section = out.partition("UNREAD MAIL")
        self.assertIn("greenbear", agents_section)
        self.assertNotIn("bolt", agents_section)
        # Mail totals must still cover everyone, not just the filtered agent.
        self.assertIn("bolt", mail_section)
        self.assertIn("1 UNREAD", mail_section)

    def test_shared_memory_is_printed_so_a_fact_told_only_in_mail_is_not_the_goal(self):
        from coworking.models import CoworkingSharedMemory

        shared = CoworkingSharedMemory.load()
        shared.open_questions = ["Who takes T22?"]
        shared.completed_today = ["v2.5.1080 shipped"]
        shared.project_memory = ["Octagon geometry is frozen"]
        shared.save()

        out = self._run()
        self.assertIn("SHARED MEMORY", out)
        self.assertIn("Who takes T22?", out)
        self.assertIn("v2.5.1080 shipped", out)
        self.assertIn("Octagon geometry is frozen", out)

    def test_empty_shared_memory_says_none_recorded_rather_than_being_silent(self):
        out = self._run()
        self.assertIn("open questions: none recorded", out)
        self.assertIn("completed today: none recorded", out)
        self.assertIn("standing facts: none recorded", out)
