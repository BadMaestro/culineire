/**
 * THE ARENA'S OWN PINCH-ZOOM.
 *
 * Owner, 2026-08-20/21. The arena crashed his iPhone every time he pinched
 * it, in both Safari and Chrome iOS (both are WKWebView) and never once on
 * Android (Blink). That is WebKit bug 172206 - "Pinch zoom crash: A problem
 * occurred with this web page so it was reloaded" - alongside an
 * independently reported IOSurface leak in WKWebView reaching 3.58GB on a
 * completely EMPTY page after ~20 seconds of pinching. Apple has not fixed
 * either.
 *
 * WHY THE CEILING APPROACH WAS ABANDONED. maximum-scale was walked down the
 * ladder on his device - 2.5, 1.5, 1.3, 1.2, 1.1 - and every value that left
 * ANY native zoom available still crashed. The only configuration that did
 * not was the full stop. The leak is charged per GESTURE, not per distance
 * travelled, so narrowing the range never removed the thing that leaks. That
 * is the whole reason this file exists rather than another number.
 *
 * WHAT THIS DOES INSTEAD. Native page zoom stays off (the arena page's
 * viewport meta says so). The pinch is read here as an ordinary touch
 * gesture and answered with a CSS transform on the camera viewport, which is
 * a compositor operation on one element - not the viewport-scaling path that
 * leaks. The user gets the zoom he actually wanted; WebKit never runs the
 * code that crashes.
 *
 * OWNERSHIP, because this file's neighbours are strict about it.
 * arena_render.js owns --arena-camera-scale/x/y and keeps owning them: it
 * decides where the octagon SITS. This file writes only --arena-user-zoom
 * and --arena-user-pan-x/y, which the stylesheet composes as separate steps
 * of the same transform. Neither writes the other's variables, so a re-fit
 * (rotation, address bar, a real resize) does not fight a zoom and a zoom
 * does not survive as a stale offset the renderer cannot see.
 */
(function (global) {
  'use strict';

  var MIN_ZOOM = 1;
  var MAX_ZOOM = 4;
  /* Below this a "zoom" is indistinguishable from a fumbled tap, and holding
     the pan/scroll takeover open for it would cost the page its normal
     scrolling for nothing. */
  var ZOOM_EPSILON = 0.01;

  var camera = null;
  var zoom = 1;
  var panX = 0;
  var panY = 0;

  /* Gesture state. Null when no pinch is in progress. */
  var startDistance = 0;
  var startZoom = 1;
  var pinching = false;

  /* One-finger pan, only ever active while zoomed in. */
  var panning = false;
  var panStartX = 0;
  var panStartY = 0;
  var panOriginX = 0;
  var panOriginY = 0;

  function clamp(value, low, high) {
    return value < low ? low : (value > high ? high : value);
  }

  function write() {
    camera.style.setProperty('--arena-user-zoom', zoom.toFixed(4));
    camera.style.setProperty('--arena-user-pan-x', panX.toFixed(1) + 'px');
    camera.style.setProperty('--arena-user-pan-y', panY.toFixed(1) + 'px');
    /* The class is what turns off the browser's own touch handling, and it
       is only on while there is something to pan. At rest the octagon must
       not be a hole the page cannot be scrolled through. */
    var engaged = zoom > MIN_ZOOM + ZOOM_EPSILON;
    camera.classList.toggle('is-user-zoomed', engaged);
    var floor = camera.parentElement;
    if (floor) { floor.classList.toggle('is-user-zoomed', engaged); }
  }

  function reset() {
    zoom = 1;
    panX = 0;
    panY = 0;
    write();
  }

  function distanceBetween(a, b) {
    var dx = a.clientX - b.clientX;
    var dy = a.clientY - b.clientY;
    return Math.sqrt(dx * dx + dy * dy) || 1;
  }

  function midpointOf(a, b) {
    return {
      x: (a.clientX + b.clientX) / 2,
      y: (a.clientY + b.clientY) / 2
    };
  }

  /**
   * Zoom about the point the fingers are actually over, rather than about
   * the middle of the octagon.
   *
   * The camera's placed centre on screen is its own rect centre, which
   * already includes the pan we wrote; so with M the pinch midpoint and
   * (Z -> Z') the zoom change, holding the content under M still gives
   *
   *     pan' = pan + (M - rectCentre) * (1 - Z'/Z)
   *
   * which needs no knowledge of the camera's internal scale or of where the
   * renderer decided to put it - the two things this file must not read as
   * if it owned them.
   */
  function zoomAbout(nextZoom, midpoint) {
    var rect = camera.getBoundingClientRect();
    var centreX = rect.left + rect.width / 2;
    var centreY = rect.top + rect.height / 2;
    var ratio = nextZoom / zoom;
    panX += (midpoint.x - centreX) * (1 - ratio);
    panY += (midpoint.y - centreY) * (1 - ratio);
    zoom = nextZoom;
    write();
  }

  function onTouchStart(event) {
    if (event.touches.length === 2) {
      pinching = true;
      panning = false;
      startDistance = distanceBetween(event.touches[0], event.touches[1]);
      startZoom = zoom;
      event.preventDefault();
      return;
    }
    if (event.touches.length === 1 && zoom > MIN_ZOOM + ZOOM_EPSILON) {
      panning = true;
      panStartX = event.touches[0].clientX;
      panStartY = event.touches[0].clientY;
      panOriginX = panX;
      panOriginY = panY;
    }
  }

  function onTouchMove(event) {
    if (pinching && event.touches.length === 2) {
      var next = clamp(
        startZoom * (distanceBetween(event.touches[0], event.touches[1]) / startDistance),
        MIN_ZOOM,
        MAX_ZOOM
      );
      zoomAbout(next, midpointOf(event.touches[0], event.touches[1]));
      event.preventDefault();
      return;
    }
    if (panning && event.touches.length === 1) {
      panX = panOriginX + (event.touches[0].clientX - panStartX);
      panY = panOriginY + (event.touches[0].clientY - panStartY);
      write();
      event.preventDefault();
    }
  }

  function onTouchEnd(event) {
    if (event.touches.length < 2) { pinching = false; }
    if (event.touches.length === 0) {
      panning = false;
      /* Snapping home from a near-rest zoom keeps the page scrollable: a
         zoom of 1.004 left behind by a clumsy release would otherwise hold
         the touch takeover open forever. */
      if (zoom <= MIN_ZOOM + ZOOM_EPSILON) { reset(); }
    }
  }

  function init() {
    /* ONLY WHERE THE BROWSER'S OWN ZOOM WAS TAKEN AWAY. The page decides
       that once, server-side, from the engine it is being served to (see
       _is_ios_webkit in chef_battle/views.py) and publishes the answer here,
       so this file and the viewport meta tag can never disagree. Everywhere
       but iOS the real pinch-zoom is still live and better than anything
       written here; running both would put two zooms on one gesture. */
    if (!global.ARENA_OWN_ZOOM) { return; }

    var svg = document.getElementById('arena-render');
    camera = svg && svg.parentElement;
    if (!camera) { return; }

    /* THE META TAG DOES NOT ACTUALLY DISABLE ZOOM ON iOS, and finding that
       out is what this block is for. Safari has IGNORED user-scalable,
       maximum-scale and minimum-scale since iOS 10, deliberately, on
       accessibility grounds - Apple's position is that a page must never be
       able to trap a reader at a text size they cannot enlarge.
       (https://bugzilla.mozilla.org/show_bug.cgi?id=1340064 records the same
       behaviour change from the other side of the fence.)
       Every ceiling walked down the Owner's device - 2.5, 1.5, 1.3, 1.2,
       1.1 - was therefore never applied at all, which is the real reason
       none of them changed anything.

       `gesturestart` and its siblings are the WebKit-only events behind the
       native pinch, and preventDefault on them DOES stop it where the meta
       tag is ignored. That is the whole mechanism this file needs: the
       leaking gesture never starts, and the same pinch is answered by the
       touch handlers below with a CSS transform instead.

       Bound on the DOCUMENT rather than the octagon on purpose. The leak is
       charged per gesture wherever on the page it happens, and a pinch that
       begins on a panel beside the floor is the same gesture; scoping it to
       the octagon would leave the crash reachable one finger-width away.
       Non-standard and inert everywhere else - these events simply never
       fire outside WebKit. */
    var blockNativeGesture = function (event) { event.preventDefault(); };
    document.addEventListener('gesturestart', blockNativeGesture, { passive: false });
    document.addEventListener('gesturechange', blockNativeGesture, { passive: false });
    document.addEventListener('gestureend', blockNativeGesture, { passive: false });

    camera.addEventListener('touchstart', onTouchStart, { passive: false });
    camera.addEventListener('touchmove', onTouchMove, { passive: false });
    camera.addEventListener('touchend', onTouchEnd, { passive: true });
    camera.addEventListener('touchcancel', onTouchEnd, { passive: true });

    /* Two taps put it back, which is the gesture everyone already tries and
       the only way back to a scrollable page from a deep zoom. */
    var lastTap = 0;
    camera.addEventListener('touchend', function (event) {
      if (event.touches.length !== 0) { return; }
      var now = Date.now();
      if (now - lastTap < 320 && zoom > MIN_ZOOM + ZOOM_EPSILON) {
        reset();
        lastTap = 0;
        return;
      }
      lastTap = now;
    }, { passive: true });

    /* A re-fit moves the octagon under a zoom that was measured against the
       old placement, so the zoom goes home rather than being left pointing
       at a part of the floor that is no longer there. ArenaPageLayout only
       announces real layout changes - a pinch cannot trigger this. */
    if (global.ArenaPageLayout && global.ArenaPageLayout.subscribe) {
      global.ArenaPageLayout.subscribe(function (changed, force) {
        if ((changed || force) && zoom > MIN_ZOOM + ZOOM_EPSILON) { reset(); }
      });
    }

    global.ArenaZoom = { reset: reset };
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
