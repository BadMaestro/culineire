_LINK_HEADERS = ", ".join([
    '</.well-known/api-catalog>; rel="api-catalog"',
    '</.well-known/mcp/server-card.json>; rel="mcp-server-card"',
    '</.well-known/agent-skills/index.json>; rel="agent-skills"',
])


class AgentLinkHeadersMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if response.status_code == 200:
            response["Link"] = _LINK_HEADERS
        return response


class MarkdownNegotiationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        accept = request.META.get("HTTP_ACCEPT", "")
        if "text/markdown" not in accept:
            return response

        content_type = response.get("Content-Type", "")
        if "text/html" not in content_type or response.status_code != 200:
            return response

        try:
            import html2text
            h = html2text.HTML2Text()
            h.ignore_links = False
            h.ignore_images = True
            h.body_width = 0
            html = response.content.decode("utf-8", errors="replace")
            md = h.handle(html)
            response.content = md.encode("utf-8")
            response["Content-Type"] = "text/markdown; charset=utf-8"
            if "Content-Length" in response:
                del response["Content-Length"]
        except ImportError:
            pass

        return response
