(function () {
  'use strict';

  var POLL_INTERVAL = 3000;   // ms between polls
  var SHOW_DURATION = 6000;   // ms toast stays visible
  var FADE_OUT_MS   = 420;    // must match CSS transition duration

  // Mark connection time — events created before this timestamp are ignored,
  // so visitors who arrive after a notification was fired never see it.
  var lastSeen = new Date().toISOString();
  var tray = null;

  function getTray() {
    if (!tray) {
      tray = document.createElement('div');
      tray.className = 'presence-tray';
      tray.setAttribute('aria-live', 'polite');
      tray.setAttribute('aria-atomic', 'false');
      tray.setAttribute('aria-label', 'System notifications');
      document.body.appendChild(tray);
    }
    return tray;
  }

  function showToast(message, type) {
    var el = document.createElement('div');
    el.className = 'presence-toast' + (type === 'owner' ? ' presence-toast--owner' : '');
    el.setAttribute('role', 'status');
    el.innerHTML =
      '<span class="presence-toast__dot" aria-hidden="true"></span>' +
      '<span class="presence-toast__text">' + escapeHtml(message) + '</span>';

    getTray().appendChild(el);

    // Double rAF ensures the element is painted before the transition starts
    requestAnimationFrame(function () {
      requestAnimationFrame(function () {
        el.classList.add('is-visible');
      });
    });

    setTimeout(function () {
      el.classList.remove('is-visible');
      el.classList.add('is-exiting');
      setTimeout(function () {
        if (el.parentNode) el.parentNode.removeChild(el);
      }, FADE_OUT_MS);
    }, SHOW_DURATION);
  }

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function poll() {
    var url = '/presence/events/?since=' + encodeURIComponent(lastSeen);
    fetch(url, { credentials: 'same-origin', cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !Array.isArray(data.events) || !data.events.length) return;
        data.events.forEach(function (ev) {
          showToast(ev.message, ev.type);
          // Advance the cursor so we never show the same event twice
          if (ev.ts > lastSeen) lastSeen = ev.ts;
        });
      })
      .catch(function () { /* silent — network blips should not surface errors */ });
  }

  // Small initial delay lets the page fully render before the first poll
  setTimeout(function () {
    poll();
    setInterval(poll, POLL_INTERVAL);
  }, 1200);

})();
