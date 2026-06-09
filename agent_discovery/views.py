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


def auth_md(request):
    content = """# CulinEire — Agent Access Guide

CulinEire (https://culineire.ie) is a public Irish food and recipe website.

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

## Authentication

No authentication is required to access public content.

## Contact

For questions about agent access, contact the site owner via the About page.
"""
    return HttpResponse(content, content_type="text/markdown; charset=utf-8")
