---
name: NGINX Unit body size fix
description: How we fixed 502 errors on large file uploads (recipe/article form with multiple photos)
type: project
originSessionId: 41497f72-e8fb-41cf-96f0-0946e152a172
---
502 Bad Gateway on POST to /recipes/create/ or /articles/ when uploading multiple large images.

**Why:** NGINX Unit 1.34.2 (Debian package) has a compiled-in default max_body_size (~8MB) and does NOT expose `limits.max_body_size` via the control API — returns "Unknown parameter" even though docs say it should be supported. Unit closes the connection early → NGINX gets `sendfile() failed (32: Broken pipe)` → 502.

**Fix applied:** Added `proxy_request_buffering off` to the `location /` block in `/etc/nginx/sites-enabled/culineire`. This makes NGINX stream the request body directly to Unit instead of buffering to a temp file and using sendfile(). Unit accepts streamed chunks.

**Also set:** `client_max_body_size 50m` in NGINX (was 25m). Unit `limits.max_body_size` cannot be configured in this build.

**How to apply:** If 502 returns on file upload after a server rebuild or nginx config reset, re-add `proxy_request_buffering off` to `location /` in the culineire nginx site config.
