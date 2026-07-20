---
name: reference-run-tests-server
description: How to run tests on the production server without breaking Telegram — correct heredoc command
metadata: 
  node_type: memory
  type: reference
  originSessionId: 54e34f70-f718-4f1f-a375-9e6d18758d42
---

`set -a && source .env` BREAKS on special characters in the secret key.
The ONLY correct way is a Python heredoc that calls `manage.py test` via subprocess.

## CRITICAL: always set DJANGO_IS_TESTING=1

When using the Python API approach (calling TestRunner directly), `sys.argv` doesn't contain "test",
so `IS_TESTING = False` → Telegram fires on the REAL channel. **Always set the env var first.**

settings.py: `IS_TESTING = "test" in sys.argv or os.getenv("DJANGO_IS_TESTING") == "1"`

## Correct command (subprocess, sets sys.argv via manage.py):

```bash
wsl -e bash -c "ssh -i ~/.ssh/culineire_linode deploy@80.85.84.156 'cd /srv/culineire/current && /srv/culineire/venv/bin/python - <<'"'"'PY'"'"'
import os, subprocess
from pathlib import Path
for raw in Path(\"/srv/culineire/shared/.env\").read_text().splitlines():
    line = raw.strip()
    if not line or line.startswith(\"#\") or \"=\" not in line:
        continue
    k, _, v = line.partition(\"=\")
    os.environ[k.strip()] = v.strip().strip(\"\\\"'\")
os.environ.setdefault(\"DJANGO_SETTINGS_MODULE\", \"config.settings\")
os.environ[\"DJANGO_IS_TESTING\"] = \"1\"
raise SystemExit(subprocess.call([\"/srv/culineire/venv/bin/python\", \"manage.py\", \"test\", \"--verbosity\", \"1\", \"--keepdb\"]))
PY
'"