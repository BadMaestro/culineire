class HtmlNoCacheMiddleware:
    """Set Cache-Control: no-cache on HTML responses.

    Prevents iOS Safari (and other browsers) from serving stale HTML pages
    from their HTTP cache after a site deploy.  Static assets are unaffected
    — they use content-hashed filenames and are managed by the service worker.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if "text/html" in response.get("Content-Type", ""):
            if "Cache-Control" not in response:
                response["Cache-Control"] = "no-cache, must-revalidate"
        return response
