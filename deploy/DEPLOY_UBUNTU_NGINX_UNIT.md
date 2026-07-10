# CulinEire Production Deploy: Ubuntu + NGINX + NGINX Unit

Target layout:

```text
/srv/culineire/current      # git checkout
/srv/culineire/venv         # Python virtual environment
/srv/culineire/shared       # .env, staticfiles, media, logs, cache, backups
```

## Accounts, DNS, and Secrets

- Domain DNS: `A` records for `culineire.ie` and `www.culineire.ie` point to the server IP.
- GitHub deploy access: use a deploy key or fine-scoped token; do not put it in `.env`.
- Cloudflare Turnstile: create production site and secret keys for `culineire.ie`.
- SMTP: create a provider account and app password or SMTP token.
  Linode may restrict outbound SMTP ports on new instances; if SMTP delivery fails, open a Linode support ticket or use a provider with an HTTP email API.
- Database password: generate on the server and store only in `/srv/culineire/shared/.env`.
- Django secret: generate on the server:

```bash
python - <<'PY'
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
PY
```

## Install Packages

```bash
sudo apt update
sudo apt install -y nginx postgresql postgresql-contrib python3.12 python3.12-venv python3-pip git curl certbot python3-certbot-nginx libnginx-mod-http-modsecurity modsecurity-crs
```

Install NGINX Unit from the official Unit repository. These commands target Ubuntu 24.04 `noble`; use the matching codename and Python module if the server is a different Ubuntu release.

```bash
sudo install -d -m 0755 /usr/share/keyrings
curl --output /tmp/nginx-keyring.gpg https://unit.nginx.org/keys/nginx-keyring.gpg
sudo mv /tmp/nginx-keyring.gpg /usr/share/keyrings/nginx-keyring.gpg
printf '%s\n' \
  'deb [signed-by=/usr/share/keyrings/nginx-keyring.gpg] https://packages.nginx.org/unit/ubuntu/ noble unit' \
  'deb-src [signed-by=/usr/share/keyrings/nginx-keyring.gpg] https://packages.nginx.org/unit/ubuntu/ noble unit' \
  | sudo tee /etc/apt/sources.list.d/unit.list
sudo apt update
sudo apt install -y unit unit-python3.12
sudo systemctl restart unit
```

Enable the services:

```bash
sudo systemctl enable --now unit nginx postgresql
```

## Create App Directories

```bash
sudo mkdir -p /srv/culineire/shared/{staticfiles,media,logs,cache,backups}
sudo chown -R "$USER":"$USER" /srv/culineire
git clone https://github.com/BadMaestro/culineire.git /srv/culineire/current
python3.12 -m venv /srv/culineire/venv
/srv/culineire/venv/bin/pip install --upgrade pip
/srv/culineire/venv/bin/pip install -r /srv/culineire/current/requirements.txt
```

## PostgreSQL

```bash
sudo -u postgres psql
```

```sql
CREATE USER culineire WITH PASSWORD 'replace-password';
CREATE DATABASE culineire OWNER culineire;
ALTER ROLE culineire SET client_encoding TO 'utf8';
ALTER ROLE culineire SET default_transaction_isolation TO 'read committed';
ALTER ROLE culineire SET timezone TO 'Europe/Dublin';
\q
```

## Environment File

Create `/srv/culineire/shared/.env` from `deploy/production.env.example`, then restrict it:

```bash
cp /srv/culineire/current/deploy/production.env.example /srv/culineire/shared/.env
chmod 600 /srv/culineire/shared/.env
```

Edit every `replace-*` value before continuing.

## Django Release Commands

If `git fetch` fails with `insufficient permission for adding an object to repository database .git/objects`,
repair checkout ownership before running the deploy script:

```bash
sudo chown -R deploy:deploy /srv/culineire/current
```

```bash
cd /srv/culineire/current
/srv/culineire/venv/bin/python manage.py check --deploy
/srv/culineire/venv/bin/python manage.py makemigrations --check --dry-run
/srv/culineire/venv/bin/python manage.py migrate
/srv/culineire/venv/bin/python manage.py collectstatic --noinput
/srv/culineire/venv/bin/python manage.py test
```

Create the owner account after migrations:

```bash
/srv/culineire/venv/bin/python manage.py createsuperuser
```

## NGINX Unit

```bash
sudo cp /srv/culineire/current/deploy/unit.culineire.json /tmp/unit.culineire.json
sudo curl -X PUT --data-binary @/tmp/unit.culineire.json --unix-socket /var/run/control.unit.sock http://localhost/config/
sudo curl --unix-socket /var/run/control.unit.sock http://localhost/config/
```

## NGINX and TLS

Start with the HTTP-only bootstrap config so NGINX can pass `nginx -t` before certificates exist:

```bash
sudo mkdir -p /var/www/letsencrypt
sudo rm -f /etc/nginx/sites-enabled/default
sudo cp /srv/culineire/current/deploy/nginx.culineire.bootstrap.conf /etc/nginx/sites-available/culineire
sudo ln -sf /etc/nginx/sites-available/culineire /etc/nginx/sites-enabled/culineire
sudo nginx -t
sudo systemctl reload nginx
```

Issue a certificate for both names:

```bash
sudo certbot certonly --webroot -w /var/www/letsencrypt -d culineire.ie -d www.culineire.ie
```

## ModSecurity WAF

Enable ModSecurity before applying the final HTTPS NGINX config. The final config expects `/etc/nginx/modsec/culineire-main.conf` to exist.

```bash
sudo mkdir -p /etc/nginx/modsec
sudo mkdir -p /etc/modsecurity
if [ ! -f /etc/modsecurity/modsecurity.conf ]; then
    if [ -f /etc/modsecurity/modsecurity.conf-recommended ]; then
        sudo cp /etc/modsecurity/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
    elif [ -f /etc/modsecurity.d/modsecurity.conf-recommended ]; then
        sudo cp /etc/modsecurity.d/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
    elif [ -f /usr/share/doc/libmodsecurity3/examples/modsecurity.conf-recommended ]; then
        sudo cp /usr/share/doc/libmodsecurity3/examples/modsecurity.conf-recommended /etc/modsecurity/modsecurity.conf
    else
        printf '%s\n' \
            'SecRuleEngine On' \
            'SecRequestBodyAccess On' \
            'SecResponseBodyAccess Off' \
            'SecAuditEngine RelevantOnly' \
            'SecAuditLog /var/log/modsec_audit.log' \
            'SecAuditLogParts ABIJDEFHZ' \
            | sudo tee /etc/modsecurity/modsecurity.conf >/dev/null
    fi
fi
sudo sed -i -E 's/^[[:space:]]*SecRuleEngine[[:space:]]+.*/SecRuleEngine On/' /etc/modsecurity/modsecurity.conf
if ! sudo grep -qE '^[[:space:]]*SecRuleEngine[[:space:]]+' /etc/modsecurity/modsecurity.conf; then
    printf '%s\n' 'SecRuleEngine On' | sudo tee -a /etc/modsecurity/modsecurity.conf >/dev/null
fi
sudo cp /srv/culineire/current/deploy/modsecurity/culineire-main.conf /etc/nginx/modsec/culineire-main.conf
sudo cp /srv/culineire/current/deploy/modsecurity/culineire-probes.conf /etc/nginx/modsec/culineire-probes.conf
```

Then switch to the final HTTPS reverse-proxy config:

```bash
sudo cp /srv/culineire/current/deploy/nginx.culineire.conf /etc/nginx/sites-available/culineire
sudo nginx -t
sudo systemctl reload nginx
```

## Final Verification

```bash
curl -I https://culineire.ie/
curl -I https://culineire.ie/static/css/base.css
curl -I https://culineire.ie/media/
curl -I https://culineire.ie/credentials.json
curl -I https://culineire.ie/stripe-credentials.json
```

Verify:

- HTTP redirects to HTTPS.
- Credential probes return 404 and are written to the ModSecurity audit log.
- `DEBUG=False`.
- Login, signup activation email, messages, recipe/article creation, moderation panel, monitoring panel.
- `check --deploy` shows only intentional HSTS preload/subdomain warnings for first launch.
- Database backup and media backup jobs exist before public traffic.

## Backups

Daily minimum:

```bash
pg_dump culineire | gzip > /srv/culineire/shared/backups/culineire-$(date +%F).sql.gz
tar -czf /srv/culineire/shared/backups/media-$(date +%F).tar.gz -C /srv/culineire/shared media
```
