#!/usr/bin/env bash
# WAF acceptance check -- real HTTP through nginx + ModSecurity + TLS.
#
# Why this exists
# ---------------
# Django's test client talks straight to the WSGI application. It never touches
# nginx, never touches ModSecurity, never touches TLS. So a page can pass all 42
# unit tests and still be returned as 403 to a real user by the WAF, and nothing
# in the suite would notice. This script closes that gap for the paths we care
# about.
#
# The useful property being exploited: ModSecurity runs BEFORE Django, so a WAF
# block does not depend on being logged in. Anonymous requests are enough to tell
# whether the WAF lets a URL, a query string or a request body through -- which
# means this check needs no credentials and no session minting.
#
# Reading the results
#   403 -> the WAF (or nginx) refused it. This is the failure we are hunting.
#   404 -> the WAF passed it and Django answered with its staff-only gate. PASS.
#   200 -> the WAF passed it and the page is public. PASS.
#   000 -> could not connect at all.
#
# Usage: ops/waf/waf_acceptance.sh [base_url]

set -uo pipefail

BASE="${1:-https://culineire.ie}"
UA="waf-acceptance/1.0 (+culineire internal check)"
PASS=0
FAIL=0

check() {
  local label="$1" path="$2" expect_not="${3:-403}"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -A "$UA" "${BASE}${path}" 2>/dev/null || echo 000)
  if [ "$code" = "$expect_not" ] || [ "$code" = "000" ]; then
    printf '  FAIL  %-46s -> %s\n' "$label" "$code"
    FAIL=$((FAIL + 1))
  else
    printf '  pass  %-46s -> %s\n' "$label" "$code"
    PASS=$((PASS + 1))
  fi
}

check_post() {
  local label="$1" path="$2" data="$3"
  local code
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -A "$UA" \
           -X POST --data "$data" "${BASE}${path}" 2>/dev/null || echo 000)
  # 403 here is ambiguous on purpose: Django's CSRF check also answers 403.
  # It is reported rather than judged, because telling the two apart needs the
  # ModSecurity audit log, which the summary below points at.
  printf '  note  %-46s -> %s  (403 may be CSRF, not the WAF -- check the audit log)\n' "$label" "$code"
}

echo "WAF acceptance against ${BASE}"
echo "  403 = blocked by WAF (bad) | 404 = WAF passed, Django gate (good) | 200 = public"
echo

echo "monitoring pages (staff-gated, so 404 anonymous is the healthy answer):"
check "monitoring dashboard"            "/monitoring/"
check "server health"                   "/monitoring/server/"
check "server health + refresh param"   "/monitoring/server/?refresh=1"
check "traffic detail + query"          "/monitoring/traffic/?period=7d&kind=pageviews"
check "security detail + ip_hash"       "/monitoring/security/?period=7d&ip_hash=abc123"

echo
echo "public pages (200 expected, they must not be blocked either):"
check "home"                            "/"
check "recipes"                         "/recipes/"
check "articles"                        "/articles/"

echo
echo "arena (staff-only during dark launch):"
check "arena hall"                      "/chef-battle/arena/"
check "battle popup fragment"           "/chef-battle/arena/battle-popup/"

echo
echo "POST handling -- does the WAF let request bodies through at all?"
# The control is what makes this readable without opening the audit log. A POST to
# a path Django does not know must come back 404. If it comes back 403, the WAF is
# refusing POST bodies wholesale and every future form endpoint is already broken.
CONTROL=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 -A "$UA"             -X POST --data "probe=1" "${BASE}/waf-acceptance-nonexistent-path/" 2>/dev/null || echo 000)
if [ "$CONTROL" = "403" ]; then
  printf '  FAIL  %-46s -> %s
' "WAF rejects POST bodies outright" "$CONTROL"
  FAIL=$((FAIL + 1))
else
  printf '  pass  %-46s -> %s
' "WAF passes POST through to Django" "$CONTROL"
  PASS=$((PASS + 1))
fi
# With the control passing, a 403 on a real endpoint is Django's CSRF check doing
# its job, not the WAF. Verified 2026-07-22: the audit entry for this request
# carried no rule hits and django.log recorded "Referer checking failed".
check_post "arena react (403 here = CSRF, expected)" "/chef-battle/arena/react/" "reaction=clap"

echo
echo "----------------------------------------------------------------"
printf '  %d passed, %d blocked by the WAF\n' "$PASS" "$FAIL"
if [ "$FAIL" -gt 0 ]; then
  echo "  Something above was refused before it reached Django."
  echo "  Correlate with: grep -A20 '<path>' /var/log/nginx/modsec_audit.log"
  exit 1
fi
echo "  Nothing is being blocked before it reaches Django."
