import secrets


class CspNonceMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.csp_nonce = secrets.token_urlsafe(16)
        response = self.get_response(request)
        nonce = request.csp_nonce
        response["Content-Security-Policy"] = (
            f"default-src 'self'; "
            f"script-src 'self' 'nonce-{nonce}' https://challenges.cloudflare.com; "
            f"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            f"font-src 'self' https://fonts.gstatic.com; "
            f"img-src 'self' data: blob:; "
            f"connect-src 'self'; "
            f"frame-src https://challenges.cloudflare.com; "
            f"frame-ancestors 'none'; "
            f"object-src 'none'; "
            f"base-uri 'self'; "
            f"form-action 'self';"
        )
        response["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response["X-XSS-Protection"] = "1; mode=block"
        return response
