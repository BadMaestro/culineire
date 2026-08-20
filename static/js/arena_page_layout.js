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

  /**
   * Publish --arena-deck-top-h: what the furniture above the floor occupies in
   * the caption's own column, measured from the top of the deck.
   *
   * AN-R1/B, 2026-08-09. This is a PAGE-LEVEL fact and it belongs here, beside
   * --arena-header-h, for the same reason: it says where the page's own panels
   * ended up, and no component should be finding that out for itself. The
   * floor layer turns it into a grid row, the caption gets the row under it,
   * and the octagon gets what is left.
   *
   * Only the broadcast ribbon stands between the top of the deck and the floor
   * in that column. The cooking widget is a left-hand HUD and is deliberately
   * not counted - it ends above the floor too and is nowhere near the caption,
   * and counting it is how a measured fix gets the wrong answer with a
   * straight face.
   */
  function measureDeckTop() {
    var deck = document.querySelector('.arena-command-deck');
    if (!deck) { return false; }
    var ribbon = deck.querySelector('.arena-broadcast-ribbon');
    // MEASURED FROM THE FLOOR LAYER, NOT FROM THE DECK.
    //
    // AN-R2/2, 2026-08-09. The number is the first row of the floor's own
    // grid, so it has to be an offset within the floor's box. It was taken
    // from the deck's box, and the deck carries a 1px border, so the row
    // was one pixel too tall and everything under it - the writing, the
    // clear air above it, the octagon's region - sat one pixel low. That
    // is the whole of the caption's remaining 1px, measured: accepted 235,
    // rendered 236.
    var floor = deck.querySelector('.arena-command-deck__floor');
    var top = 0;
    if (ribbon && floor) {
      var floorBox = floor.getBoundingClientRect();
      var box = ribbon.getBoundingClientRect();
      if (box.height > 0) { top = Math.max(0, Math.round(box.bottom - floorBox.top)); }
    }
    var next = top + 'px';
    if (deck.style.getPropertyValue('--arena-deck-top-h') === next) { return false; }
    deck.style.setProperty('--arena-deck-top-h', next);
    return true;
  }

  /**
   * Publish --arena-caption-nudge-x: how far the writing must step aside so a
   * page panel does not stand on it.
   *
   * AN-R1/B. This is the page's business and not the caption's. The caption is
   * centred on the floor by the stylesheet; when a panel reaches into its band
   * - the metrics card does, at every width measured - the page says by how
   * much the band is blocked, and the stylesheet steps the writing aside by
   * exactly that much and no more.
   *
   * It is the same kind of fact as --arena-deck-top-h: where the page's own
   * furniture ended up. The caption never measures a neighbour; it is told.
   *
   * Measured at 1280x800 before this existed: a centred caption ran 69px into
   * the metrics card and 43px down it. That is the Owner's own report of
   * 2026-08-07 - "блоки опять наезжают друг на друга" - reappearing the moment
   * the old measurement-based placement was removed, which is why the page has
   * to answer it instead.
   */
  function measureCaptionBand() {
    var deck = document.querySelector('.arena-command-deck');
    var caption = deck && deck.querySelector('.arena-floor-caption');
    if (!deck || !caption) { return false; }
    var GAP = 8;
    var box = caption.getBoundingClientRect();
    // Measure the caption where it WOULD be with no nudge, by adding back the
    // one already applied. Reading its nudged position instead makes the
    // measurement depend on its own last answer: it steps aside, the overlap
    // disappears, the nudge returns to zero, and it steps back - measured,
    // that oscillated between 77px and 0.
    var applied = parseFloat(deck.style.getPropertyValue('--arena-caption-nudge-x')) || 0;
    var left = box.left + applied;
    var right = box.right + applied;
    var nudge = 0;
    if (box.width > 0) {
      var panels = deck.querySelectorAll('.arena-command-deck__metrics, .arena-command-deck__phase-card');
      for (var i = 0; i < panels.length; i++) {
        var p = panels[i].getBoundingClientRect();
        if (!(p.width > 0) || !(p.height > 0)) { continue; }
        if (p.bottom <= box.top || p.top >= box.bottom) { continue; }   // not in the band
        if (p.left >= right || p.right <= left) { continue; }           // not in the way
        if (p.left > left) { nudge = Math.max(nudge, right - (p.left - GAP)); }
      }
    }
    var next = Math.round(nudge) + 'px';
    if (deck.style.getPropertyValue('--arena-caption-nudge-x') === next) { return false; }
    deck.style.setProperty('--arena-caption-nudge-x', next);
    return true;
  }

  function announce(changed, force) {
    for (var i = 0; i < subscribers.length; i++) {
      try { subscribers[i](changed, force); } catch (e) { /* one bad subscriber must not stop the rest */ }
    }
  }

  /**
   * Publish --arena-left-stack-top: where the lower-left stack may begin.
   *
   * 2026-08-18, with the spectator chat. The stack - crown ladder above,
   * spectator chat below - is anchored to the floor and must not reach up into
   * the status card above it. The card's height is decided by its CONTENT, so
   * no percentage is right on two screens at once: a cap tuned at 1280x720 left
   * the pair three pixels short at 1000x625 and the composer fell out of its
   * panel. Percentages were guessing at a number the page can simply measure,
   * which is what --arena-header-h and --arena-deck-top-h already do here.
   *
   * Measured as an offset inside the floor's box, like measureDeckTop, because
   * that is the box the stack is positioned in.
   */
  function measureLeftStack() {
    var deck = document.querySelector('.arena-command-deck');
    if (!deck) { return false; }
    var card = deck.querySelector('.arena-command-deck__phase-card');
    var floor = deck.querySelector('.arena-command-deck__floor');
    if (!card || !floor) { return false; }
    var cardBox = card.getBoundingClientRect();
    var floorBox = floor.getBoundingClientRect();
    if (cardBox.height <= 0 || floorBox.height <= 0) { return false; }
    // A little air under the card, matching the gap the stack keeps inside
    // itself, so the two panels do not touch.
    var top = Math.max(0, Math.round(cardBox.bottom - floorBox.top) + 9);
    var next = top + 'px';
    if (deck.style.getPropertyValue('--arena-left-stack-top') === next) { return false; }
    deck.style.setProperty('--arena-left-stack-top', next);
    return true;
  }

  function remeasure(force) {
    var header = measure();
    var regions = measureDeckTop();
    var band = measureCaptionBand();
    var stack = measureLeftStack();
    announce(header || regions || band || stack, !!force);
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
    // COALESCED, not raw - found 2026-08-20 chasing an iPhone crash on pinch-
    // zoom. On iOS, a pinch gesture fires `resize` on the window repeatedly
    // WHILE THE GESTURE IS HAPPENING, not once at the end (a documented iOS
    // quirk, unlike desktop browsers). Each firing ran remeasure(true)
    // synchronously - force=true, so it always called every subscriber,
    // including the octagon's fitScene(): a forced layout read, a full
    // re-position of 300+ SVG nodes, on every one of however many resize
    // events one continuous two-finger gesture produces. Nothing here
    // throttled it. One rAF slot now holds at most one pending remeasure, so
    // a burst of resize events across one frame collapses to the one
    // recalculation that frame can actually show.
    var resizeFrame = null;
    global.addEventListener('resize', function () {
      if (resizeFrame !== null) { return; }
      resizeFrame = global.requestAnimationFrame(function () {
        resizeFrame = null;
        remeasure(true);
      });
    });
    if (document.fonts && document.fonts.ready && document.fonts.ready.then) {
      document.fonts.ready.then(function () { remeasure(false); }).catch(function () {});
    }
    global.setTimeout(function () { remeasure(true); }, LATE_PASS_MS);
  }

  global.ArenaPageLayout = {
    /** Both page-level numbers in one call: the header, and the regions. */
    measure: function () {
      var header = measure();
      var regions = measureDeckTop();
      var band = measureCaptionBand();
      return header || regions || band;
    },
    watch: watch,
    /** fn(changed, force) - `force` means re-fit even when the number held. */
    subscribe: function (fn) {
      if (typeof fn === 'function') { subscribers.push(fn); }
    },
    headerSelector: HEADER_SELECTOR
  };
}(window));
