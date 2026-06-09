import json

from django.http import HttpResponse


def _json(data, content_type="application/json"):
    return HttpResponse(
        json.dumps(data, indent=2),
        content_type=content_type,
    )


def api_catalog(request):
    data = {
        "linkset": [
            {
                "anchor": "https://culineire.ie",
                "service-doc": [{"href": "https://culineire.ie/about/", "type": "text/html"}],
                "describedby": [
                    {"href": "https://culineire.ie/sitemap.xml", "type": "application/xml"}
                ],
            }
        ]
    }
    return _json(data, content_type="application/linkset+json")


def mcp_server_card(request):
    data = {
        "serverInfo": {
            "name": "CulinEire",
            "version": "1.0.0",
            "description": (
                "CulinEire is an Irish food and recipe website featuring traditional "
                "and modern Irish cuisine, articles, and food culture."
            ),
            "website": "https://culineire.ie",
        },
        "transport": None,
        "capabilities": {
            "resources": {
                "recipes": {
                    "description": "Browse and search Irish recipes",
                    "url": "https://culineire.ie/recipes/",
                },
                "articles": {
                    "description": "Food culture articles and guides",
                    "url": "https://culineire.ie/articles/",
                },
                "sitemap": {
                    "description": "Full sitemap for content discovery",
                    "url": "https://culineire.ie/sitemap.xml",
                },
            }
        },
    }
    return _json(data)


def agent_skills_index(request):
    data = {
        "$schema": "https://agentskills.io/schema/v0.2.0/index.json",
        "skills": [
            {
                "name": "browse-recipes",
                "type": "link",
                "description": "Browse Irish recipes by category, difficulty, or search term",
                "url": "https://culineire.ie/recipes/",
            },
            {
                "name": "browse-articles",
                "type": "link",
                "description": "Read articles about Irish food culture, history, and ingredients",
                "url": "https://culineire.ie/articles/",
            },
        ],
    }
    return _json(data)


def oauth_protected_resource(request):
    data = {
        "resource": "https://culineire.ie",
        "resource_name": "CulinEire",
        "resource_documentation": "https://culineire.ie/auth.md",
        "authorization_servers": ["https://culineire.ie"],
        "scopes_supported": [],
        "bearer_methods_supported": ["header"],
        "introspection_endpoint_auth_methods_supported": [],
        "dpop_signing_alg_values_supported": [],
    }
    return _json(data)


def oauth_authorization_server(request):
    data = {
        "issuer": "https://culineire.ie",
        "service_documentation": "https://culineire.ie/auth.md",
        "ui_locales_supported": ["en"],
        "op_policy_uri": "https://culineire.ie/privacy/",
        "grant_types_supported": [],
        "response_types_supported": [],
        "agent_auth": {
            "skill": "https://isitagentready.com/.well-known/agent-skills/auth-md/SKILL.md",
            "register_uri": None,
            "identity_types_supported": ["anonymous"],
            "anonymous": {
                "credential_types_supported": [],
                "claim_uri": None,
            },
            "registration_required": False,
            "notes": (
                "CulinEire is a fully public website. No registration, authentication, "
                "or credentials are required. AI agents may access all public URLs freely."
            ),
        },
    }
    return _json(data)


def auth_md(request):
    content = """# auth.md

## CulinEire — Agent Access Guide

CulinEire (https://culineire.ie) is a public Irish food and recipe website
celebrating Irish culinary heritage.

## agent_auth

```yaml
skill: https://isitagentready.com/.well-known/agent-skills/auth-md/SKILL.md
register_uri: none
identity_types_supported:
  - anonymous
anonymous:
  credential_types_supported: []
  claim_uri: none
registration_required: false
access_type: public
notes: >
  CulinEire is a fully public website. No registration, authentication,
  or credentials are required to access recipes, articles, or any other
  public content. AI agents may access all public URLs freely.
```

## Access Policy

All public pages are freely accessible to AI agents and crawlers in accordance
with the permissions declared in `/robots.txt`.

## Content Permissions

See `/robots.txt` for per-bot Content-Signal directives that specify whether
content may be used for training, summarisation, or other purposes.

## Available Resources

| Resource | URL | Description |
|----------|-----|-------------|
| Recipes | /recipes/ | Browse and search Irish recipes |
| Articles | /articles/ | Irish food culture articles |
| Sitemap | /sitemap.xml | Full content index |
| API Catalog | /.well-known/api-catalog | Machine-readable resource index |
| MCP Server Card | /.well-known/mcp/server-card.json | MCP discovery |
| Agent Skills | /.well-known/agent-skills/index.json | Available agent actions |
| OAuth Resource | /.well-known/oauth-protected-resource | Resource metadata |
| Auth.md | /auth.md | Agent authentication guide |

## Authentication

No authentication is required to access public content.

## Contact

For questions about agent access, contact the site owner via the About page:
https://culineire.ie/messages/contact/
"""
    return HttpResponse(content, content_type="text/markdown; charset=utf-8")
