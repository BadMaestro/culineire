#!/usr/bin/env python3
"""
culineire.ie SEO Audit Script
Checks all 8 priority SEO fixes and outputs results.
Usage: python audit.py [--base-url https://culineire.ie]
"""

import sys
import os
import json
import csv
import re
import time
import urllib.request
import urllib.error
from datetime import datetime

BASE_URL = 'https://culineire.ie'
for i, arg in enumerate(sys.argv[1:], 1):
    if arg.startswith('--base-url='):
        BASE_URL = arg.split('=', 1)[1]
    elif arg == '--base-url' and i + 1 < len(sys.argv):
        BASE_URL = sys.argv[i + 1]

RESULTS = []

def check(name, priority, status, detail, expected=None, actual=None):
    r = {
        'priority': priority,
        'check': name,
        'status': status,
        'detail': detail,
        'expected': expected or '',
        'actual': actual or '',
        'timestamp': datetime.utcnow().isoformat()
    }
    RESULTS.append(r)
    icon = {'PASS': '[PASS]', 'FAIL': '[FAIL]', 'WARN': '[WARN]'}.get(status, '[????]')
    print(f'{icon} P{priority}: {name} -- {detail}')
    return r

def fetch(path, timeout=10):
    url = BASE_URL + path
    req = urllib.request.Request(url, headers={'User-Agent': 'culineire-audit/1.0'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode('utf-8', errors='replace'), dict(resp.headers)
    except urllib.error.HTTPError as e:
        return e.code, '', {}
    except Exception as e:
        return 0, str(e), {}

print(f'\n=== culineire.ie SEO Audit -- {datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")} ===\n')

# Setup Django
try:
    sys.path.insert(0, '/srv/culineire/current')
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'culineire.settings')
    import django
    django.setup()
    django_ok = True
except Exception as e:
    print(f'[WARN] Django setup failed: {e}')
    django_ok = False

# P1: 410 for soft-deleted recipes
print('--- P1: 410 Gone for soft-deleted recipes ---')
if django_ok:
    try:
        from recipes.models import Recipe
        deleted = Recipe.objects.filter(is_deleted=True).first()
        if deleted:
            st, bd, hd = fetch(f'/recipes/{deleted.slug}/')
            if st == 410:
                check('410 Gone for soft-deleted recipe', 1, 'PASS', f'/recipes/{deleted.slug}/ returns 410', '410', str(st))
            else:
                check('410 Gone for soft-deleted recipe', 1, 'FAIL', f'/recipes/{deleted.slug}/ returns {st}', '410', str(st))
        else:
            check('410 Gone for soft-deleted recipe', 1, 'WARN', 'No deleted recipes found to test', '410', 'N/A')
    except Exception as e:
        check('410 Gone for soft-deleted recipe', 1, 'WARN', f'Django error: {e}', '410', 'N/A')
else:
    check('410 Gone for soft-deleted recipe', 1, 'WARN', 'Django not available', '410', 'N/A')

# P2: noindex on paginated pages
print('\n--- P2: noindex on paginated recipe pages ---')
st, body, hd = fetch('/recipes/?page=2')
if st == 200:
    if 'noindex' in body.lower():
        check('noindex on /recipes/?page=2', 2, 'PASS', 'noindex meta tag found', 'noindex', 'present')
    else:
        check('noindex on /recipes/?page=2', 2, 'FAIL', 'noindex meta tag NOT found', 'noindex', 'absent')
else:
    check('noindex on /recipes/?page=2', 2, 'WARN', f'Page returned {st}', '200', str(st))

# P3: Canonical tags on recipe pages
print('\n--- P3: Canonical tags on recipe pages ---')
if django_ok:
    try:
        from recipes.models import Recipe
        live = Recipe.objects.filter(is_deleted=False, status='approved').first()
        if live:
            st, body, hd = fetch(f'/recipes/{live.slug}/')
            if 'rel="canonical"' in body or "rel='canonical'" in body:
                check('Canonical tag on recipe page', 3, 'PASS', f'/recipes/{live.slug}/ has canonical', 'canonical', 'present')
            else:
                check('Canonical tag on recipe page', 3, 'FAIL', f'/recipes/{live.slug}/ missing canonical', 'canonical', 'absent')
        else:
            check('Canonical tag on recipe page', 3, 'WARN', 'No approved recipes found', 'canonical', 'N/A')
    except Exception as e:
        check('Canonical tag on recipe page', 3, 'WARN', f'Django error: {e}', 'canonical', 'N/A')
else:
    check('Canonical tag on recipe page', 3, 'WARN', 'Django not available', 'canonical', 'N/A')

# P4: Email obfuscation
print('\n--- P4: Email obfuscation ---')
pages_to_check = ['/legal/privacy/', '/legal/terms/', '/sponsors/']
for page in pages_to_check:
    st, body, hd = fetch(page)
    if st == 200:
        if '/cdn-cgi/l/email-protection' in body:
            check(f'Email obfuscation on {page}', 4, 'FAIL', 'Cloudflare email protection link found', 'obfuscated', 'exposed')
        elif 'culineire@bearcave.ie' in body:
            check(f'Email obfuscation on {page}', 4, 'WARN', 'Raw email visible (may be obfuscated by CF)', 'obfuscated', 'raw')
        else:
            check(f'Email obfuscation on {page}', 4, 'PASS', 'No email exposure issues', 'obfuscated', 'ok')
    else:
        check(f'Email obfuscation on {page}', 4, 'WARN', f'{page} returned {st}', '200', str(st))

# P5: WebP images
print('\n--- P5: WebP hero images ---')
st, body, hd = fetch('/')
if st == 200:
    if '.webp' in body:
        check('WebP images on homepage', 5, 'PASS', 'WebP image references found', 'webp', 'present')
    else:
        check('WebP images on homepage', 5, 'FAIL', 'No WebP image references found', 'webp', 'absent')
    if '<picture' in body:
        check('<picture> element on homepage', 5, 'PASS', '<picture> element found', 'picture', 'present')
    else:
        check('<picture> element on homepage', 5, 'FAIL', '<picture> element NOT found', 'picture', 'absent')
else:
    check('WebP images on homepage', 5, 'WARN', f'Homepage returned {st}', '200', str(st))

# P6: Deferred non-critical CSS
print('\n--- P6: Deferred non-critical CSS ---')
st, body, hd = fetch('/')
if st == 200:
    if 'media="print"' in body:
        check('CSS deferred via media=print', 6, 'PASS', 'media="print" deferred CSS found', 'deferred', 'present')
    else:
        check('CSS deferred via media=print', 6, 'FAIL', 'No media="print" CSS deferral found', 'deferred', 'absent')
    if 'defer' in body:
        check('JS scripts deferred', 6, 'PASS', 'defer attribute found on scripts', 'defer', 'present')
    else:
        check('JS scripts deferred', 6, 'FAIL', 'No defer attribute found on scripts', 'defer', 'absent')

# P7: Title tags
print('\n--- P7: Title tags ---')
title_checks = [
    ('/', 'CulinEire'),
    ('/recipes/', 'Recipe'),
    ('/articles/', 'Article'),
]
if django_ok:
    try:
        from recipes.models import Recipe
        live = Recipe.objects.filter(is_deleted=False, status='approved').first()
        if live:
            title_checks.append((f'/recipes/{live.slug}/', 'Irish Recipe'))
    except Exception:
        pass

for page, expected_fragment in title_checks:
    st, body, hd = fetch(page)
    if st == 200:
        m = re.search(r'<title[^>]*>(.*?)</title>', body, re.IGNORECASE | re.DOTALL)
        title = m.group(1).strip() if m else ''
        if title and expected_fragment.lower() in title.lower():
            check(f'Title tag on {page}', 7, 'PASS', f'Title: "{title[:80]}"', expected_fragment, title[:80])
        elif title:
            check(f'Title tag on {page}', 7, 'WARN', f'Missing "{expected_fragment}": "{title[:80]}"', expected_fragment, title[:80])
        else:
            check(f'Title tag on {page}', 7, 'FAIL', f'No title tag found on {page}', expected_fragment, 'absent')
    else:
        check(f'Title tag on {page}', 7, 'WARN', f'{page} returned {st}', '200', str(st))

# P8: CLS - width/height on img tags
print('\n--- P8: CLS prevention (width/height on images) ---')
st, body, hd = fetch('/')
if st == 200:
    imgs = re.findall(r'<img[^>]+>', body, re.IGNORECASE)
    missing = [img for img in imgs if 'width=' not in img.lower() or 'height=' not in img.lower()]
    total = len(imgs)
    if total == 0:
        check('CLS img width/height on homepage', 8, 'WARN', 'No img tags found', 'width+height', 'N/A')
    elif not missing:
        check('CLS img width/height on homepage', 8, 'PASS', f'All {total} images have width+height', 'all', f'{total}/{total}')
    else:
        check('CLS img width/height on homepage', 8, 'FAIL', f'{len(missing)}/{total} images missing width or height', 'all', f'{total-len(missing)}/{total}')

# Summary
print('\n=== SUMMARY ===')
passed = sum(1 for r in RESULTS if r['status'] == 'PASS')
failed = sum(1 for r in RESULTS if r['status'] == 'FAIL')
warned = sum(1 for r in RESULTS if r['status'] == 'WARN')
print(f'PASS: {passed}  FAIL: {failed}  WARN: {warned}  TOTAL: {len(RESULTS)}')

out_dir = '/srv/culineire/current'

csv_path = f'{out_dir}/full_audit.csv'
with open(csv_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['priority', 'check', 'status', 'detail', 'expected', 'actual', 'timestamp'])
    writer.writeheader()
    writer.writerows(RESULTS)
print(f'\nResults written to {csv_path}')

json_path = f'{out_dir}/site_checks.json'
with open(json_path, 'w') as f:
    json.dump({'summary': {'pass': passed, 'fail': failed, 'warn': warned, 'total': len(RESULTS)}, 'checks': RESULTS}, f, indent=2)
print(f'Results written to {json_path}')

sys.exit(0 if failed == 0 else 1)
