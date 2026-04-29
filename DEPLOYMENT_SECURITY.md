# Deployment Security

Use environment variables to control security behavior.

Development example:

- `DJANGO_ENV=development`
- `DJANGO_SECRET_KEY=<local-dev-secret>`
- `DJANGO_DEBUG=True`
- `DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,::1,culineire.localhost`
- `DJANGO_CSRF_TRUSTED_ORIGINS=http://127.0.0.1:8000,http://localhost:8000,http://culineire.localhost:8000`
- `DJANGO_SERVE_STATIC_LOCALLY=True`
- `DJANGO_SERVE_MEDIA_LOCALLY=True`
- `DJANGO_SECURE_SSL_REDIRECT=False`
- `DJANGO_SECURE_HSTS_SECONDS=0`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=False`
- `DJANGO_SECURE_HSTS_PRELOAD=False`
- `DJANGO_SESSION_COOKIE_SECURE=False`
- `DJANGO_CSRF_COOKIE_SECURE=False`

Production example:

- `DJANGO_ENV=production`
- `DJANGO_SECRET_KEY=<strong-random-secret>`
- `DJANGO_DEBUG=False`
- `DJANGO_ALLOWED_HOSTS=culineire.ie,www.culineire.ie`
- `DJANGO_CSRF_TRUSTED_ORIGINS=https://culineire.ie,https://www.culineire.ie`
- `DJANGO_SERVE_STATIC_LOCALLY=False`
- `DJANGO_SERVE_MEDIA_LOCALLY=False`
- `DJANGO_SECURE_SSL_REDIRECT=True`
- `DJANGO_SECURE_HSTS_SECONDS=31536000`
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- `DJANGO_SECURE_HSTS_PRELOAD=True`
- `DJANGO_SESSION_COOKIE_SECURE=True`
- `DJANGO_CSRF_COOKIE_SECURE=True`
- `DJANGO_SECURE_PROXY_SSL_HEADER=True`

Reverse proxy reminders:

- Terminate HTTPS at Nginx or another trusted reverse proxy.
- Forward `X-Forwarded-Proto: https` only from that trusted proxy.
- Enable `DJANGO_SECURE_PROXY_SSL_HEADER=True` only when the proxy is correctly configured.

Media upload safety:

- Keep user uploads outside the static asset pipeline.
- Apply operating system and web server upload limits in addition to Django validation.
- Review unapproved comments in admin before publishing them.

Before deployment run:

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py check
python manage.py check --deploy
python manage.py test
```

Dependency hygiene:

- Keep Django, Pillow, and rate-limiting dependencies updated.
- Reinstall from `requirements.txt` in each environment before deployment.
