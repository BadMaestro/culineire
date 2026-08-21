/**
 * THE ARENA'S ZOOM LOCK, iOS ONLY.
 *
 * Owner, 2026-08-21: "block zoom for the arena page, on iOS devices."
 *
 * WHY THE PAGE HAS TO DO THIS AT ALL. WKWebView leaks GPU memory on the
 * pinch gesture itself - WebKit bug 172206, "Pinch zoom crash: A problem
 * occurred with this web page so it was reloaded", alongside an
 * independently reported IOSurface leak reaching 3.58GB on a completely
 * EMPTY page after ~20 seconds of pinching. Apple has fixed neither. The
 * Owner's iPhone crashed on the arena in both Safari and Chrome iOS; his
 * Android phone (Blink) never reproduced it once under the same gesture.
 *
 * WHY THE VIEWPORT TAG IS NOT ENOUGH ON ITS OWN. Safari has ignored
 * `user-scalable=no` since iOS 10, deliberately, on accessibility grounds -
 * a page must never be able to trap a reader at a size they cannot enlarge.
 * A WKWebView-based app (Chrome iOS, every in-app browser) does honour the
 * scale limits by default, which is why the ceiling values the Owner tested
 * produced real, differing behaviour on his device rather than none at all.
 * So the meta tag covers one browser and this file covers the other.
 *
 * WHAT IT DOES. preventDefault on WebKit's own `gesturestart`,
 * `gesturechange` and `gestureend` - the non-standard events behind the
 * native pinch, honoured even where the meta tag is ignored. Bound on the
 * DOCUMENT, not the octagon: the leak is charged wherever on the page the
 * gesture happens, so scoping it to the floor would leave the crash
 * reachable a finger-width away on the panel beside it. Double-tap zoom is
 * the other native path in and is closed in CSS (`touch-action:
 * manipulation` on the arena page), not here.
 *
 * These events do not exist outside WebKit, so this is inert everywhere
 * else - and it is gated behind a server-side iOS check besides, because
 * Android and desktop keep the real pinch-zoom they never had a problem
 * with. See _is_ios_webkit in chef_battle/views.py; the same flag drives
 * the viewport meta, so the two can never disagree.
 *
 * A page-owned replacement zoom lived here briefly (v2.5.1168-1171): the
 * pinch read as a plain touch gesture and answered with a CSS transform on
 * the camera. It worked, and it is in the history if it is ever wanted, but
 * the Owner's instruction is that the arena does not zoom on iOS, so
 * carrying that machinery would be dead weight rather than a spare.
 */
(function (global) {
  'use strict';

  function init() {
    if (!global.ARENA_LOCK_ZOOM) { return; }

    function block(event) { event.preventDefault(); }

    document.addEventListener('gesturestart', block, { passive: false });
    document.addEventListener('gesturechange', block, { passive: false });
    document.addEventListener('gestureend', block, { passive: false });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
