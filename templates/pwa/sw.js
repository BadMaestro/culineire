{% autoescape off %}
// CulinEire Service Worker — {{ cache_name }}
// Rendered by Django; do not edit cached copies.

var CACHE_NAME = '{{ cache_name }}';
var OFFLINE_URL = '/offline/';
var NO_CACHE_PREFIXES = {{ no_cache_prefixes_json }};

// Returns true if the pathname starts with any no-cache prefix.
function isNoCachePath(pathname) {
  for (var i = 0; i < NO_CACHE_PREFIXES.length; i++) {
    if (pathname.startsWith(NO_CACHE_PREFIXES[i])) return true;
  }
  return false;
}

// ── Install ───────────────────────────────────────────────────────────────────
// Pre-cache only the offline fallback page so we can show it without a network.
self.addEventListener('install', function (event) {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(function (cache) {
        return cache.add(OFFLINE_URL).catch(function () {
          // Fail silently — offline page might not be available at install time.
        });
      })
      .then(function () {
        // Skip waiting so the new SW activates immediately.
        return self.skipWaiting();
      })
  );
});

// ── Activate ──────────────────────────────────────────────────────────────────
// Delete caches from older SW versions so storage does not grow unbounded.
self.addEventListener('activate', function (event) {
  event.waitUntil(
    caches.keys()
      .then(function (keys) {
        return Promise.all(
          keys
            .filter(function (key) { return key !== CACHE_NAME; })
            .map(function (key) { return caches.delete(key); })
        );
      })
      .then(function () {
        // Take control of existing open pages immediately.
        return self.clients.claim();
      })
  );
});

// ── Fetch ─────────────────────────────────────────────────────────────────────
self.addEventListener('fetch', function (event) {
  var request = event.request;

  // Only intercept GET requests.
  if (request.method !== 'GET') return;

  // Only intercept same-origin requests.
  if (!request.url.startsWith(self.location.origin + '/')) return;

  var pathname = new URL(request.url).pathname;

  // Never intercept private, admin, or user-specific paths.
  // Let the browser handle them directly — no SW interference.
  if (isNoCachePath(pathname)) return;

  // ── Static assets (/static/, /media/): Cache First ───────────────────────
  // Serve from cache when available; fetch from network and cache on miss.
  // Django's ManifestStaticFilesStorage uses content-hashed filenames so
  // cached entries remain valid until a new deploy changes the hash.
  if (pathname.startsWith('/static/') || pathname.startsWith('/media/')) {
    event.respondWith(
      caches.match(request).then(function (cached) {
        if (cached) return cached;
        return fetch(request)
          .then(function (response) {
            // Only cache valid same-origin 200 responses.
            if (response && response.status === 200 && response.type === 'basic') {
              var toCache = response.clone();
              caches.open(CACHE_NAME).then(function (cache) {
                cache.put(request, toCache);
              });
            }
            return response;
          })
          .catch(function () {
            // Network unavailable and not cached — return empty 503.
            return new Response('', { status: 503 });
          });
      })
    );
    return;
  }

  // ── Navigation requests (HTML pages): Network First ───────────────────────
  // Always prefer a fresh page from the network; show the offline fallback
  // only when the network is completely unavailable.
  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request).catch(function () {
        return caches.match(OFFLINE_URL).then(function (offlinePage) {
          return offlinePage || new Response(
            '<!doctype html><html lang="en"><body><p>You are offline. Please reconnect and try again.</p></body></html>',
            { status: 200, headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
    );
    return;
  }

  // All other requests (XHR, fonts from external CDNs, etc.): pass through.
});
{% endautoescape %}
