# CulinEire Linode Deploy Handoff

This is the short handoff for the person publishing CulinEire on Linode/Akamai Cloud.
The full command-by-command server guide is in `deploy/DEPLOY_UBUNTU_NGINX_UNIT.md`.

## What is already prepared in the repository

- Django production settings are environment-driven in `config/settings.py`.
- PostgreSQL is supported through `DATABASE_URL`.
- Static and media roots are configurable through `DJANGO_STATIC_ROOT` and `DJANGO_MEDIA_ROOT`.
- NGINX Unit config is ready: `deploy/unit.culineire.json`.
- NGINX bootstrap config is ready for the first certificate issue: `deploy/nginx.culineire.bootstrap.conf`.
- Final NGINX HTTPS reverse-proxy config is ready: `deploy/nginx.culineire.conf`.
- ModSecurity WAF rules are ready: `deploy/modsecurity/culineire-main.conf` and `deploy/modsecurity/culineire-probes.conf`.
- Production environment template is ready: `deploy/production.env.example`.
- Public technical URLs are implemented: `/about/`, `/privacy/`, `/robots.txt`, `/sitemap.xml`.
- Last local preflight before this handoff: 62 Django tests passed, `manage.py check` passed, no pending migrations.

## What the deployer must prepare outside the repo

Do not commit any of these values to Git.

- Linode/Akamai Cloud account with billing enabled.
- Ubuntu 24.04 LTS Linode instance.
- SSH key for server access.
- Domain DNS control for `culineire.ie`.
- Production PostgreSQL password.
- Production `DJANGO_SECRET_KEY`.
- Cloudflare Turnstile production site key and secret key for `culineire.ie`.
- SMTP account/app password or SMTP token for outgoing email.
  Linode may restrict outbound SMTP ports on new instances; if SMTP delivery fails, open a Linode support ticket or use a provider with an HTTP email API.
- GitHub deploy key or fine-scoped token for pulling the private/public repository on the server.

## Linode setup checklist

1. Create a Linode running Ubuntu 24.04 LTS.
2. Add SSH key access. Disable password SSH login after confirming key login works.
3. Create/attach a Linode Cloud Firewall:
   - allow TCP `22` only from trusted admin IPs where possible;
   - allow TCP `80` from the internet;
   - allow TCP `443` from the internet;
   - deny other inbound traffic by default.
4. Point DNS to the Linode public IP:
   - root/apex `culineire.ie` -> A record to IPv4;
   - `www.culineire.ie` -> A record to IPv4 or CNAME to root;
   - add AAAA records too if IPv6 is enabled and configured.
5. Wait for DNS propagation before issuing Let's Encrypt certificates.

Current first Linode IP from the setup screen: `80.85.84.156`.
Use it for SSH and DNS only if it is still the active public IP in Linode Cloud Manager.

## Server deployment order

1. SSH into the Linode.
2. Follow `deploy/DEPLOY_UBUNTU_NGINX_UNIT.md` from top to bottom:
   - install system packages;
   - install NGINX Unit and `unit-python3.12`;
   - clone the repo into `/srv/culineire/current`;
   - create `/srv/culineire/venv`;
   - install `requirements.txt`;
   - create PostgreSQL user/database;
   - copy `deploy/production.env.example` to `/srv/culineire/shared/.env`;
   - replace every `replace-*` value;
   - run Django checks, migrations, collectstatic and tests;
   - load the Unit config;
   - apply NGINX bootstrap config;
   - issue Let's Encrypt certificate;
   - install and enable ModSecurity with the project rules;
   - switch to final NGINX HTTPS config.
3. Create the first owner account with `createsuperuser`.
4. Log into the site and verify signup, email activation, recipes, articles, messages, moderation and monitoring.

## Production `.env` values to verify

The server file should be `/srv/culineire/shared/.env`.

```env
DJANGO_ENV=production
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
SITE_DOMAIN=culineire.ie
SITE_SCHEME=https
DATABASE_URL=postgresql://culineire:<real-password>@127.0.0.1:5432/culineire
MONITORING_BLOCK_SUSPICIOUS_PROBES=True
```

Keep `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS` and `DJANGO_SECURE_HSTS_PRELOAD` disabled for the first launch. Enable them only after HTTPS is confirmed for every relevant subdomain.

## Final acceptance checks

- `https://culineire.ie/` returns 200.
- `http://culineire.ie/` redirects to HTTPS.
- `https://www.culineire.ie/` works or redirects as intended.
- `/static/css/base.css` returns 200.
- `/robots.txt` returns 200.
- `/sitemap.xml` returns XML.
- `/credentials.json` and `/stripe-credentials.json` return 404 and appear in the ModSecurity audit log.
- Uploads under `/media/` work after creating/editing content.
- Signup activation email is delivered.
- Moderator tools work for GreenBear.
- Backups exist for both PostgreSQL and `/srv/culineire/shared/media`.

## Useful official references

- Django deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/
- NGINX Unit Django guide: https://docs.nginx.com/nginx-unit/howto/frameworks/django/
- Linode Cloud Firewalls: https://techdocs.akamai.com/cloud-computing/docs/cloud-firewall
- Linode A/AAAA DNS records: https://techdocs.akamai.com/cloud-computing/docs/a-and-aaaa-records
