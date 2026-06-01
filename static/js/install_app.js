/**
 * CulinEire PWA — install prompt and service-worker registration.
 *
 * Handles:
 *   - Service Worker registration (HTTPS / localhost only)
 *   - Android/Chrome native install prompt (beforeinstallprompt)
 *   - iOS Safari manual "Add to Home Screen" instructions
 *   - Standalone-mode detection (skip everything if already installed)
 *   - Dismiss with 7-day cooldown via localStorage
 */
(function () {
  'use strict';

  // ── Config ──────────────────────────────────────────────────────────────────
  var DISMISS_NATIVE_KEY = 'ce_pwa_dismiss_native';
  var DISMISS_IOS_KEY    = 'ce_pwa_dismiss_ios';
  var COOLDOWN_MS        = 7 * 24 * 60 * 60 * 1000; // 7 days

  // ── Environment detection ───────────────────────────────────────────────────
  var isStandalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  // App is already installed — nothing to do.
  if (isStandalone) return;

  var ua = navigator.userAgent || '';
  var isIOS       = /iphone|ipad|ipod/i.test(ua) && !window.MSStream;
  // iOS Safari but not Chrome-on-iOS or Firefox-on-iOS (those use different UA)
  var isIOSSafari = isIOS && /safari/i.test(ua) && !/crios|fxios|opios/i.test(ua);

  // ── Service Worker registration ─────────────────────────────────────────────
  if ('serviceWorker' in navigator &&
      (location.protocol === 'https:' || location.hostname === 'localhost' || location.hostname === '127.0.0.1')) {
    window.addEventListener('load', function () {
      navigator.serviceWorker.register('/sw.js', { scope: '/' })
        .catch(function (err) {
          // Registration failed — PWA still degrades gracefully.
          // No console noise in production.
        });
    });
  }

  // ── DOM references ──────────────────────────────────────────────────────────
  var banner        = document.getElementById('pwa-install-banner');
  var nativeSection = document.getElementById('pwa-install-native');
  var iosSection    = document.getElementById('pwa-install-ios');
  var installBtn    = document.getElementById('pwa-install-btn');
  var dismissBtn    = document.getElementById('pwa-install-dismiss');
  var iosDismissBtn = document.getElementById('pwa-install-ios-dismiss');

  // Nothing to do if the banner markup is absent.
  if (!banner) return;

  // ── Utilities ───────────────────────────────────────────────────────────────
  function isDismissed(key) {
    try {
      var ts = localStorage.getItem(key);
      return ts ? (Date.now() - parseInt(ts, 10)) < COOLDOWN_MS : false;
    } catch (e) {
      return false;
    }
  }

  function markDismissed(key) {
    try { localStorage.setItem(key, String(Date.now())); } catch (e) {}
  }

  var autoHideTimer = null;
  var DESKTOP_AUTOHIDE_MS = 5000; // 5 s on non-touch screens

  function isDesktop() {
    return !window.matchMedia('(hover: none)').matches;
  }

  function showBanner() {
    banner.hidden = false;
    if (isDesktop()) {
      clearTimeout(autoHideTimer);
      autoHideTimer = setTimeout(function () { hideBanner(); }, DESKTOP_AUTOHIDE_MS);
    }
  }
  function hideBanner() {
    clearTimeout(autoHideTimer);
    banner.hidden = true;
  }

  // ── Android / Chrome: native install prompt ─────────────────────────────────
  var deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', function (e) {
    e.preventDefault();
    deferredPrompt = e;

    if (isDismissed(DISMISS_NATIVE_KEY)) return;

    if (nativeSection) nativeSection.hidden = false;
    if (iosSection)    iosSection.hidden    = true;
    showBanner();
  });

  window.addEventListener('appinstalled', function () {
    hideBanner();
    deferredPrompt = null;
  });

  if (installBtn) {
    installBtn.addEventListener('click', function () {
      if (!deferredPrompt) return;
      deferredPrompt.prompt();
      deferredPrompt.userChoice.then(function () {
        deferredPrompt = null;
        hideBanner();
      });
    });
  }

  if (dismissBtn) {
    dismissBtn.addEventListener('click', function () {
      markDismissed(DISMISS_NATIVE_KEY);
      hideBanner();
    });
  }

  // ── iOS Safari: manual "Add to Home Screen" instructions ────────────────────
  // Only show once per cooldown period; never show inside standalone mode.
  if (isIOSSafari && !isDismissed(DISMISS_IOS_KEY)) {
    if (iosSection)    iosSection.hidden    = false;
    if (nativeSection) nativeSection.hidden = true;
    showBanner();
  }

  if (iosDismissBtn) {
    iosDismissBtn.addEventListener('click', function () {
      markDismissed(DISMISS_IOS_KEY);
      hideBanner();
    });
  }

  // ── Keyboard accessibility: Escape closes the banner ────────────────────────
  document.addEventListener('keydown', function (e) {
    if ((e.key === 'Escape' || e.key === 'Esc') && !banner.hidden) {
      // Treat Escape as a soft dismiss (same cooldown as the X button).
      if (nativeSection && !nativeSection.hidden) markDismissed(DISMISS_NATIVE_KEY);
      if (iosSection    && !iosSection.hidden)    markDismissed(DISMISS_IOS_KEY);
      hideBanner();
    }
  });

})();
