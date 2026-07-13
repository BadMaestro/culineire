from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from coworking.models import CoworkingAgent, CoworkingMessage


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
