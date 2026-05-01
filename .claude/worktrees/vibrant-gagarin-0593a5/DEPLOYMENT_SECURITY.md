# Deployment Security

Use environment variables to control Django's deployment posture.

## Local development example

```env
DJANGO_ENV=development
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,::1,culineire.localhost
DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://culineire.localhost:8000
DJANGO_SERVE_STATIC_LOCALLY=True
DJANGO_SERVE_MEDIA_LOCALLY=True
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SECURE_HSTS_SECONDS=0
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False
DJANGO_SECURE_HSTS_PRELOAD=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_SECURE_PROXY_SSL_HEADER=False
DJANGO_LOG_LEVEL=DEBUG
DJANGO_LOG_DIR=logs
```

## Production example

```env
DJANGO_ENV=production
DJANGO_SECRET_KEY=replace-with-a-long-random-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=culineire.ie,www.culineire.ie
DJANGO_CSRF_TRUSTED_ORIGINS=https://culineire.ie,https://www.culineire.ie
DJANGO_SERVE_STATIC_LOCALLY=False
DJANGO_SERVE_MEDIA_LOCALLY=False
DJANGO_SECURE_SSL_REDIRECT=True
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False
DJANGO_SECURE_HSTS_PRELOAD=False
DJANGO_SESSION_COOKIE_SECURE=True
DJANGO_CSRF_COOKIE_SECURE=True
DJANGO_SECURE_PROXY_SSL_HEADER=True
DJANGO_LOG_LEVEL=INFO
DJANGO_LOG_DIR=/srv/culineire/logs
```

`DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD` should only be enabled after HTTPS is confirmed
for the main domain, `www`, and every covered subdomain. Do not enable them automatically on a first production deploy.

## Linode / Nginx / HTTPS checklist

- Confirm DNS for `culineire.ie` and `www.culineire.ie` points to the intended Linode.
- Terminate HTTPS at Nginx with a valid certificate for the main domain and `www`.
- Redirect plain HTTP to HTTPS at the Nginx layer.
- Forward `X-Forwarded-Proto: https` only from the trusted reverse proxy.
- Enable `DJANGO_SECURE_PROXY_SSL_HEADER=True` only after the proxy forwarding is verified.
- Verify static and media serving strategy before launch.
- Confirm secure cookies are enabled in production.
- Verify admin is reachable only over HTTPS.
- Run Django deployment checks before switching traffic.

## Password reset routes

The project currently includes `django.contrib.auth.urls` in `config/urls.py`, which exposes Django's password reset
routes in addition to login/logout flows. If password reset is not needed before public launch, disable those routes. If
it is needed, add rate limiting and confirm the outbound email flow before exposing it publicly.

## Rate limiting in production

If the app runs under multiple Gunicorn workers or across multiple instances, production rate limiting should use a
shared cache such as Redis. Per-process local memory is not enough for consistent enforcement across workers.

## Recommended command checklist

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate
python manage.py test
python manage.py check --deploy
```
