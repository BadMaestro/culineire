/* ============================================================
   ARENA PAGE LAYOUT — the one owner of the page's own geometry.

   AN15, master task section 9: one system owns page-level layout, and a widget
   does not measure its neighbours.

   Until this file existed, the octagon renderer did it. `arena_render.js` -
   whose job is to draw a ring of polygons inside a box it is given - reached
   out of that box, found `.ce-header`, measured everything above it, published
   `--arena-header-h` for a CSS rule in a different file, and owned the four
   triggers that keep the number honest. That is the page's business, not the
   octagon's, and it is why the renderer had an opinion about the site's utility
   bar.

   What lives here now:

     - the NUMBER: `--arena-header-h`, everything above the deck, in pixels;
     - the TRIGGERS that can change it: the header's own box, the window, the
       moment the web fonts settle, and one late pass for whatever arrives
       after paint without announcing itself;
     - and nothing else. The deck's height RULE stays in the stylesheet
       (`100svh - var(--arena-header-h)`), because a rule belongs to CSS. This
       file owns the number that rule reads.

   What consumes it: anything that needs to know the page has re-laid itself,
   through `ArenaPageLayout.subscribe(fn)`. The octagon subscribes and re-fits.
   It no longer knows the site has a header at all.

   The measurements, the formula and the four triggers are UNCHANGED from the
   renderer's own, deliberately - this section moves ownership, and moving
   ownership is not licence to change a pixel. Every comment below records a
   fault that was measured on production and is kept with the code it explains.
   ============================================================ */
(function (global) {
  'use strict';

  // The site header the deck's height is measured against.
  var HEADER_SELECTOR = '.ce-header';
  // One late pass for anything that lands after paint without announcing
  // itself - a lazy banner, a consent strip, an image above the fold.
  var LATE_PASS_MS = 1200;

  var subscribers = [];

  /**
   * Publish the real header height as --arena-header-h.
   *
   * A07, Owner 2026-08-05: the arena fits the screen whole, on every screen.
   * The stylesheet sizes the deck as `100svh - var(--arena-header-h)`, and that
   * variable had never been set by anything - the rule ran on its 146px
   * fallback, which is the DESKTOP header and is wrong by whatever the header
   * actually measures anywhere else. A fit computed from a constant that only
   * holds at one width is not a fit.
   *
   * A18, MEASURED AT 1920x1080 ON PRODUCTION: measuring the HEADER ELEMENT
   * alone gave 146px while the header itself starts 77px down the page, under
   * the site utility bar. The arena overflowed the screen by exactly the height
   * of that bar at every width where it shows, and A07 was quietly false. What
   * the deck needs is not the header's height but everything above it: the
   * header box top plus its height, read from the viewport.
   *
   * Returns true when the value CHANGED, so a caller can skip a re-fit it does
   * not need: fitting the scene is a two-pass measure-and-scale and is not free.
   */
  function measure() {
    var header = document.querySelector(HEADER_SELECTOR);
    if (!header) { return false; }
    var box = header.getBoundingClientRect();
    var height = Math.round(Math.max(0, box.top + window.scrollY) + box.height);
    if (!(height > 0)) { return false; }
    var next = height + 'px';
    if (document.documentElement.style.getPropertyValue('--arena-header-h') === next) {
      return false;
    }
    document.documentElement.style.setProperty('--arena-header-h', next);
    return true;
  }

  function announce(changed, force) {
    for (var i = 0; i < subscribers.length; i++) {
      try { subscribers[i](changed, force); } catch (e) { /* one bad subscriber must not stop the rest */ }
    }
  }

  function remeasure(force) {
    announce(measure(), !!force);
  }

  /**
   * Start watching. Idempotent: a second call adds no second observer.
   *
   * The four triggers, and why each one is here rather than trusted to another:
   *
   * THE HEADER'S OWN BOX, in BORDER-BOX mode - and that mode is the whole of
   * why the first attempt did not land. A ResizeObserver watches the CONTENT
   * box unless told otherwise, and the header grows by twelve pixels of padding
   * after first paint: content box identical, observer silent,
   * --arena-header-h stuck at 134 while the header measured 146.
   *
   * THE WINDOW, always re-fitting whatever the header did. The header-driven
   * path only re-fits when the number CHANGED, and a change of window HEIGHT
   * does not touch the header at all - so the scene, and with it the rank
   * ladder's measured position beside the floor, kept the coordinates it was
   * given at the old size. Measured on production at 1280x520: the ladder hung
   * 19px below the fold and 133px off the floor's centre line.
   *
   * THE FONTS, because they land after init, the header grows, and by then
   * nothing asks again.
   *
   * ONE LATE PASS, for what none of the three can see.
   */
  var watching = false;
  function watch() {
    if (watching) { return; }
    watching = true;
    var header = document.querySelector(HEADER_SELECTOR);
    if (global.ResizeObserver && header) {
      new global.ResizeObserver(function () { remeasure(false); })
        .observe(header, { box: 'border-box' });
    }
    global.addEventListener('resize', function () { remeasure(true); });
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(function () { remeasure(false); }).catch(function () {});
    }
    global.setTimeout(function () { remeasure(true); }, LATE_PASS_MS);
  }

  global.ArenaPageLayout = {
    measure: measure,
    watch: watch,
    /** fn(changed, force) - `force` means re-fit even when the number held. */
    subscribe: function (fn) {
      if (typeof fn === 'function') { subscribers.push(fn); }
    },
    headerSelector: HEADER_SELECTOR
  };
}(window));
