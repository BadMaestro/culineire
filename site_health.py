#!/usr/bin/env python3
"""
culineire.ie Site Health Check
Checks all key pages for 500 errors and response times.
Usage: python site_health.py [--base-url https://culineire.ie] [--timeout 10]
Output: site_health.json + prints summary
Exit: 0 = all green, 1 = failures found
"""

import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = "https://culineire.ie"
TIMEOUT = 10

for i, arg in enumerate(sys.argv[1:], 1):
    if arg.startswith("--base-url="):
        BASE_URL = arg.split("=", 1)[1].rstrip("/")
    elif arg == "--base-url" and i + 1 < len(sys.argv):
        BASE_URL = sys.argv[i + 1].rstrip("/")
    elif arg.startswith("--timeout="):
        TIMEOUT = int(arg.split("=", 1)[1])

# -- Pages to check ----------------------------------------------------------
# (path, expected_status, description)
PAGES = [
    # Core public pages
    ("/",                               200, "Homepage"),
    ("/recipes/",                       200, "Recipe list"),
    ("/recipes/?page=2",                200, "Recipe list page 2"),
    ("/articles/",                      200, "Article list"),
    ("/amuse-bouche/",                  200, "Amuse-bouche feed"),
    ("/news/",                          200, "Newsfeed"),
    ("/sponsors/",                      200, "Sponsors puzzle"),
    ("/chef-battle/",                   None, "Chef Battle (disabled when feature off)"),

    # Auth pages
    ("/accounts/login/",                200, "Login page"),
    ("/accounts/signup/",               200, "Signup page"),

    # Legal
    ("/legal/terms/",                   200, "Terms"),
    ("/legal/cookies/",                 200, "Cookies"),

    # Static assets (manifest, robots, sitemap)
    ("/manifest.json",                  200, "PWA manifest"),
    ("/robots.txt",                     200, "robots.txt"),
    ("/sitemap.xml",                    200, "Sitemap"),

    # Agent discovery
    ("/.well-known/api-catalog",        200, "Agent discovery catalog"),
    ("/.well-known/mcp/server-card.json", 200, "MCP server card"),

    # Soft-deleted / non-existent slug -> expect 404 or 410, NOT 500
    ("/recipes/this-slug-does-not-exist-xyz/", None, "Non-existent recipe (expect 404/410)"),

    # Auth-protected pages should redirect (302/301), not 500
    ("/messages/",                      None, "Messages (expect redirect)"),
    ("/collection/",                    None, "Collection (expect redirect)"),
    ("/recipes/studio/create/",         None, "Recipe studio (expect redirect)"),
]

# ----------------------------------------------------------------------------

RESULTS = []
FAILURES = []

def fetch(path):
    url = BASE_URL + path
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "culineire-healthcheck/1.0"},
    )
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            ms = int((time.monotonic() - t0) * 1000)
            return resp.status, ms
    except urllib.error.HTTPError as e:
        ms = int((time.monotonic() - t0) * 1000)
        return e.code, ms
    except Exception as e:
        ms = int((time.monotonic() - t0) * 1000)
        return 0, ms

def is_server_error(status):
    return status >= 500

def check(path, expected, desc):
    status, ms = fetch(path)
    fail = False

    if expected is not None:
        fail = (status != expected)
    else:
        # No expected status — just flag 5xx
        fail = is_server_error(status)

    status_str = str(status) if status else "TIMEOUT"
    icon = "[FAIL]" if fail else "[OK]  "
    expected_str = str(expected) if expected else "not 5xx"
    print(f"{icon} {status_str:>3}  {ms:>5}ms  {desc}  ({path})")

    r = {
        "path": path,
        "description": desc,
        "status": status,
        "ms": ms,
        "expected": expected,
        "pass": not fail,
    }
    RESULTS.append(r)
    if fail:
        FAILURES.append(r)
    return not fail

# -- Run checks --------------------------------------------------------------

ts = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
print(f"\n=== culineire.ie Health Check -- {ts} ===\n")
print(f"{'':6} {'Status':>6}  {'Time':>7}  Description")
print("-" * 70)

for path, expected, desc in PAGES:
    check(path, expected, desc)

# -- Summary -----------------------------------------------------------------

total  = len(RESULTS)
passed = sum(1 for r in RESULTS if r["pass"])
failed = len(FAILURES)

print("-" * 70)
print(f"\nRESULT: {passed}/{total} passed", end="")
if failed:
    print(f"  --  {failed} FAILED:")
    for f in FAILURES:
        print(f"  x  [{f['status']}] {f['description']} -> {BASE_URL}{f['path']}")
else:
    print("  -- all green")

# -- Write JSON --------------------------------------------------------------

out = {
    "timestamp": ts,
    "base_url": BASE_URL,
    "summary": {"total": total, "passed": passed, "failed": failed},
    "results": RESULTS,
    "failures": FAILURES,
}
out_path = "/srv/culineire/current/site_health.json"
try:
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nResults written to {out_path}")
except Exception as e:
    print(f"\n[WARN] Could not write {out_path}: {e}")

sys.exit(0 if failed == 0 else 1)
