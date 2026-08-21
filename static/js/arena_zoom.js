/**
 * THE ARENA'S ZOOM LOCK, iOS ONLY.
 *
 * Owner, 2026-08-21: block zoom for the arena page on iOS devices.
 *
 * WHY THE PAGE HAS TO DO THIS AT ALL. WKWebView leaks GPU memory on the
 * pinch gesture itself - WebKit bug 172206, "Pinch zoom crash: A problem
 * occurred with this web page so it was reloaded", alongside an
 * independently reported IOSurface leak reaching 3.58GB on a completely
 * EMPTY page after ~20 seconds of pinching. Apple has fixed neither. The
 * Owner's iPhone crashed on the arena in both Safari and Chrome iOS; his
 * Android phone (Blink) never reproduced it once under the same gesture,
 * which is why this is scoped to iOS and every other engine keeps the
 * pinch-zoom it never had a problem with.
 *
 * FOUR LAYERS, because iOS closes none of these doors on its own and each
 * layer leaves a different one open:
 *
 *   1. the viewport meta tag - honoured by WKWebView apps (Chrome iOS and
 *      every in-app browser), IGNORED by Safari, which has refused
 *      `user-scalable=no` since iOS 10 on accessibility grounds;
 *   2. `touch-action: pan-y` on the arena body (arena.css) - the CSS-level
 *      statement that this page pans vertically and does nothing else. This
 *      replaced `touch-action: manipulation`, which was WRONG for the job:
 *      manipulation is "auto minus double-tap-zoom" and still permits pinch,
 *      so the first attempt at this lock closed the double tap and left the
 *      pinch wide open;
 *   3. the touch handlers below - any touchmove carrying more than one
 *      finger, or a WebKit `scale` that is not 1, is cancelled outright;
 *   4. the `gesturestart`/`gesturechange`/`gestureend` handlers below -
 *      WebKit's own non-standard gesture events, honoured where the meta tag
 *      is not.
 *
 * Every listener is registered with `{ passive: false }`, and that is
 * load-bearing rather than a detail: touch listeners default to passive in
 * modern browsers, and preventDefault is silently a no-op inside a passive
 * listener. A version of this file without those options would look exactly
 * like this one and do nothing at all.
 *
 * Everything is bound on the DOCUMENT rather than the octagon: the leak is
 * charged wherever on the page the gesture happens, so scoping it to the
 * floor would leave the crash reachable a finger-width away on the panel
 * beside it.
 *
 * A page-owned replacement zoom lived here briefly (v2.5.1168-1171): the
 * pinch read as a plain touch gesture and answered with a CSS transform on
 * the camera. It worked and it is in the history if it is ever wanted, but
 * the instruction is that the arena does not zoom on iOS, so carrying that
 * machinery would be dead weight rather than a spare.
 */
(function (global) {
  'use strict';

  function init() {
    if (!global.ARENA_LOCK_ZOOM) { return; }

    function block(event) {
      event.preventDefault();
    }

    /* A second finger landing is already the start of a pinch; refusing it
       here is cheaper than unwinding a gesture that has begun. */
    function blockMultiTouch(event) {
      if (event.touches && event.touches.length > 1) {
        event.preventDefault();
      }
    }

    /* `scale` is WebKit's own reading of the pinch and is the signal that
       survives when a finger count alone would not - a gesture continuing
       after one finger lifts still reports a scale away from 1. */
    function blockScaledMove(event) {
      if (
        (event.touches && event.touches.length > 1) ||
        (typeof event.scale === 'number' && event.scale !== 1)
      ) {
        event.preventDefault();
      }
    }

    document.addEventListener('touchstart', blockMultiTouch, { passive: false });
    document.addEventListener('touchmove', blockScaledMove, { passive: false });

    document.addEventListener('gesturestart', block, { passive: false });
    document.addEventListener('gesturechange', block, { passive: false });
    document.addEventListener('gestureend', block, { passive: false });

    /* Double-tap zoom is closed by touch-action in arena.css rather than
       here: it is a CSS-level statement about the page and a handler that
       had to guess at tap timing would be a worse version of it. */
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
