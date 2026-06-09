import json

from django.test import TestCase, override_settings


class ApiCatalogTest(TestCase):
    def test_returns_linkset_json(self):
        r = self.client.get("/.well-known/api-catalog")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/linkset+json", r["Content-Type"])
        data = json.loads(r.content)
        self.assertIn("linkset", data)

    def test_contains_culineire_anchor(self):
        r = self.client.get("/.well-known/api-catalog")
        data = json.loads(r.content)
        anchors = [entry.get("anchor") for entry in data["linkset"]]
        self.assertIn("https://culineire.ie", anchors)


class McpServerCardTest(TestCase):
    def test_returns_json(self):
        r = self.client.get("/.well-known/mcp/server-card.json")
        self.assertEqual(r.status_code, 200)
        self.assertIn("application/json", r["Content-Type"])
        data = json.loads(r.content)
        self.assertEqual(data["serverInfo"]["name"], "CulinEire")

    def test_has_capabilities(self):
        r = self.client.get("/.well-known/mcp/server-card.json")
        data = json.loads(r.content)
        self.assertIn("capabilities", data)
        self.assertIn("recipes", data["capabilities"]["resources"])


class AgentSkillsIndexTest(TestCase):
    def test_returns_json(self):
        r = self.client.get("/.well-known/agent-skills/index.json")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertIn("skills", data)

    def test_has_browse_recipes_skill(self):
        r = self.client.get("/.well-known/agent-skills/index.json")
        data = json.loads(r.content)
        names = [s["name"] for s in data["skills"]]
        self.assertIn("browse-recipes", names)

    def test_skills_have_sha256(self):
        r = self.client.get("/.well-known/agent-skills/index.json")
        data = json.loads(r.content)
        for skill in data["skills"]:
            self.assertIn("sha256", skill)
            self.assertEqual(len(skill["sha256"]), 64)


class AuthMdTest(TestCase):
    def test_returns_markdown(self):
        r = self.client.get("/auth.md")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/markdown", r["Content-Type"])
        self.assertIn(b"CulinEire", r.content)

    def test_has_auth_md_heading(self):
        r = self.client.get("/auth.md")
        self.assertIn(b"# Auth.md", r.content)


class OAuthProtectedResourceTest(TestCase):
    def test_returns_json(self):
        r = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertEqual(data["resource"], "https://culineire.ie")

    def test_bearer_methods_includes_header(self):
        r = self.client.get("/.well-known/oauth-protected-resource")
        data = json.loads(r.content)
        self.assertIn("header", data["bearer_methods_supported"])

    def test_authorization_servers_lists_issuer(self):
        r = self.client.get("/.well-known/oauth-protected-resource")
        data = json.loads(r.content)
        self.assertIn("https://culineire.ie", data["authorization_servers"])


class OAuthAuthorizationServerTest(TestCase):
    def test_returns_json(self):
        r = self.client.get("/.well-known/oauth-authorization-server")
        self.assertEqual(r.status_code, 200)
        data = json.loads(r.content)
        self.assertIn("issuer", data)

    def test_has_agent_auth_block(self):
        r = self.client.get("/.well-known/oauth-authorization-server")
        data = json.loads(r.content)
        self.assertIn("agent_auth", data)
        self.assertIn("identity_types_supported", data["agent_auth"])

    def test_openid_configuration_alias(self):
        r = self.client.get("/.well-known/openid-configuration")
        self.assertEqual(r.status_code, 200)


class AgentLinkHeadersTest(TestCase):
    def test_link_header_on_homepage(self):
        r = self.client.get("/")
        self.assertIn("Link", r)
        link = r["Link"]
        self.assertIn("api-catalog", link)
        self.assertIn("mcp-server-card", link)

    def test_link_header_on_404(self):
        r = self.client.get("/this-page-does-not-exist-xyz/")
        self.assertNotIn("Link", r)


class MarkdownNegotiationTest(TestCase):
    def test_html_returned_without_accept_header(self):
        r = self.client.get("/")
        self.assertIn("text/html", r["Content-Type"])

    def test_markdown_returned_with_accept_header(self):
        try:
            import html2text  # noqa: F401
        except ImportError:
            self.skipTest("html2text not installed")
        r = self.client.get("/", HTTP_ACCEPT="text/markdown")
        self.assertIn("text/markdown", r["Content-Type"])
        self.assertIn("X-Markdown-Tokens", r)
        self.assertTrue(int(r["X-Markdown-Tokens"]) > 0)
