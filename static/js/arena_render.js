/*
 * Unified Chef Battles Arena renderer.
 *
 * Merges the two arenas that existed side by side:
 *   - structure  <- procedural geometry (ArenaGeometry.cellVertices, chord-lerp
 *                   octagon). Every ring, its rank key and its seat capacity come
 *                   from payload.geometry. Nothing about the grid is hardcoded here.
 *   - behaviour  <- the legacy arena_puzzle.js interaction layer (cell-shaped
 *                   avatars, tooltip, ripple, presence ping, live poll).
 *
 * Layer boundary: this file owns rendering only. ArenaGeometry owns the maths;
 * the payload owns the data. Effects read data-* attributes and never the payload.
 */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  // Native Sponsors puzzle coordinates (sponsors_puzzle.js) — do not rescale
  // the shell. Arena copies that octagon 1:1; only the bound data differs.
  var TPL_CX = 550;
  var TPL_CY = 550;
  var SVG_SIZE = 1100; // legacy alias for helpers that still read a canvas size
  var OUTER_MARGIN = 26;
  // STAGE_RADIUS follows the arena octagon's crown plate (85 − gap).
  var STAGE_RADIUS = 82;

  /**
   * Where the three rings of lamps stand. Radius is a MULTIPLE of the stage
   * radius, never a pixel count, so the whole rig follows a stage resize; angle
   * is degrees of offset inside one 45-degree face, and eight-fold symmetry is
   * assumed everywhere so only that offset is free.
   *
   * These numbers are the Owner's own, read off the lamp console on 2026-07-31.
   * The console writes a live override into ArenaLampLayout; when he has not
   * moved anything, or the console is not loaded at all, these apply.
   */
  var LAMP_DEFAULTS = {
    outer: { r: 1.1280, deg: 0.0 },    // plate, both beams
    inner: { r: 0.9475, deg: 22.7 },   // plate, inward beam only
    moat: { r: 1.3161, deg: 0.2 }      // no beam — carries the travelling spot
  };

  // The three strobe rings a beamless lamp throws, as multiples of the stage
  // radius: small, medium, large. Sized so the largest still dies well inside
  // the rank rings instead of washing the floor.
  var STROBE_RINGS = [0.30, 0.55, 0.85];

  function lampLayout() {
    var live = global.ArenaLampLayout || {};
    var out = {};
    var keys = ['outer', 'inner', 'moat'];
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i];
      var set = live[k] || {};
      out[k] = {
        r: typeof set.r === 'number' && isFinite(set.r) ? set.r : LAMP_DEFAULTS[k].r,
        deg: typeof set.deg === 'number' && isFinite(set.deg) ? set.deg : LAMP_DEFAULTS[k].deg
      };
    }
    return out;
  }
  // Crown nick capacity at name Y (dy ≈ 0.44·R, font ≈ 0.16·R): usable ≈ 130
  // SVG units. Measured live: ~14 uppercase / ~17 mixed; hard ceiling = 14.
  // Keep in lockstep with recipes.models.RecipeAuthor.PEN_NAME_MAX_LENGTH.
  var CROWN_NAME_MAX_CHARS = 14;
  var CROWN_NAME_Y_FACTOR = 0.44;
  var CROWN_NAME_PAD = 6;
  // Adaptive nick type: short names grow toward MAX, long ones settle near MIN,
  // then width-fit clamps so the chord never overflows.
  var CROWN_NAME_FONT_MAX = 0.24;
  var CROWN_NAME_FONT_MIN = 0.125;
  var CROWN_NAME_FILL = 0.90;
  var POLL_INTERVAL = 10000;
  var PING_INTERVAL = 20000;
  // Cells are inset toward their own centroid to open the seams. Proportional
  // rather than a fixed pixel gap so inner rings (small cells) keep the same

  // G1/G5 — docs/chef_battle/arena_mockup_spec.json proportions (NO tilt in this slice).
  // Mockup stands_outer 1.60 R_floor is the OUTERMOST VISIBLE EXTENT (bbox), not
  // seat centres. G4 measured bbox M3=1.7541 with centres at 1.60; G5 shrinks
  // construction so projected bbox lands on 1.60 (1.60²/1.7541 ≈ 1.4594).
  // Floor span 0.63 is an OUTPUT after fit-by-stands; stage = 0.13 × floor;
  // composition centre at 0.50 W / 0.51 H.
  // Removed here because nothing read them: FLOOR_SHARE 0.63, STAGE_RATIO 0.13
  // and VERTICAL_COMPRESSION 0.56 were declared and never used. All three are
  // recorded values, not working code, and they remain in
  // docs/chef_battle/arena_mockup_spec.json, which is the authoritative copy.
  // Note VERTICAL_COMPRESSION 0.56 = cos(56deg) — the spec's camera tilt. The
  // live camera is rotateX(42deg), so that acceptance figure never described
  // what ships; keeping it in the source implied otherwise.
  var STANDS_RATIO = 1.60 * 1.60 / 1.7541;

  // ============================================================
  // THE PRODUCT LAYOUT CONTRACT FOR THE OCTAGON.
  //
  // Owner, 2026-08-09: "THE ACCEPTED OCTAGON SIZE AND POSITION MUST REMAIN",
  // and the historical sentence "the floor stands inside its frame at 64%"
  // is no longer authoritative, because the accepted composition was never
  // produced by it - it emerged from fitScene's iterative multiplication,
  // reserveCaptionBand's multiplication on top of that, and the old
  // camera/container relationship. A rule that did not produce the accepted
  // result cannot be quoted as the reason to keep it.
  //
  // So the accepted composition IS the contract now. These are not numbers
  // copied off a screenshot to make an implementation reproduce a picture -
  // that is what REGION_FILL_X 0.5197 was, and it is gone. They are the
  // Owner's accepted design proportions promoted to the product
  // specification, and their provenance is written beside them:
  //
  //   reference viewport   1280x800
  //   octagon page region  x 1..1269, y 235..799   (1268 x 564)
  //   accepted octagon     [305, 284, 659, 454], centre (634.5, 511)
  //
  // Everything below is region-relative, so it holds at every viewport.
  // ============================================================

  // Width first, because the octagon is a square SVG under a FIXED camera:
  // one number decides its rendered size and the height follows from the
  // projection rather than being a second decision. 659 of the region's 1268.
  var OCTAGON_VISUAL_WIDTH_SHARE = 659 / 1268;
  // Horizontally the composition is simply centred, and this is structural
  // rather than measured: 0.5 of 1268 is 634, against an accepted 634.5.
  var OCTAGON_VISUAL_CENTRE_X = 0.5;
  // Vertically it is deliberately NOT centred - the floor sits high so the
  // crowd rail and the lower dock read beneath it. 276 of the region's 564:
  // accepted centre 511 in a region whose top edge is 235.
  var OCTAGON_VISUAL_CENTRE_Y = 276 / 564;
  // A ceiling, not a target: on a short screen the octagon must not spill out
  // of the region it was given. It does not decide the size when there is room.
  var REGION_MAX_Y = 0.95;
  // AN15: the site header belongs to ArenaPageLayout. This renderer draws
  // inside the box it is given and does not look for its neighbours.
  // A09: clear floor between the crown block and a fighter block, as a fraction
  // of the floor's width. Measured off the reference — see fighterOffset().
  var REFERENCE_FIGHTER_GAP = 0.044153;

  var pollTimer = null;
  var pingTimer = null;
  // AA1: the geometry_version we last received, from first paint or the most
  // recent poll. Sent back on every poll so the server can omit the (large,
  // static-per-deploy) geometry payload when nothing about it has changed.
  var lastGeometryVersion = null;
  // Latest centre payload, so a stage click knows which battle room to open.
  var stageCentre = null;
  // Centre identity from the last bind; null until the first one, so a page
  // load does not replay an arrival that happened before the viewer arrived.
  var centreKey = null;

  function el(tag, attrs) {
    var node = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (key) {
      node.setAttribute(key, attrs[key]);
    });
    return node;
  }

  function pointString(point) {
    return point.x.toFixed(2) + ',' + point.y.toFixed(2);
  }

  /* ---------------------------------------------------------------- */
  /* Projection — the floor is a plane seen from a camera, not a plan   */
  /* ---------------------------------------------------------------- */

  // We never had perspective. The scene was a flat octagon tilted by a CSS
  // rotateX, which foreshortens it but does not make the far side NARROWER:
  // measured on production, our near and far edges came out 103.1px and
  // 103.1px, a ratio of exactly 1.000, while the hall photograph behind it
  // converges to 0.51. A parent `perspective` did not change that at any value
  // from 1500 down to 300 — so the fix is a real projection, not a parameter.
  //
  // CONVERGENCE is the single number that describes it: how wide the far edge
  // is compared with the near one. 0.51 is measured off the backdrop; change
  // the picture and this is the one value to re-measure.
  //
  // For a floor point at depth v (-1 far, +1 near) the width scale is
  //   s(v) = A / (B - v),  B = (1+k)/(1-k),  A = B - 1
  // which gives exactly s(-1) = k and s(+1) = 1. The vertical positions are
  // the integral of that scale, so rows crowd together as they recede the way
  // they do in the photograph, rather than sitting at even spacing.
  // 0 = flat. The owner's call: the arena is looked at from straight above, so
  // there is no tilt and no convergence at all. The projection below is kept
  // whole rather than deleted - put a number back in here and the camera
  // returns without rewriting anything.
  var CONVERGENCE = 0;

  /**
   * G1 plan-space radii. Ring counts/segments stay in get_arena_geometry;
   * only the radial projection changes here so floor/stands/stage hit the
   * measured mockup ratios without rotateX (G2 owns the camera).
   */
  function g1Radii(geometry) {
    // Exact sponsors radii — scale 1. Stands squeeze into the same viewBox
    // (30 30 1040 1040) just outside ring 6 so the octagon itself is untouched.
    var tpl = global.ArenaOctagon;
    var floorOuter = tpl ? tpl.OUTER : 515;
    var stageR = tpl ? tpl.CROWN_OUTER : 85;
    var gap = tpl ? tpl.GAP : 3;
    STAGE_RADIUS = stageR - gap;
    // THE STANDS HAD FIVE UNITS OF DEPTH AND ASKED FOR FORTY-EIGHT.
    //
    // This was `Math.min(520, floorOuter + 48)`. With floorOuter 515 the
    // request was 563 and the answer was 520, so the whole gallery - 114
    // seats in two rows - was squeezed into a band FIVE units deep while a
    // single seat is about thirteen across. They overlapped into the "grey
    // dot grid around the floor" that a later card hid with opacity:0, so
    // the seats were not hidden for being empty; they were hidden for being
    // crushed.
    //
    // The canvas was never the constraint: viewBox is 0 0 1100 1100, centre
    // 550, and the octagon ends at 515 - thirty-five units stood unused.
    // The ceiling now leaves a small margin to the canvas edge so a seat's
    // stroke and glow are not clipped, and the +48 request is honoured when
    // it fits.
    var CANVAS_EDGE_MARGIN = 6;
    var standsOuter = Math.min(TPL_CX - CANVAS_EDGE_MARGIN, floorOuter + 48);
    var rankStep = (floorOuter - stageR) / 6;
    return {
      standsOuter: standsOuter,
      floorOuter: floorOuter,
      stageR: stageR,
      rankStep: rankStep,
      templateScale: 1,
      cx: TPL_CX,
      cy: TPL_CY
    };
  }
  // Neither number is the measurement itself. CONVERGENCE describes the whole
  // depth span, while what has to match is the OCTAGON's own far and near
  // edges, which sit at 0.59 of that span - and VERTICAL_SQUASH acts on the
  // span too, while the target is the finished shape's height. Both were
  // solved together against the two measurements taken off the backdrop:
  // far edge 0.51 of the near one, height 0.437 of the width. Solving one at a
  // time moved the other, which is why an earlier pass matched the height
  // exactly and pushed the corners further out.
  var VERTICAL_SQUASH = 1;

  function projector() {
    var k = CONVERGENCE;
    // Flat: a plan view, drawn exactly as the geometry contract lays it out.
    if (!(k > 0) || k >= 1) {
      return function (point) { return { x: point.x, y: point.y }; };
    }
    var B = (1 + k) / (1 - k);
    var A = B - 1;
    var half = SVG_SIZE / 2;
    var span = half - OUTER_MARGIN;
    var full = A * Math.log((B + 1) / (B - 1));

    return function (point) {
      var dx = point.x - half;
      var dy = point.y - half;
      var v = Math.max(-1, Math.min(1, dy / span));
      var scale = A / (B - v);
      var travel = A * Math.log((B + 1) / (B - v));
      return {
        x: half + dx * scale,
        y: half + ((2 * travel / full) - 1) * span * VERTICAL_SQUASH
      };
    };
  }

  /* ---------------------------------------------------------------- */
  /* Grid — drawn once from geometry, then only re-stamped by bind()   */
  /* ---------------------------------------------------------------- */

  // The octagon at a given radius, as an SVG points string.
  // Orientation matches the Sponsors puzzle template (vertices at 0°, 45°, …)
  // via the arena's own ArenaOctagon — geometrically the same shell the
  // sponsors floor uses, but a copy the arena owns (Owner, 2026-07-30).
  function ringOutline(radius, sides) {
    var tpl = global.ArenaOctagon;
    if (tpl) {
      return tpl.octagonPoints(TPL_CX, TPL_CY, radius);
    }
    var project = projector();
    var points = [];
    var n = sides || 8;
    for (var i = 0; i < n; i++) {
      var angle = (Math.PI * 2 * i) / n;
      points.push(project(global.ArenaGeometry.polar(TPL_CX, TPL_CY, radius, angle)));
    }
    return points.map(pointString).join(' ');
  }

  // The author gallery: a CLOSED RING of cells around the chef octagon.
  //
  // Owner, 2026-08-17, replacing two earlier rules of his own. The 2026-07-24
  // rule made the gallery an OVAL and kept it off the octagon's grid; the
  // 2026-07-29 contract (§2a) put author seats in two banks, top and bottom,
  // and left the flanks empty. His words today: seats go "везде где есть
  // свободное место вокруг октагона", built from "тот же код, что и соты
  // октагона" - mechanics and form.
  //
  // The backend still owns the seat contract, so ring/cell ids continue to
  // match ArenaSeat; only the shape they are drawn in has changed.
  function drawSpectatorOval(svg, geometry, step, defs) {
    var project = projector();
    var layer = el('g', { 'data-arena-layer': 'spectator-oval' });
    var props = g1Radii(geometry);
    var floorR = props.floorOuter;
    var standsOuter = props.standsOuter;
    var oval = geometry.spectator_oval || {};
    // The backend owns the stable seat contract. These defaults only matter if
    // the payload arrives without one, and they mirror it: two rows, 56 inner
    // and 58 outer, 114 author seats all the way round.
    var rowsBySide = oval.rows_by_side || { ring: 2 };
    var countsBySide = oval.counts_by_side || { ring: [56, 58] };
    var beFloor = oval.floor_outer_radius || 220;
    var seats = (Array.isArray(oval.seats) && oval.seats.length)
      ? oval.seats
      : (global.ArenaGeometry.ovalSeats
        ? global.ArenaGeometry.ovalSeats(0, 0, beFloor, rowsBySide, Math.max(8, beFloor * 0.032), countsBySide)
        : []);

    // Remap radial depth so outermost seat CENTRE sits at STANDS_RATIO
    // (G5: ~1.46 so bbox ≈ 1.60). Angle preserved.
    // THE FURTHEST THING IN THE HALL, not the furthest SEAT.
    //
    // This measured seats only, and drawBalconies() then mapped balcony radii
    // through the same scale - but a balcony stands BEHIND the seats, so its
    // plan radius is larger than any seat's and it mapped past standsOuter,
    // off the canvas. It never showed while the stands were crushed into five
    // units and everything landed on top of the floor edge; giving the gallery
    // real depth is what would have thrown the spirits over the rim.
    var maxBe = beFloor;
    function stretchTo(list) {
      (list || []).forEach(function (item) {
        var rb = Math.hypot(item.x || 0, item.y || 0);
        if (rb > maxBe) { maxBe = rb; }
      });
    }
    stretchTo(seats);
    stretchTo((geometry.balconies || {}).stands);
    var depthBe = Math.max(1e-6, maxBe - beFloor);
    var depthSvg = standsOuter - floorR;

    // OWNER, 2026-08-17: THE GALLERY IS BUILT FROM THE OCTAGON'S OWN CELLS.
    // "это тот же код, что и соты октагона" - mechanics AND form. Each seat is
    // a segment of an octagonal ring, drawn by tpl.ringSegmentPath(), the same
    // generator the rank rings use. Circles are gone.
    //
    // The row's band is derived from the backend radii rather than from a
    // second copy of the packing constants: the seats of one row all share a
    // radius, so half the gap to the neighbouring row is this row's half-depth.
    var tpl = global.ArenaOctagon;
    var seatGap = Math.max(1.2, depthSvg * 0.05);

    // Group the backend's seats by ring so each row knows its own radius and
    // cell count without trusting a constant that could drift from the payload.
    var byRing = {};
    seats.forEach(function (seat) {
      var key = String(seat.ring);
      if (!byRing[key]) { byRing[key] = { seats: [], rBe: 0 }; }
      byRing[key].seats.push(seat);
      byRing[key].rBe = Math.hypot(seat.x || 0, seat.y || 0);
    });
    var ringKeys = Object.keys(byRing).sort(function (a, b) {
      return byRing[a].rBe - byRing[b].rBe;
    });

    // Half the distance between adjacent rows, so bands touch without overlap.
    // One row on its own gets the whole remaining depth.
    function bandHalfDepth(i) {
      var here = mapRadius(byRing[ringKeys[i]].rBe);
      if (ringKeys.length < 2) { return Math.max(2, (standsOuter - here)); }
      var other = i === 0
        ? mapRadius(byRing[ringKeys[1]].rBe)
        : mapRadius(byRing[ringKeys[i - 1]].rBe);
      return Math.max(2, Math.abs(other - here) / 2);
    }

    function mapRadius(rBe) {
      if (rBe <= beFloor) { return rBe * (floorR / beFloor); }
      return floorR + ((rBe - beFloor) / depthBe) * depthSvg;
    }

    ringKeys.forEach(function (key, rowIndex) {
      var entry = byRing[key];
      var mid = mapRadius(entry.rBe);
      var half = bandHalfDepth(rowIndex);
      var innerR = mid - half;
      var outerR = mid + half;
      var count = entry.seats.length;
      var sweep = (Math.PI * 2) / count;
      // A gap in ANGLE, so a seam is the same width on a short cell and a long
      // one - the rank rings divide theirs the same way.
      var angGap = seatGap / Math.max(1, outerR);

      entry.seats.forEach(function (seat) {
        var startAngle = seat.cell * sweep + angGap;
        var endAngle = (seat.cell + 1) * sweep - angGap;
        var d = tpl.ringSegmentPath(TPL_CX, TPL_CY, innerR, outerR, startAngle, endAngle);
        var centroid = tpl.segmentCentroid(TPL_CX, TPL_CY, innerR, outerR, startAngle, endAngle);

        // G6-FIX: the seat and anything hosted on it share one transform chain.
        var seatGroup = el('g', { class: 'arena-seat-group', 'data-arena-seat-host': 'true' });
        var cell = el('path', {
          d: d,
          'data-ring': String(seat.ring),
          'data-ring-key': 'gallery_' + rowIndex,
          'data-ring-kind': 'spectator',
          'data-cell': String(seat.cell),
          'data-side': seat.side || 'ring',
          'data-row': String(seat.row != null ? seat.row : rowIndex),
          'data-ring-inner': innerR.toFixed(2),
          'data-ring-outer': outerR.toFixed(2),
          'data-ring-count': String(count),
          'data-centroid-x': centroid.x.toFixed(2),
          'data-centroid-y': centroid.y.toFixed(2),
          'data-occupancy': 'empty',
          'data-state': 'idle',
          'vector-effect': 'non-scaling-stroke',
          class: 'arena-cell arena-cell--oval-seat'
        });
        seatGroup.appendChild(cell);
        layer.appendChild(seatGroup);

        // The seated viewer's portrait is masked with this clip. It was a
        // circle when the seat was one; it is the CELL now, so a face fills
        // its chair the way a chef's fills a rank cell. Losing this clip is
        // how a viewer once became unable to appear in the stands at all.
        var clip = el('clipPath', { id: 'arena-clip-' + seat.ring + '-' + seat.cell });
        clip.appendChild(el('path', { d: d }));
        defs.appendChild(clip);
      });
    });
    svg.appendChild(layer);
    drawBalconies(svg, geometry, layer, {
      floorR: floorR, standsOuter: standsOuter, beFloor: beFloor,
      maxBe: maxBe, project: project
    });
  }

  /**
   * AR5 — the spirit balconies behind the author rows (ARENA_BATTLE_PLAN 2a).
   *
   * A spirit is a COUNT MADE VISIBLE, never a person made up. That is the whole
   * design and every choice below follows from it:
   *
   *   - it has no face, no name, no avatar and no profile link;
   *   - it carries no data-ring, no data-cell and no seat id, so nothing in
   *     bind() can ever seat anybody here — the stands are not in seat_map()
   *     and ArenaSeat has no row for them;
   *   - how many are LIT comes from payload.spirit_count on every poll, which
   *     is why the stands are drawn once here and occupancy is set in bind(),
   *     exactly as the seats work. Drawing the count here instead would freeze
   *     the balconies at whatever the page load happened to see.
   *
   * The nodes below are the empty balcony itself. Nothing is lit until
   * bindSpirits() says so, and a count of zero lights nothing at all.
   */
  function drawBalconies(svg, geometry, seatLayer, props) {
    var balconies = geometry.balconies || {};
    var stands = Array.isArray(balconies.stands) ? balconies.stands : [];
    var layer = el('g', {
      'data-arena-layer': 'balconies',
      'aria-hidden': 'true',
      'pointer-events': 'none'
    });
    svg.insertBefore(layer, seatLayer);
    if (!stands.length) { return; }

    var depthBe = Math.max(1e-6, props.maxBe - props.beFloor);
    var depthSvg = props.standsOuter - props.floorR;
    var pitch = Math.max(8, props.floorR * 0.032);

    // Front row first, so a small crowd gathers at the rail instead of
    // scattering through an empty balcony. bindSpirits() lights them in this
    // order, so the order has to be settled here, once.
    var ordered = stands.slice().sort(function (a, b) {
      return (a.row || 0) - (b.row || 0);
    });

    ordered.forEach(function (stand, i) {
      var rBe = Math.hypot(stand.x || 0, stand.y || 0);
      var ang = Math.atan2(stand.y || 0, stand.x || 0);
      var rSvg = props.floorR + ((rBe - props.beFloor) / depthBe) * depthSvg;
      var pt = props.project({
        x: TPL_CX + Math.cos(ang) * rSvg,
        y: TPL_CY + Math.sin(ang) * rSvg
      });
      var r = Math.max(2.8, pitch * (0.30 - 0.05 * (stand.row || 0)));
      layer.appendChild(el('circle', {
        cx: pt.x.toFixed(2),
        cy: pt.y.toFixed(2),
        r: r.toFixed(2),
        'data-arena-spirit': 'true',
        'data-side': stand.side || '',
        'data-row': String(stand.row != null ? stand.row : ''),
        'data-occupancy': 'empty',
        style: 'animation-delay:' + ((i % 7) * 0.45).toFixed(2) + 's',
        class: 'arena-spirit'
      }));
    });
  }

  /**
   * Light exactly as many balcony stands as there are unauthorised visitors.
   *
   * A count of zero lights nothing, and that is the correct picture today: the
   * lobby heartbeat sits behind the visibility gate, so an anonymous visitor
   * 404s before anything can record them. Inventing a handful of spirits to
   * make the balconies look inhabited would be exactly the fake viewers the
   * plan forbids in production.
   */
  function bindSpirits(svg, payload) {
    var stands = svg.querySelectorAll('.arena-spirit');
    if (!stands.length) { return; }
    var count = parseInt(payload && payload.spirit_count, 10);
    if (!(count > 0)) { count = 0; }
    if (count > stands.length) { count = stands.length; }
    for (var i = 0; i < stands.length; i++) {
      stands[i].setAttribute('data-occupancy', i < count ? 'present' : 'empty');
    }
  }

  // The walkway, and the light along its edges.
  //
  // In the mockup the floor does not run straight into the crowd: a pale grey
  // walkway circles it, and the boundary carries a bronze rim light on both
  // sides — that line is what separates a lit floor from a dark hall instead
  // of letting the parchment fade into the stands.
  //
  // Both are one outline at the floor's outer radius: a wide neutral stroke
  // for the walkway, a thin bronze stroke over it for the rim. Drawn between
  // the cells and the crowd so faces sit in front of it, never behind.

  function drawWalkway(svg, geometry, step) {
    var props = g1Radii(geometry);
    var tpl = global.ArenaOctagon;
    var inner = props.floorOuter;
    // Grey band sits OUTSIDE the last ring (not a clipped stroke on the edge).
    var outer = inner + 18;
    var band = el('g', { 'data-arena-layer': 'walkway', 'pointer-events': 'none' });

    function octPath(R) {
      var pts = [];
      for (var i = 0; i < 8; i++) {
        var angle = i * Math.PI / 4;
        pts.push((TPL_CX + R * Math.cos(angle)).toFixed(2) + ',' + (TPL_CY + R * Math.sin(angle)).toFixed(2));
      }
      return 'M ' + pts.join(' L ') + ' Z';
    }

    band.appendChild(el('path', {
      d: octPath(outer) + ' ' + octPath(inner),
      'fill-rule': 'evenodd',
      fill: '#c4bbb0',
      stroke: 'none',
      class: 'arena-walkway'
    }));
    svg.appendChild(band);
  }

  // Sponsors template cells already carry white strokes — no extra seams.
  // Solid underlay beneath the sponsors-template floor (no SVG Gaussian blur).
  // Ring structure, geometry and the eleven-ring table all live in
  // static/js/arena_octagon.js — the arena's OWN copy of the octagon, with no
  // link back to the Sponsors puzzle (Owner, 2026-07-30). data-ring stays the
  // BACKEND seating key (stage 0, ranks 1..8, oval ring ids) because live
  // ArenaSeat rows store it; the approved 1..11 structure ships alongside as
  // data-ring-visual, which is what stylesheets target.

  /**
   * Draw the chef floor as a 1:1 copy of the Sponsors octagon shell
   * (same CX/CY, radii, counts, gaps, fills, strokes). Sponsors page code
   * shell. Nothing here reads the Sponsors puzzle any more: the arena has its
   * own copy of the octagon in arena_octagon.js.
   */
  function drawGrid(svg, geometry) {
    var props = g1Radii(geometry);
    var step = props.rankStep;
    var tpl = global.ArenaOctagon;
    if (!tpl) {
      throw new Error('ArenaOctagon missing — load arena_octagon.js before arena_render.js');
    }

    svg.setAttribute('viewBox', '0 0 1100 1100');

    var cx = TPL_CX;
    var cy = TPL_CY;
    var gap = tpl.GAP;
        var defs = el('defs', {});
    var cells = el('g', { 'data-arena-layer': 'cells' });
    // The chef spark cannot live in the cells layer: a chef's portrait is
    // clipped to that very cell and painted from the occupants layer above it,
    // so an outline drawn down here is covered by the face standing on it. Its
    // own layer, appended after the occupants, is what makes it visible at all.
    var sparks = el('g', { 'data-arena-layer': 'sparks', 'pointer-events': 'none' });
    var stageRing = geometry.rings[0];

    // No cell-shadow — soft drop-shadows bled past the outer rim as junk.

    // Outer → inner, so an inner ring paints over its neighbour's seam the way
    // the sponsors shell did. The table is the arena's own (ArenaOctagon.ringTable).
    // no fill or stroke is written inline any more — CSS owns every colour, per
    // TECHNICAL_STANDARDS (tokens, never raw hex). SVG presentation attributes
    // lose to any stylesheet rule anyway, so the old inline #fff/hex pairs were
    // dead weight that made the floor look JS-painted.
    var table = tpl.ringTable(geometry.rings);
    for (var t = table.length - 1; t >= 0; t--) {
      var entry = table[t];
      var count = entry.segments;
      if (!count) { continue; }
      var innerR = entry.inner;
      var outerR = entry.outer;
      var sweep = (2 * Math.PI) / count;
      var offset = -Math.PI / 2 - sweep / 2;
      // Ranks keep the backend index in data-ring (the seating key). The moat
      // and the VIP ring hold no seats yet (AR3 / AR5), so they carry no
      // seating index at all rather than a made-up one.
      var ringAttr = entry.ring === null ? '' : String(entry.ring);

      for (var pos = 0; pos < count; pos++) {
        // The moat has no dividers: its eight cells meet at the octagon's
        // vertices, so an angular gap there is not a seam between cells but a
        // white notch cut into the ring at every corner. Ranks and VIP keep it.
        var angGap = entry.kind === 'moat' ? 0 : gap / outerR;
        var startAngle = offset + pos * sweep + angGap;
        var endAngle = offset + (pos + 1) * sweep - angGap;
        var d = tpl.ringSegmentPath(
          cx, cy, innerR + gap, outerR - gap / 2, startAngle, endAngle
        );
        var centroid = tpl.segmentCentroid(
          cx, cy, innerR + gap, outerR - gap / 2, startAngle, endAngle
        );
        var attrs = {
          d: d,
          'data-ring-visual': String(entry.visual),
          'data-ring-key': entry.key,
          'data-ring-kind': entry.kind,
          'data-cell': String(pos),
          'data-centroid-x': centroid.x.toFixed(2),
          'data-centroid-y': centroid.y.toFixed(2),
          // The cell carries its own band and cell count. Anything that needs to
          // re-find this wedge later (the online beacon) reads it from here
          // instead of a table that can drift out from under it.
          'data-ring-inner': innerR.toFixed(2),
          'data-ring-outer': outerR.toFixed(2),
          'data-ring-count': String(count),
          'data-occupancy': 'empty',
          'data-state': 'idle',
          // Only the rank rings still carry arena-cell--sponsors-tpl: 37 fill
          // rules across three stylesheets key on it, so dropping it there
          // would un-paint the floor (AR2 renames it when it rewrites those
          // rules). The moat and VIP ring are NOT sponsors-template rings and
          // must not inherit its paint, so they are left out of it.
          class: entry.kind === 'rank'
            ? 'arena-cell arena-cell--sponsors-tpl arena-cell--rank'
            : 'arena-cell arena-cell--' + entry.kind
        };
        if (ringAttr !== '') { attrs['data-ring'] = ringAttr; }
        cells.appendChild(el('path', attrs));

        // Owner 2026-07-31: the firefly that used to circle a lamp belongs on a
        // chef's own cell instead — the cell's outline traced again with one
        // bright dash running round it. It carries the same ring and cell keys
        // as the seat it belongs to, which is how bind() finds it when a chef
        // arrives or leaves.
        if (entry.kind === 'rank') {
          sparks.appendChild(el('path', {
            d: d, pathLength: '100', fill: 'none',
            'data-ring': ringAttr, 'data-cell': String(pos),
            'pointer-events': 'none', class: 'arena-cell-spark'
          }));
        }

        // AR3 — the moat is lit, not decorated. One lantern at each cell centre;
        // the glow is CSS so the light stays a token and never a literal.
        if (entry.kind === 'moat') {
          // Owner 2026-07-31: these eight stand on the corners and throw no
          // beam, so they are the lamps that get the Enter Arena button's
          // travelling spot. Their place is no longer the cell's centroid — he
          // set it himself on the lamp console — so it is read from the layout,
          // in the same stage-radius multiples every other lamp uses.
          var moatSet = lampLayout().moat;
          var moatAngle = pos * Math.PI / 4 + moatSet.deg * Math.PI / 180;
          var moatR = STAGE_RADIUS * moatSet.r;
          var lampX = cx + moatR * Math.cos(moatAngle);
          var lampY = cy + moatR * Math.sin(moatAngle);

          var lamp = el('circle', {
            cx: lampX.toFixed(2), cy: lampY.toFixed(2), r: '4.2',
            'pointer-events': 'none', class: 'arena-lantern'
          });
          // Each lantern breathes on its own clock so the ring never pulses as
          // one flat band.
          var ph = ((pos * 37) % 100) / 100;
          lamp.appendChild(el('animate', {
            attributeName: 'opacity', values: '0.95;0.55;0.95',
            dur: (2.4 + ph).toFixed(2) + 's', begin: (ph * 2).toFixed(2) + 's',
            repeatCount: 'indefinite'
          }));
          cells.appendChild(lamp);

          // Owner 2026-07-31: a looping strobe on each of these lamps, three
          // rings — small, medium, large — in the tricolour. It follows the same
          // law as the chef-click ripple (fireRipple): a ring that grows from
          // nothing while it fades, on a cubic ease-out. What it does NOT reuse
          // is that function's requestAnimationFrame loop — that is right for
          // one shot and wrong for twenty-four rings running forever, which
          // would never idle and could not be stopped by prefers-reduced-motion.
          // Same visual law, declarative vehicle.
          //
          // "It is light, so it is a ray": the rings are strokes in screen blend
          // with a glow, never ink outlines, so two that cross add up.
          for (var s = 0; s < STROBE_RINGS.length; s++) {
            cells.appendChild(el('circle', {
              cx: lampX.toFixed(2), cy: lampY.toFixed(2),
              r: (STAGE_RADIUS * STROBE_RINGS[s]).toFixed(2),
              fill: 'none', 'vector-effect': 'non-scaling-stroke',
              style: 'transform-origin: ' + lampX.toFixed(2) + 'px ' + lampY.toFixed(2) + 'px',
              'pointer-events': 'none',
              class: 'arena-lamp-strobe arena-lamp-strobe--' + (s + 1)
            }));
          }
        }

        // A VIP box gets a gold liner set inside its own edge. A stroke sits
        // centred on a path, so an inner rim cannot be done with one shape —
        // this is a second, inset wedge that carries the gold and takes no
        // pointer events, so hover and clicks still belong to the box itself.
        if (entry.kind === 'vip') {
          cells.appendChild(el('path', {
            d: tpl.ringSegmentPath(
              cx, cy, innerR + gap + 5, outerR - gap / 2 - 5,
              startAngle + 0.008, endAngle - 0.008
            ),
            class: 'arena-cell--vip-liner',
            'pointer-events': 'none'
          }));

          // Every fourth box is centred exactly on an octagon vertex (32 boxes at
          // 11.25 degrees, a face is 45), so that box is folded by the corner and
          // carries the whole word, bent around it. The three boxes between
          // corners are flat and carry V, I and P, one letter each.
          var addLabel = function (text, a0, a1, cls) {
            var c = tpl.segmentCentroid(cx, cy, innerR + gap, outerR - gap / 2, a0, a1);
            var deg = ((a0 + a1) / 2) * 180 / Math.PI + 90;
            var node = el('text', {
              x: c.x.toFixed(2), y: c.y.toFixed(2),
              'text-anchor': 'middle', 'dominant-baseline': 'central',
              'pointer-events': 'none',
              transform: 'rotate(' + deg.toFixed(2) + ' ' + c.x.toFixed(2) + ' ' + c.y.toFixed(2) + ')',
              'data-vip-label': String(pos),
              class: cls
            });
            node.textContent = text;
            cells.appendChild(node);
          };
          if ((pos % 4) === 0) {
            // SPONSORS had been set as two halves, SPON and SORS, each in its own
            // <text> rotated about its own half-centroid. Two rotations about two
            // different centres cannot meet: the word read as cut in half at the
            // corner, which is what the Owner has been looking at since 2026-07-30.
            //
            // One word, one guide. The guide is the middle of the box's band,
            // sampled along the octagon — so it TURNS at the vertex by itself,
            // because octRadius already knows where the corner is — and the word
            // is laid on it. It bends with the corner instead of being broken by it.
            var guideR = ((innerR + gap) + (outerR - gap / 2)) / 2;
            var guideId = 'arena-vip-word-' + pos;
            var steps = 16;
            var guide = [];
            for (var gi = 0; gi <= steps; gi++) {
              var ga = startAngle + (endAngle - startAngle) * (gi / steps);
              var gp = tpl.octPoint(cx, cy, ga, guideR);
              guide.push(gp[0].toFixed(2) + ',' + gp[1].toFixed(2));
            }
            defs.appendChild(el('path', {
              id: guideId, fill: 'none', d: 'M ' + guide.join(' L ')
            }));

            var word = el('text', {
              'dominant-baseline': 'central',
              'pointer-events': 'none',
              'data-vip-label': String(pos),
              class: 'arena-vip-label arena-vip-label--word'
            });
            var wordPath = el('textPath', {
              href: '#' + guideId,
              startOffset: '50%',
              'text-anchor': 'middle'
            });
            wordPath.textContent = 'SPONSORS';
            word.appendChild(wordPath);
            cells.appendChild(word);
          } else {
            addLabel(['', 'V', 'I', 'P'][pos % 4], startAngle, endAngle, 'arena-vip-label');
          }
        }

        // A VIP box needs its own clip so a sponsor's logo can be dropped into
        // it without spilling over the brass edge. Keyed by kind, not by the
        // seating index, because the ring deliberately carries none.
        if (entry.kind === 'vip') {
          var vipClip = el('clipPath', { id: 'arena-clip-vip-' + pos });
          vipClip.appendChild(el('path', { d: d }));
          defs.appendChild(vipClip);

          // Owner 2026-08-03: a gold firefly runs around an ACTIVE box. Same
          // outline, same running dash as a chef's — gold, because the ring is
          // sold rather than earned. It goes in the sparks layer, above both the
          // sponsors and the chefs, so a logo cannot bury the light that says
          // the box is taken.
          sparks.appendChild(el('path', {
            d: d, pathLength: '100', fill: 'none',
            'data-vip-spark': String(pos),
            'pointer-events': 'none', class: 'arena-vip-spark'
          }));
        }

        // Portrait clips are keyed by the seating index, so only real seat
        // rings build them — and the ids stay byte-identical to before.
        if (ringAttr !== '') {
          var clip = el('clipPath', { id: 'arena-clip-' + ringAttr + '-' + pos });
          clip.appendChild(el('path', { d: d }));
          defs.appendChild(clip);
        }
      }
    }

    // The moat keeps NO dividers between its eight cells, but the ring itself is
    // still outlined in white, inner edge and outer edge. Cells are strokeless
    // and the outline is drawn once, as a ring, so nothing cuts across it.
    (function () {
      var moat = null;
      for (var mi = 0; mi < table.length; mi++) {
        if (table[mi].kind === 'moat') { moat = table[mi]; break; }
      }
      if (!moat) { return; }
      [moat.inner + gap, moat.outer - gap / 2].forEach(function (r) {
        cells.appendChild(el('polygon', {
          points: tpl.octagonPoints(cx, cy, r),
          'pointer-events': 'none', class: 'arena-moat-edge'
        }));
      });
    })();

    var faceClip = el('clipPath', { id: 'arena-face-clip', clipPathUnits: 'objectBoundingBox' });
    faceClip.appendChild(el('circle', { cx: '0.5', cy: '0.5', r: '0.5' }));
    defs.appendChild(faceClip);

    var centreR = tpl.CROWN_OUTER - gap;
    var centrePts = tpl.octagonPoints(cx, cy, centreR);
    var centreClip = el('clipPath', { id: 'arena-clip-0-0' });
    centreClip.appendChild(el('polygon', { points: centrePts }));
    defs.appendChild(centreClip);

    // Hard clip: avatars / cell strokes / any filter bleed cannot paint past
    // the outer octagon. Grey walkway is drawn OUTSIDE this group.
    var floorClip = el('clipPath', { id: 'arena-shell-clip' });
    floorClip.appendChild(el('polygon', {
      points: tpl.octagonPoints(cx, cy, tpl.OUTER)
    }));
    defs.appendChild(floorClip);

    var shell = el('g', {
      'data-arena-layer': 'shell',
      'clip-path': 'url(#arena-shell-clip)'
    });

    svg.appendChild(defs);
    shell.appendChild(cells);
    shell.appendChild(el('polygon', {
      points: centrePts,
      stroke: '#fff',
      'stroke-width': '2',
      'data-ring': String(stageRing.index),
      'data-ring-visual': String(tpl.VISUAL_CROWN),
      'data-ring-key': stageRing.key,
      'data-ring-kind': stageRing.kind,
      'data-occupancy': 'stage',
      'data-state': 'open',
      'data-arena-stage': 'true',
      class: 'arena-stage'
    }));
    shell.appendChild(el('g', { 'data-arena-layer': 'sponsors' }));
    shell.appendChild(el('g', { 'data-arena-layer': 'occupants' }));
    shell.appendChild(sparks);
    shell.appendChild(el('g', { 'data-arena-layer': 'centre' }));
    svg.appendChild(shell);

    // Grey outer band outside the clip — visible frame, no avatar bleed over it.
    drawWalkway(svg, geometry, step);

    // The spectator oval. drawSpectatorOval existed, was complete, and was
    // called from nowhere: production rendered 210 rank cells, one stage and
    // ZERO spectator seats, while the payload carried all 290 of them. Nothing
    // reported it, because an unseated arena looks the same as an arena with no
    // seats. It also builds the arena-clip-<ring>-<cell> clip paths that a
    // seated viewer's portrait is masked with, so without this call a viewer
    // could never appear in the stands at all.
    //
    // Drawn after the walkway so seats sit in front of it, and inside drawGrid
    // so the nodes exist before bind() seats anyone.
    drawSpectatorOval(svg, geometry, step, defs);

    var label = el('text', {
      'text-anchor': 'middle', 'dominant-baseline': 'central',
      'pointer-events': 'none', hidden: 'hidden',
      class: 'arena-seat-label'
    });
    label.textContent = 'Sit here';
    svg.appendChild(label);

    // "You are here" - Owner, 2026-08-17.
    //
    // A SECOND element rather than a second mode on the one above, because the
    // two are opposites in every way that matters: "Sit here" follows the
    // pointer and vanishes when it leaves, "You are here" is anchored to one
    // seat and stays. Sharing a node would mean a hover over a free chair
    // erasing the marker telling you where you sit, and restoring it on
    // mouseleave - state to get wrong for no gain.
    var mine = el('text', {
      'text-anchor': 'middle', 'dominant-baseline': 'central',
      'pointer-events': 'none', hidden: 'hidden',
      class: 'arena-seat-label arena-seat-label--mine'
    });
    mine.textContent = 'You are here';
    svg.appendChild(mine);
  }

  /* ---------------------------------------------------------------- */
  /* Data binding                                                      */
  /* ---------------------------------------------------------------- */

  /**
   * A chef fighting the battle currently shown in the centre vacates their ring
   * cell — they move, they are never drawn twice. Derived from the payload
   * itself (chef.battle_id vs center.battle_id) rather than from a hardcoded
   * list of battle statuses, which is what the legacy renderer did.
   */
  function isDisplaced(chef, center) {
    if (!chef || !center) { return false; }
    if (center.battle_id && chef.battle_id && chef.battle_id === center.battle_id) { return true; }
    var slugs = [center.challenger, center.opponent].map(function (side) {
      return side && side.slug;
    });
    return !!chef.slug && slugs.indexOf(chef.slug) !== -1;
  }

  // Stable per-chef hash — seats stay put across 20s polls (no Math.random flicker).
  function chefSeatHash(slug, ring) {
    var source = String(slug || '') + '#' + String(ring || 0);
    var h = 2166136261;
    for (var i = 0; i < source.length; i++) {
      h ^= source.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return h >>> 0;
  }

  function cellsAdjacent(a, b, capacity) {
    if (capacity <= 0) { return false; }
    var d = Math.abs(a - b) % capacity;
    return d === 1 || d === capacity - 1;
  }

  /**
   * Pick a free cell in the ring. Idle chefs scatter by slug hash (ТЗ: random
   * places). Neighbours are avoided when possible — they only stand side by
   * side after an accepted challenge (facing teleport), not on ordinary online.
   */
  function pickScatteredCell(ring, slug, capacity, occupied) {
    if (capacity <= 0) { return -1; }
    var start = chefSeatHash(slug, ring) % capacity;
    var i;
    var cell;
    // Pass 1: preferred hash seat, then walk — skip seats beside anyone already placed.
    for (i = 0; i < capacity; i++) {
      cell = (start + i) % capacity;
      if (occupied[cell]) { continue; }
      var blocked = false;
      for (var other in occupied) {
        if (!occupied.hasOwnProperty(other)) { continue; }
        if (cellsAdjacent(cell, Number(other), capacity)) { blocked = true; break; }
      }
      if (!blocked) { return cell; }
    }
    // Pass 2: ring nearly full — take any free seat.
    for (i = 0; i < capacity; i++) {
      cell = (start + i) % capacity;
      if (!occupied[cell]) { return cell; }
    }
    return -1;
  }

  function buildAssignments(payload, geometry) {
    var assignments = [];
    var center = payload.center || {};
    // Ring identity and capacity come from payload.geometry — the same authority
    // the floor is now drawn from (ArenaOctagon.ringTable). Until this fix they came from
    // the Sponsors template instead, and both halves were wrong once AR1 gave the
    // arena its own rings:
    //   * capacity was 10..60 while the floor draws 9..40, so a chef whose
    //     scattered cell landed past the drawn count matched no cell, hit the
    //     `if (!seat) { return; }` in bind() and vanished from the arena without a
    //     word — taking its green online light with it (Owner, 2026-07-30);
    //   * ranks 6-8 were collapsed onto one template ring with Math.min(6, index),
    //     so commis/prep/porter fought for the same seats and prep_cook and
    //     kitchen_porter never stood on a ring of their own.
    var occupiedByRing = {};
    var capacity = {};
    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'rank') { return; }
      occupiedByRing[ring.index] = {};
      capacity[ring.index] = ring.segments;
    });

    /* OWNER, scenario A2 and A4, 2026-08-06.
     *
     * "шефы сближаются внутри своего кольца, либо шеф который на 1 ранг выше
     *  занимает позицию рядом со вторым шефом но всё ещё в своём кольце -
     *  получается что всё равно две соты стоят рядом друг с другом", and once
     * the challenge is accepted "они всегда стоят друг с другом - пока идет
     * подготовка к баттлу".
     *
     * So a pair bound by an accepted challenge is seated FIRST, together, and
     * the scatter below then works around them. Three properties matter:
     *
     *   - NOBODY LEAVES HIS OWN RING. Ranks may differ by one (the ±1 challenge
     *     rule), and a ring is a rank. The pair is aligned across the boundary
     *     instead: the same angular position, which on an octagon is the same
     *     fraction of the way round, so the two cells face each other.
     *   - IT IS STABLE. The seat comes from the battle id, not from the poll,
     *     the slug order or the time. Either chef can leave the site and come
     *     back and the pair is in the same two cells - which is exactly what
     *     "не появляются в рандомных сотах" asks for.
     *   - IT IS THE BATTLE THAT PAIRS THEM, not the challenge. While a
     *     challenge is only pending (A3) neither chef carries a battle_id, so
     *     they scatter like anyone else and may come and go.
     */
    var pairedSlugs = {};
    (function seatBattlePairs() {
      var byBattle = {};
      var ringByKey = {};
      geometry.rings.forEach(function (r) {
        if (r.kind === 'rank') { ringByKey[r.key] = r; }
      });
      Object.keys(ringByKey).forEach(function (key) {
        ((payload.rings && payload.rings[key]) || []).forEach(function (chef) {
          if (!chef || isDisplaced(chef, center) || !chef.battle_id) { return; }
          var id = String(chef.battle_id);
          (byBattle[id] = byBattle[id] || []).push({ chef: chef, ring: ringByKey[key] });
        });
      });

      Object.keys(byBattle).sort().forEach(function (id) {
        var pair = byBattle[id];
        if (pair.length !== 2) { return; }
        // Fix WHICH of the two takes the first cell, by slug. Without this the
        // pair still lands on the same two cells but the chefs swap between
        // them whenever the payload happens to list them in the other order -
        // the seat would be stable and the chef would not, which is the jitter
        // A4 exists to forbid.
        pair.sort(function (x, y) {
          return String(x.chef.slug || '').localeCompare(String(y.chef.slug || ''));
        });
        var a = pair[0], b = pair[1];
        var capA = capacity[a.ring.index], capB = capacity[b.ring.index];
        if (!capA || !capB) { return; }

        var seed = chefSeatHash('battle-' + id, a.ring.index);
        var cellA = seed % capA;
        var cellB;

        function free(ringIndex, cell) {
          return !occupiedByRing[ringIndex][cell];
        }

        var step;
        if (a.ring.index === b.ring.index) {
          // Same rank, same ring: neighbouring cells. Walk together until a
          // pair of free neighbours exists, so a busy ring cannot split them.
          for (step = 0; step < capA; step++) {
            var c = (cellA + step) % capA;
            var n = (c + 1) % capA;
            if (free(a.ring.index, c) && free(a.ring.index, n)) {
              cellA = c; cellB = n; break;
            }
          }
        } else {
          // One rank apart: each keeps his own ring, aligned by angle. Rings
          // hold different numbers of cells, so the position is carried as a
          // fraction of the way round rather than as an index.
          for (step = 0; step < capA; step++) {
            var ca = (cellA + step) % capA;
            var cb = Math.round(ca / capA * capB) % capB;
            if (free(a.ring.index, ca) && free(b.ring.index, cb)) {
              cellA = ca; cellB = cb; break;
            }
          }
        }
        if (cellB === undefined) { return; }

        occupiedByRing[a.ring.index][cellA] = true;
        occupiedByRing[b.ring.index][cellB] = true;
        pairedSlugs[a.chef.slug] = true;
        pairedSlugs[b.chef.slug] = true;
        [[a, cellA], [b, cellB]].forEach(function (seat) {
          assignments.push({
            ring: seat[0].ring.index, cell: seat[1], entity: seat[0].chef,
            occupancy: 'chef',
            state: seat[0].chef.in_battle
              ? 'in-battle'
              : (seat[0].chef.is_online ? 'online' : 'idle')
          });
        });
      });
    })();

    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'rank') { return; }
      var chefs = ((payload.rings && payload.rings[ring.key]) || []).filter(function (chef) {
        return chef && !isDisplaced(chef, center) && !pairedSlugs[chef.slug];
      });
      // Stable order so hash collisions resolve the same way every poll.
      chefs.sort(function (a, b) {
        return String(a.slug || '').localeCompare(String(b.slug || ''));
      });
      chefs.forEach(function (chef) {
        var occupied = occupiedByRing[ring.index];
        var cell = pickScatteredCell(
          ring.index, chef.slug, capacity[ring.index], occupied
        );
        if (cell < 0) { return; }
        occupied[cell] = true;
        assignments.push({
          ring: ring.index, cell: cell, entity: chef,
          occupancy: 'chef',
          state: chef.in_battle ? 'in-battle' : (chef.is_online ? 'online' : 'idle')
        });
      });
    });

    var spectators = payload.spectators || [];
    var placed = {};
    var queue = [];

    // Prefer explicit seat coordinates when BE provides them (ArenaSeat /
    // public_seat). Fall back to front-row list order for payloads that still
    // ship a plain spectator list without ring/cell.
    spectators.forEach(function (spectator) {
      if (!spectator) { return; }
      var hasSeat = spectator.ring !== undefined && spectator.ring !== null
        && spectator.cell !== undefined && spectator.cell !== null
        && spectator.ring !== '' && spectator.cell !== '';
      if (hasSeat) {
        var ringNo = Number(spectator.ring);
        var cellNo = Number(spectator.cell);
        var key = ringNo + ':' + cellNo;
        if (!isFinite(ringNo) || !isFinite(cellNo) || placed[key]) { return; }
        placed[key] = true;
        assignments.push({
          ring: ringNo, cell: cellNo, entity: spectator,
          occupancy: 'spectator', state: 'watching'
        });
        return;
      }
      queue.push(spectator);
    });

    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'spectator') { return; }
      for (var cell = 0; cell < ring.segments && queue.length; cell++) {
        var key = ring.index + ':' + cell;
        if (placed[key]) { continue; }
        var spectator = queue.shift();
        placed[key] = true;
        assignments.push({
          ring: ring.index, cell: cell, entity: spectator,
          occupancy: 'spectator', state: 'watching'
        });
      }
    });

    return assignments;
  }

  // A hall is people. Real spectators sit as their own avatars, but there are
  // never 208 of them online at once, and stands of empty stone read as an
  // abandoned building rather than the packed house the arena is meant to be.
  //
  // The stand-ins are the site's own three default avatars — the same faces a
  // member has before uploading a photo — so the preview crowd is made of the
  // people this hall will actually hold. They are served as 96px webp copies
  // (under a kilobyte each) rather than the 2.3MB originals: three shared
  // sources across 200-odd seats is three requests either way, but at full
  // size that is seven megabytes on a phone.
  // Seat the crowd. The face has to be decided by the seat, not by chance:
  // Math.random() would deal a new hall on every 10s poll and the stands would
  // shimmer. But arithmetic on the seat number is not enough either — the old
  // (ring * 7 + cell * 3) walked the list in a fixed stride, so the same face
  // landed every third seat and the rows read as a repeating pattern rather
  // than a crowd. The owner's word for it was eggs in a carton.
  //
  // A hash scatters the same three or twelve faces without any visible
  // period, and stays put across polls because it is still a pure function of
  // the seat.
  function seatHash(ring, cell) {
    var h = (ring + 1) * 0x9e3779b1 ^ (cell + 1) * 0x85ebca6b;
    h ^= h >>> 15;
    h = Math.imul(h, 0x2545f491);
    h ^= h >>> 13;
    return (h >>> 0);
  }



  // Face size, from the measured mockup (docs/chef_battle/arena_mockup_spec.md
  // §4): a portrait is 0.06 of the floor's own radius, 0.07 in the front row
  // and 0.05 in the back. We were drawing them at 0.14-0.20 R_floor — the
  // avatar was scaled to the seat's larger side and sliced by the seat, so the
  // stands read as a mosaic of cropped heads instead of a crowd of people.
  var FACE_NEAR = 0.07;
  var FACE_FAR = 0.05;

  // How far back a seat sits, 0 at the front row and 1 at the back. The server
  // puts row / rows_total in the geometry contract for exactly this, so depth
  // never has to be inferred from an absolute ring index that shifts whenever
  // the stands get deeper.
  function rowDepth(geometry, ring) {
    var record = null;
    (geometry.rings || []).forEach(function (r) { if (r.index === ring) { record = r; } });
    if (record && record.row && record.rows_total && record.rows_total >= 2) {
      return Math.min(1, Math.max(0, (record.row - 1) / (record.rows_total - 1)));
    }
    // Oval ring ids: 100 + sideIndex*10 + row. Keep depth valid for fallback
    // payloads that omit compact oval ring descriptors.
    if (ring >= 100) {
      var ovalRow = ring % 10;
      var side = ['top', 'right', 'bottom', 'left'][Math.floor((ring - 100) / 10)];
      var rows = geometry.spectator_oval && geometry.spectator_oval.rows_by_side;
      var ovalRows = (rows && rows[side]) || 1;
      return Math.min(1, Math.max(0, ovalRow / Math.max(1, ovalRows - 1)));
    }
    return 0;
  }


  // Depth of light. Size alone does not read as distance: with every face at
  // full brightness the back row shines as hard as the front and the
  // perspective flattens out. The mockup (§4) drops roughly 35% of brightness
  // from the near row to the far one; G8 pushes that to ~45% so four oval rows
  // actually read as a mass receding into the bowl (tokens via filter only).
  var FACE_DIM = 0.45;
  var FACE_DESATURATE = 0.38;

  // The seats fall into the dark on the same curve as the faces sitting in
  // them. arena.css reads --row-light (the renderer's own section, merged in
  // AN12); it used to hold a hand-written
  // ladder of ring numbers, which stopped covering the stands the moment they
  // grew from four rows to eight. One source of depth, written from here.
  function lightRows(svg, geometry) {
    // G8: light every drawn spectator seat from its own ring id (oval row =
    // ring % 10). Do not depend on geometry.rings listing every oval row.
    var seats = svg.querySelectorAll('.arena-cell[data-ring-kind="spectator"]');
    Array.prototype.forEach.call(seats, function (seat) {
      var ring = Number(seat.getAttribute('data-ring'));
      var light = (1 - FACE_DIM * rowDepth(geometry, ring)).toFixed(3);
      seat.style.setProperty('--row-light', light);
    });
  }


  // THE ATMOSPHERIC CROWD IS GONE. Owner, 2026-08-17.
  //
  // Three rows of real face photographs stood behind the seats as scenery. On
  // screen each was 3-4 PIXELS across at 30-62% opacity - measured, not
  // guessed - so a photograph of a person read as a black dot, and a ring of
  // black dots around the octagon is what he reported. The assets were fine:
  // 96 files in git, 192 on production, nothing broken. The size was the bug.
  //
  // Removed rather than enlarged: with the author gallery now visible and the
  // spirits lighting the balconies by real count, the hall is described by two
  // honest things. Ninety-six drawn spectators around an empty arena would be
  // the invented viewers the plan forbids in production.
  //
  // The face assets under static/images/crowd/ stay on disk. They are paid
  // work and not litter; they are simply not drawn.
  //
  // Deleted with it, because it existed only to serve it: fillCrowd,
  // crowdFaceFor, seatJitter, faceDiameter, faceLighting, billboardFaces, the
  // crowd layer, and appendCrowdFigure - which had already been unreachable,
  // defined and called from nowhere.


  function initialOf(entity) {
    var source = (entity.name || entity.slug || '').trim();
    return source ? source.charAt(0).toUpperCase() : '?';
  }

  function appendOnlineDot(group, assignment, seat) {
    // Top-left of the wedge itself (not the bbox) — bbox min sits outside
    // slanted cells and spilled the pulse into the neighbour.
    var entity = assignment.entity || {};
    var tpl = global.ArenaOctagon;
    if (assignment.occupancy !== 'chef') { return; }
    if (entity.is_online === false) { return; }
    if (!seat || !tpl) { return; }

    var ring = assignment.ring;
    var cell = assignment.cell;
    // Read the wedge off the cell the floor actually drew. This used to read the
    // Sponsors template's ring table, which had no entry at all for
    // the arena's outer rank rings — so a Kitchen Porter simply got no beacon —
    // and stale radii for the inner ones, which put the beacon off the avatar.
    var count = parseFloat(seat.getAttribute('data-ring-count'));
    var bandInner = parseFloat(seat.getAttribute('data-ring-inner'));
    var bandOuter = parseFloat(seat.getAttribute('data-ring-outer'));
    if (!isFinite(count) || !count || !isFinite(bandInner) || !isFinite(bandOuter)) { return; }

    var outerR = bandOuter - tpl.GAP / 2;
    var innerR = bandInner + tpl.GAP;
    var angles = tpl.cellAngles(count, cell, outerR);
    var pts = tpl.ringSegmentPoints(tpl.CX, tpl.CY, innerR, outerR, angles.start, angles.end);

    var best = pts[0];
    var bestScore = pts[0][0] + pts[0][1];
    for (var i = 1; i < pts.length; i++) {
      var score = pts[i][0] + pts[i][1];
      if (score < bestScore) {
        bestScore = score;
        best = pts[i];
      }
    }

    var cx = parseFloat(seat.getAttribute('data-centroid-x'));
    var cy = parseFloat(seat.getAttribute('data-centroid-y'));
    if (!isFinite(cx) || !isFinite(cy)) {
      var box = seat.getBBox();
      cx = box.x + box.width / 2;
      cy = box.y + box.height / 2;
    }

    // Pull inward from the NW corner so the white halo stays on the avatar.
    var dx = cx - best[0];
    var dy = cy - best[1];
    var len = Math.sqrt(dx * dx + dy * dy) || 1;
    var pull = 12;
    var dotX = best[0] + (dx / len) * pull;
    var dotY = best[1] + (dy / len) * pull;
    var cxAttr = dotX.toFixed(1);
    var cyAttr = dotY.toFixed(1);

    // Each chef blinks on their own clock — stable hash so polls don't resync.
    var h = chefSeatHash(entity.slug || ('r' + ring + 'c' + cell), ring);
    var durSec = 1.05 + ((h % 1100) / 1000);           // ~1.05s … 2.15s
    var beginSec = (((h >>> 9) % 1000) / 1000) * durSec; // phase 0 … dur
    var dur = durSec.toFixed(2) + 's';
    var begin = beginSec.toFixed(2) + 's';

    group.appendChild(el('circle', {
      cx: cxAttr, cy: cyAttr, r: '5.5',
      fill: '#fff', 'pointer-events': 'none'
    }));

    // Expanding ping — reads as “live” even when opacity alone is subtle.
    var ping = el('circle', {
      cx: cxAttr, cy: cyAttr, r: '4',
      fill: 'none', stroke: '#22c55e', 'stroke-width': '2',
      'pointer-events': 'none',
      class: 'arena-online-ping'
    });
    ping.appendChild(el('animate', {
      attributeName: 'r', values: '4;11', dur: dur, begin: begin,
      repeatCount: 'indefinite'
    }));
    ping.appendChild(el('animate', {
      attributeName: 'opacity', values: '0.85;0', dur: dur, begin: begin,
      repeatCount: 'indefinite'
    }));
    group.appendChild(ping);

    var dot = el('circle', {
      cx: cxAttr, cy: cyAttr, r: '4',
      fill: '#22c55e', 'pointer-events': 'none',
      class: 'arena-online-dot',
      style: 'animation-duration:' + dur + ';animation-delay:-' + begin
    });
    // SMIL radius pulse — reliable on SVG circles (CSS `r` keyframes are flaky).
    dot.appendChild(el('animate', {
      attributeName: 'r', values: '4;2.6;4', dur: dur, begin: begin,
      repeatCount: 'indefinite'
    }));
    dot.appendChild(el('animate', {
      attributeName: 'opacity', values: '1;0.35;1', dur: dur, begin: begin,
      repeatCount: 'indefinite'
    }));
    group.appendChild(dot);
  }

  /**
   * B5 (T25) — where each chef stood on the LAST paint, by slug.
   *
   * The occupants layer is wiped and rebuilt from scratch on every poll, so a
   * chef who changes cell simply vanishes from one and appears in another.
   * That is the "static relocation" B2/B3/F2 shipped; B5 is the second half
   * the board always said would come after it, and to animate a move you have
   * to know where the chef was, which nothing recorded.
   *
   * Two maps, not one. `previousCellCentres` is last paint's, read while this
   * paint is being drawn; `lastCellCentres` is this paint's, written as each
   * occupant lands. bind() swaps them before rebuilding, so a chef who leaves
   * the floor drops out instead of accumulating - the map is never larger
   * than the number of chefs currently on it. One map would be overwritten
   * mid-loop and every chef would compare against himself.
   */
  var lastCellCentres = {};
  var previousCellCentres = {};

  function cellCentre(seat) {
    var box = seat.getBBox();
    return { x: box.x + box.width / 2, y: box.y + box.height / 2 };
  }

  function appendOccupant(svg, layer, assignment) {
    var entity = assignment.entity || {};
    var selector = '.arena-cell[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]';
    var seat = svg.querySelector(selector);
    if (!seat) { return; }

    var box = seat.getBBox();
    // Cover the wedge bbox so the face fills the cell (sponsors-style clip).
    var size = Math.max(box.width, box.height) * 1.08;
    var group = el('g', {
      'clip-path': 'url(#arena-clip-' + assignment.ring + '-' + assignment.cell + ')',
      'data-entity-slug': entity.slug || '',
      class: 'arena-occupant'
    });

    if (entity.avatar_url) {
      group.appendChild(el('image', {
        href: entity.avatar_url,
        x: (box.x + box.width / 2 - size / 2).toFixed(2),
        y: (box.y + box.height / 2 - size / 2).toFixed(2),
        width: size.toFixed(2), height: size.toFixed(2),
        preserveAspectRatio: 'xMidYMid slice',
        'pointer-events': 'none'
      }));
    } else {
      // display_avatar_url always resolves to a photo or a default, so this is
      // a guard rather than an expected path: a seat that is taken must never
      // read as free, whatever the payload carries.
      var initial = el('text', {
        x: (box.x + box.width / 2).toFixed(2),
        y: (box.y + box.height / 2).toFixed(2),
        'text-anchor': 'middle', 'dominant-baseline': 'central',
        'font-size': Math.max(6, size * 0.42).toFixed(1),
        'pointer-events': 'none',
        class: 'arena-occupant__initial'
      });
      initial.textContent = initialOf(entity);
      group.appendChild(initial);
    }

    appendOnlineDot(group, assignment, seat);
    layer.appendChild(group);

    // B5 (T25) — animate the relocation instead of jumping it.
    //
    // The chef is already drawn in his NEW cell. If he was somewhere else on
    // the last paint, we offset him back to where he was, force the browser
    // to accept that as the starting state, then release the offset - CSS
    // carries him across. Going this way round rather than animating towards
    // the new cell means the clip-path, the avatar and the online dot are all
    // already correct for the destination; only the whole group slides.
    //
    // No per-frame JavaScript and no timers: the transition lives in
    // arena.css, so `prefers-reduced-motion` can switch it off there with
    // everything else, and a backgrounded tab costs nothing.
    var slug = entity.slug || '';
    var here = cellCentre(seat);
    if (slug) {
      var was = previousCellCentres[slug];
      // A chef appearing for the first time has no previous position and must
      // NOT slide in from the origin - only a real move animates.
      if (was && (Math.abs(was.x - here.x) > 0.5 || Math.abs(was.y - here.y) > 0.5)) {
        group.setAttribute('class', 'arena-occupant arena-occupant--moving');
        group.style.transform =
          'translate(' + (was.x - here.x).toFixed(2) + 'px, ' +
          (was.y - here.y).toFixed(2) + 'px)';
        // A deliberate synchronous reflow, of the kind AN20's guard test
        // explicitly allows: "each read depends on the write above it". The
        // browser would otherwise coalesce setting the offset and clearing it
        // into one style recalculation, leaving nothing to transition FROM.
        // Cost is bounded by chefs who ACTUALLY MOVED - normally none, and a
        // rank change or a fighter taking the centre moves one or two. This
        // is not a per-occupant read; it is inside the branch that already
        // proved the cell changed.
        void group.getBoundingClientRect();
        group.style.transform = '';
      }
      lastCellCentres[slug] = here;
    }
  }

  function bind(svg, payload, geometry) {
    var occupants = svg.querySelector('[data-arena-layer="occupants"]');
    while (occupants.firstChild) { occupants.removeChild(occupants.firstChild); }

    // B5 (T25): this paint's positions become the ones the next paint animates
    // from. Swapped here, before a single occupant is drawn, so appendOccupant
    // reads a map that is complete and finished with.
    previousCellCentres = lastCellCentres;
    lastCellCentres = {};

    // The balconies are not seats and hold no occupant records, so they are
    // settled here, before the seat machinery runs, and never touched by it.
    bindSpirits(svg, payload);

    // Clear every transient attribute first: a poll may free a cell, and a
    // stale occupancy left on it would outlive its occupant.
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell[data-ring]'), function (seat) {
      seat.setAttribute('data-occupancy', 'empty');
      seat.setAttribute('data-state', 'idle');
      seat.removeAttribute('data-entity-slug');
      seat.removeAttribute('data-avatar-default');
      seat.chefRecord = null;
    });
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell-spark'), function (spark) {
      spark.removeAttribute('data-lit');
      // Cleared with data-lit, not separately: a crown left behind on a cell
      // the Owner has moved off would hand his aura to whoever sits there next.
      spark.removeAttribute('data-owner');
    });

    lightRows(svg, geometry);

    var assignments = buildAssignments(payload, geometry);

    assignments.forEach(function (assignment) {
      var seat = svg.querySelector(
        '.arena-cell[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]'
      );
      if (!seat) {
        // A dropped occupant used to be invisible in every sense: no cell, no
        // message, just a chef missing from the arena — which is exactly how the
        // AR1 capacity mismatch survived a deploy and had to be reported by the
        // Owner instead of by the code. Say it out loud.
        if (global.console && global.console.warn) {
          global.console.warn(
            'arena_render: no cell at ring ' + assignment.ring + ' cell ' +
            assignment.cell + ' — occupant dropped',
            (assignment.entity && assignment.entity.slug) || ''
          );
        }
        return;
      }
      var entity = assignment.entity;
      seat.setAttribute('data-occupancy', assignment.occupancy);
      seat.setAttribute('data-state', assignment.state);
      seat.setAttribute('data-entity-slug', entity.slug || '');
      seat.setAttribute('data-avatar-default', entity.avatar_is_default ? '1' : '0');
      seat.chefRecord = assignment.occupancy === 'spectator' ? asSpectator(entity) : entity;

      // The spark belongs to chefs, not to every occupant: a gallery spectator
      // is atmosphere and does not get a ring of light on the floor.
      if (assignment.occupancy === 'chef') {
        var spark = svg.querySelector(
          '.arena-cell-spark[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]'
        );
        if (spark) {
          spark.setAttribute('data-lit', 'true');
          // 2026-08-16: the Owner wears a gold crown, not a rank aura. His
          // rank is hand-set, so without this he lights up as an ordinary
          // ring-2 Executive Chef like anybody who earns that rank.
          if (entity.is_owner) { spark.setAttribute('data-owner', 'true'); }
        }
      }

      appendOccupant(svg, occupants, assignment);
    });

    seatSponsors(svg, payload.vip_sponsors);

    markSeatable(svg, geometry);
    markMySeat(svg);
    stampStage(svg, payload.center || { type: 'empty' });
  }

  /**
   * "You are here" over the viewer's own seat - Owner, 2026-08-17.
   *
   * Placed at the END of bind(), after every occupant has landed, because the
   * seat it marks is found by the slug that bind() has just stamped on the
   * cells. Running it earlier would read a floor that is still half the
   * previous poll's.
   *
   * Anchored on the cell's own centroid rather than a measured box: every cell
   * already carries data-centroid-x/y from the generator that drew it, and a
   * getBBox() here would be a synchronous layout read on every poll to
   * recover a number the element is holding out for us.
   *
   * ONLY FOR SOMEONE WHO CANNOT FIND HIMSELF (the Owner, 2026-08-17). A person
   * who uploaded his own photograph spots it in the hall unaided, and a label
   * over it is clutter telling him what he already knows. The marker is for the
   * viewer wearing one of the three illustrated stand-ins, who is looking at a
   * face shared with everyone else who never uploaded one.
   *
   * This is not a spectator/chef distinction. A chef without his own picture is
   * in exactly the same position and gets the marker; a spectator with one does
   * not.
   */
  function markMySeat(svg) {
    var label = svg.querySelector('.arena-seat-label--mine');
    if (!label) { return; }
    var slug = viewerSlug();
    if (!slug) { label.setAttribute('hidden', 'hidden'); return; }

    var seat = svg.querySelector('.arena-cell[data-entity-slug="' + slug + '"]');
    if (!seat) { label.setAttribute('hidden', 'hidden'); return; }
    if (seat.getAttribute('data-avatar-default') !== '1') {
      label.setAttribute('hidden', 'hidden'); return;
    }

    var cx = parseFloat(seat.getAttribute('data-centroid-x'));
    var cy = parseFloat(seat.getAttribute('data-centroid-y'));
    if (!isFinite(cx) || !isFinite(cy)) { label.setAttribute('hidden', 'hidden'); return; }

    // Above the head, not across the face: a marker that covers the avatar it
    // points at defeats itself. The lift is a fraction of the cell's own
    // radial band so it scales with the ring rather than drifting on the
    // outer ones.
    var inner = parseFloat(seat.getAttribute('data-ring-inner'));
    var outer = parseFloat(seat.getAttribute('data-ring-outer'));
    var band = (isFinite(inner) && isFinite(outer)) ? Math.abs(outer - inner) : 14;
    label.setAttribute('x', cx.toFixed(2));
    label.setAttribute('y', (cy - band * 0.62).toFixed(2));
    label.setAttribute('font-size', Math.min(11, Math.max(5, band * 0.42)).toFixed(1));
    label.removeAttribute('hidden');
  }

  /**
   * Ring 11 is the sponsors' (ARENA_BATTLE_PLAN 2a). The server decides WHO is
   * entitled to a box — only publicly active cells reach the payload — and the
   * arena decides WHERE, because the boxes are the arena's own and share no
   * grid with the Sponsors puzzle.
   *
   * Seating is by list order into box order, which is stable across polls: a
   * sponsor whose standing has not changed must not hop around the ring every
   * thirty seconds. Every box is cleared first, so a sponsorship that lapses
   * empties its box instead of leaving a ghost sitting in it.
   */
  function seatSponsors(svg, sponsors) {
    var layer = svg.querySelector('[data-arena-layer="sponsors"]');
    if (!layer) { return; }
    while (layer.firstChild) { layer.removeChild(layer.firstChild); }

    var boxes = svg.querySelectorAll('.arena-cell--vip');
    var i;
    for (i = 0; i < boxes.length; i++) {
      boxes[i].setAttribute('data-occupancy', 'empty');
      boxes[i].removeAttribute('data-sponsor-url');
      boxes[i].sponsorRecord = null;
    }
    Array.prototype.forEach.call(svg.querySelectorAll('[data-vip-label]'), function (label) {
      label.removeAttribute('hidden');
    });
    Array.prototype.forEach.call(svg.querySelectorAll('[data-vip-spark]'), function (spark) {
      spark.removeAttribute('data-lit');
    });

    var list = Array.isArray(sponsors) ? sponsors : [];
    var seats = Math.min(list.length, boxes.length);
    for (i = 0; i < seats; i++) {
      var sponsor = list[i];
      var box = boxes[i];
      var cell = box.getAttribute('data-cell');
      box.setAttribute('data-occupancy', 'sponsor');
      if (sponsor.url) { box.setAttribute('data-sponsor-url', sponsor.url); }
      box.sponsorRecord = sponsor;

      // The ring signs itself only where it is unsold. A box with a sponsor in
      // it carries the sponsor, not the letter S of the word SPONSORS.
      var label = svg.querySelector('[data-vip-label="' + cell + '"]');
      if (label) { label.setAttribute('hidden', 'hidden'); }

      var vipSpark = svg.querySelector('[data-vip-spark="' + cell + '"]');
      if (vipSpark) { vipSpark.setAttribute('data-lit', 'true'); }

      // A logo goes in exactly the way a chef's face does (appendOccupant):
      // measure the box, cover its bbox with a square 8% larger, slice rather
      // than fit, and clip the whole thing to the box. A logo placed by its
      // centroid instead sat in the middle of a wedge with air around it and
      // read as a sticker; covering-and-clipping makes it the box's own surface,
      // which is what the Owner is buying when he sells one.
      var bbox = box.getBBox();
      var size = Math.max(bbox.width, bbox.height) * 1.08;
      var mark = el('g', {
        'clip-path': 'url(#arena-clip-vip-' + cell + ')',
        'pointer-events': 'none',
        class: 'arena-vip-sponsor'
      });

      if (sponsor.logo) {
        mark.appendChild(el('image', {
          href: sponsor.logo,
          x: (bbox.x + bbox.width / 2 - size / 2).toFixed(2),
          y: (bbox.y + bbox.height / 2 - size / 2).toFixed(2),
          width: size.toFixed(2), height: size.toFixed(2),
          preserveAspectRatio: 'xMidYMid slice',
          'pointer-events': 'none',
          class: 'arena-vip-sponsor-logo'
        }));
      } else {
        // The analogue of a chef's initial: a paid box must never read as free,
        // whatever the record carries. A long trading name would run out of the
        // box, so it shows what fits and the title carries the whole of it.
        var name = el('text', {
          x: (bbox.x + bbox.width / 2).toFixed(2),
          y: (bbox.y + bbox.height / 2).toFixed(2),
          'text-anchor': 'middle', 'dominant-baseline': 'central',
          'pointer-events': 'none',
          class: 'arena-vip-sponsor-name'
        });
        name.textContent = sponsor.name.length > 12
          ? sponsor.name.slice(0, 11) + '…'
          : sponsor.name;
        mark.appendChild(name);
      }

      var title = el('title', {});
      title.textContent = sponsor.name;
      mark.appendChild(title);
      layer.appendChild(mark);
    }
  }

  function viewerSlug() {
    return (global.ARENA_VIEWER && global.ARENA_VIEWER.slug) || '';
  }

  /**
   * Which free seats this viewer may take: the galleries, and only those.
   *
   * Moving seat is a SPECTATOR'S option (Owner, 2026-08-17) - an author moves
   * to sit beside somebody. A chef's cell is decided by the scatter from his
   * slug so it holds still across polls, and a rank ring is a rank rather
   * than a seating preference, so a rank cell is never offered to anybody.
   * Anonymous visitors cannot sit at all and are never offered a seat.
   */
  function markSeatable(svg, geometry) {
    var kindByRing = {};
    geometry.rings.forEach(function (ring) { kindByRing[ring.index] = ring.kind; });

    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell[data-ring]'), function (polygon) {
      var ring = Number(polygon.getAttribute('data-ring'));
      var seatable = false;
      // Owner, 2026-08-17: MOVING SEAT IS A SPECTATOR'S OPTION AND NOBODY
      // ELSE'S. "у зрителей нет ранговых колец, они все за пределами
      // октагона, октагон только для шефов".
      //
      // This used to offer a seated CHEF the other empty cells of his own rank
      // ring, which reads as a choice he does not have: a chef's cell is
      // decided by the scatter from his slug so it stays put across polls, and
      // a rank ring is a rank, not a seating preference. Only the galleries
      // are ever offered now, to anybody, and the branch that treated a rank
      // ring as re-seatable is gone rather than narrowed.
      //
      // The point of the option is social, and it is why it belongs to
      // spectators alone: an author moves to sit NEXT TO somebody.
      if (viewerSlug() && polygon.getAttribute('data-occupancy') === 'empty') {
        seatable = kindByRing[ring] === 'spectator';
      }
      if (seatable) { polygon.setAttribute('data-seatable', 'true'); }
      else { polygon.removeAttribute('data-seatable'); }
    });
  }

  function asSpectator(spectator) {
    return {
      name: spectator.name, slug: spectator.slug, avatar_url: spectator.avatar_url,
      rank_label: 'Spectator', rating: '',
      in_battle: false, is_online: true, is_spectator: true
    };
  }

  function stampStage(svg, center) {
    var stage = svg.querySelector('[data-arena-stage]');
    if (!stage) { return; }
    stageCentre = center;
    stage.setAttribute('data-state', center.type || 'empty');
    stage.style.cursor = center.battle_url ? 'pointer' : 'default';
    // Same key the command deck stamps on its own live stage, so the effects
    // layer can key both surfaces off one identity.
    var key = global.ArenaDeck ? global.ArenaDeck.centreKey(center) : 'empty';
    var arrived = centreKey !== null && centreKey !== key && key !== 'empty';
    centreKey = key;
    stage.setAttribute('data-centre-key', key);
    if (arrived) { flashTeleport(svg); }
    stampFloorCentre(svg, center);
  }

  // Mockup M07: large challenger/opponent hex tiles ON the floor (green left /
  // red right), not only the HTML confrontation band. Uses existing
  // center.challenger / center.opponent fighter contract — no new payload.
  function hexPoints(cx, cy, r) {
    var pts = [];
    for (var i = 0; i < 6; i++) {
      var a = (Math.PI / 180) * (60 * i - 30);
      pts.push({ x: cx + r * Math.cos(a), y: cy + r * Math.sin(a) });
    }
    return pts;
  }

  /**
   * A09: how far from the arena centre each fighter pad sits, in plan units.
   *
   * MEASURED OFF THE REFERENCE, 2026-08-05, not copied from a summary. Its two
   * fighters are `image-slot` elements 190 x 212, centred at x 700 and x 1220 on
   * a 1920 canvas — exactly 260px either side of centre, symmetric to the pixel.
   * Its crown block is 190 wide. So the CLEAR FLOOR between the crown's edge and
   * a fighter's edge is 260 - 95 - 95 = 70px against a 1585.4-wide floor grid:
   *
   *     gap / floor width = 70 / 1585.4 = 0.044153
   *
   * That fraction is what transfers, and it is camera-free because rotateX
   * leaves x untouched. What does NOT transfer is the reference's y: that block
   * is taller than it is wide and stands upright above the crown, while our
   * fighters lie flat on the floor plane on purpose (v2.5.649 — a nested 3D
   * billboard shattered the camera). Reading its y as a floor offset is exactly
   * the mistake that produced A07's withdrawn target, so the pads stay on the
   * crown's own plane and only their x moves.
   *
   * WHY THE GAP AND NOT THE OFFSET. Copying the offset directly — 0.164 of the
   * floor width, 154 plan units here — is not merely different, it is
   * impossible: our crown half-width (82) plus a pad half-width (94) is 176,
   * so the pads would overlap the crown. Both of our centre blocks are larger
   * relative to the floor than the reference's, and the card asks for placement,
   * not resizing. The gap is the part of the composition that can be honoured
   * without touching either block.
   */
  function fighterOffset(padR) {
    var tpl = global.ArenaOctagon;
    var floorOuter = tpl ? tpl.OUTER : 515;
    // Octagon width across the flats, which is what the rank grid spans.
    var floorWidth = 2 * floorOuter * Math.cos(Math.PI / 8);
    return STAGE_RADIUS + REFERENCE_FIGHTER_GAP * floorWidth + padR;
  }

  /**
   * A10 — HOW BIG THE CROWN HUB IS, TAKEN FROM THE REFERENCE AND NOT INVENTED.
   *
   * Measured off the approved Design Template in
   * ops/audits/arena/A06_remeasure_2026-08-04.md: the crown block is 190 wide on
   * a floor grid 1585.4 wide, which is 0.1198 of the floor. Production drew it
   * from STAGE_RADIUS - the crown PLATE of the octagon geometry - which is 82,
   * so the hub spanned 164 against a floor of 1030: 0.159, a third too wide.
   * That is the whole of the size half of this card.
   *
   * It is deliberately NOT done by moving CROWN_OUTER. That constant is the
   * inner edge of the moat and the base of rankStep, so shrinking it would
   * widen every one of the eight rank rings - a change to the floor the Owner
   * froze in ARENA_BATTLE_PLAN section 2, made in passing, to fix the crown.
   * The plate keeps its size; the hub is drawn smaller inside it, which is the
   * recess this card also asks for.
   *
   * STAGE_RADIUS is untouched for the same reason: the fighter plinths, the VS
   * and the lamp strobes are all measured off it, and the fighters' 260px
   * either side of centre came off the same reference file.
   */
  var REFERENCE_CROWN_SHARE = 0.1198;

  function crownRadius() {
    var tpl = global.ArenaOctagon;
    var floorOuter = tpl ? tpl.OUTER : 515;
    // The reference share is of the floor's full span; span = 2 * outer, so the
    // radius is the share of the outer radius.
    return REFERENCE_CROWN_SHARE * floorOuter;
  }

  function stampFloorCentre(svg, center) {
    var layer = svg.querySelector('[data-arena-layer="centre"]');
    if (!layer) { return; }
    while (layer.firstChild) { layer.removeChild(layer.firstChild); }

    // Plan coords — CSS rotateX(42deg) on #arena-render tilts the whole floor
    // including these pads, so they share the octagon plane (mockup M07).
    var cx = TPL_CX;
    var cy = TPL_CY;
    var type = (center && center.type) || '';
    var padR = STAGE_RADIUS * 1.15;
    var offset = fighterOffset(padR);
    var stage = svg.querySelector('.arena-stage');
    if (stage) {
      stage.setAttribute('data-state', type || 'empty');
      stage.setAttribute('data-occupancy', type === 'crown' ? 'crown' : 'stage');
    }

    // THE PADS APPEAR WHEN THE FIGHT DOES. Owner, 2026-08-07: "скрой ячейки для
    // шефов перед боем - пусть они появляются только когда шефы начинают бой."
    //
    // This reverses v2.5.848, which drew them permanently and then muted them on
    // his instruction of the same day. The muting was the half-measure; the
    // decision now is that an idle floor has no fighting cells on it at all, and
    // the two hexes ARE the announcement that a bout has started. Nothing else
    // in stampFloorCentre changes: an occupied centre still draws them through
    // drawFloorFighter, which is the only path that ever put a chef on one.
    if (!type) { return; }

    if (type === 'active_battle' || type === 'facing_pair') {
      drawFloorFighter(svg, layer, center.challenger, { x: cx - offset, y: cy }, padR, 'challenger');
      drawFloorVs(layer, cx, cy, STAGE_RADIUS * 0.92, center);
      drawFloorFighter(svg, layer, center.opponent, { x: cx + offset, y: cy }, padR, 'opponent');
      return;
    }

    if (type === 'crown') {
      // Reference: centre octagon holds crown glyph + nick only — never the
      // holder avatar (that would cover / mis-read the stage pad).
      drawFloorCrown(layer, cx, cy, crownRadius(), center);
    }
  }

  function octagonPathD(cx, cy, R) {
    var pts = [];
    var i;
    for (i = 0; i < 8; i++) {
      var angle = i * Math.PI / 4;
      pts.push((cx + R * Math.cos(angle)).toFixed(2) + ',' + (cy + R * Math.sin(angle)).toFixed(2));
    }
    return 'M ' + pts.join(' L ') + ' Z';
  }

  /** One-time defs: tilt-aware gold rim + warm bulb glow (no SVG filter blur). */
  function ensureCrownStageDefs(svg) {
    if (svg.querySelector('#arena-crown-rim-grad')) { return; }
    var defs = svg.querySelector('defs');
    if (!defs) { return; }

    var rimGrad = el('linearGradient', {
      id: 'arena-crown-rim-grad',
      gradientUnits: 'userSpaceOnUse',
      x1: TPL_CX.toFixed(2),
      y1: (TPL_CY - STAGE_RADIUS * 1.2).toFixed(2),
      x2: TPL_CX.toFixed(2),
      y2: (TPL_CY + STAGE_RADIUS * 1.2).toFixed(2)
    });
    // rotateX(42deg): plan-top = far/shadow, plan-bottom = near/highlight.
    rimGrad.appendChild(el('stop', { offset: '0%', 'stop-color': '#8a5a18' }));
    rimGrad.appendChild(el('stop', { offset: '28%', 'stop-color': '#d4a017' }));
    rimGrad.appendChild(el('stop', { offset: '55%', 'stop-color': '#f0c85a' }));
    rimGrad.appendChild(el('stop', { offset: '78%', 'stop-color': '#ffe9a0' }));
    rimGrad.appendChild(el('stop', { offset: '100%', 'stop-color': '#fff6d0' }));
    defs.appendChild(rimGrad);

    var recessGrad = el('linearGradient', {
      id: 'arena-crown-recess-grad',
      gradientUnits: 'userSpaceOnUse',
      x1: TPL_CX.toFixed(2),
      y1: (TPL_CY - STAGE_RADIUS * 1.4).toFixed(2),
      x2: TPL_CX.toFixed(2),
      y2: (TPL_CY + STAGE_RADIUS * 1.4).toFixed(2)
    });
    recessGrad.appendChild(el('stop', { offset: '0%', 'stop-color': '#1a120c' }));
    recessGrad.appendChild(el('stop', { offset: '55%', 'stop-color': '#2a1e14' }));
    recessGrad.appendChild(el('stop', { offset: '100%', 'stop-color': '#4a3524' }));
    defs.appendChild(recessGrad);

    var bulbGrad = el('radialGradient', { id: 'arena-crown-bulb-grad', cx: '50%', cy: '50%', r: '50%' });
    bulbGrad.appendChild(el('stop', { offset: '0%', 'stop-color': '#fff4d0' }));
    bulbGrad.appendChild(el('stop', { offset: '35%', 'stop-color': '#ffb347' }));
    bulbGrad.appendChild(el('stop', { offset: '100%', 'stop-color': '#ff8c1a', 'stop-opacity': '0' }));
    defs.appendChild(bulbGrad);
  }

  /**
   * Two beams for one lamp: one inward over the marble, one outward across the
   * moat into the ranks. Each is an isoceles triangle with its apex ON the lamp,
   * so the light reads as coming out of it rather than lying beside it.
   *
   * The fade needs a gradient that runs apex → far end, and that axis is
   * different for every lamp, so the gradient cannot be shared: each beam gets
   * its own, in user space, rebuilt on every draw because a stage resize moves
   * the lamps and a stale axis would leave the light pointing the wrong way.
   */
  function addLampCones(defs, group, bx, by, angle, radius, index, far, scale, dirs) {
    var ux = Math.cos(angle);
    var uy = Math.sin(angle);
    // Perpendicular to the beam: the base of the triangle is measured on it.
    var px = -uy;
    var py = ux;
    // The second row is the quieter one: its beams are scaled down so the two
    // rows read as a pattern rather than as sixteen equal spokes.
    var k = typeof scale === 'number' ? scale : 1;
    // Reach and spread are fractions of the stage radius, never fixed numbers,
    // so both survive a resize the same way the bulbs do. The outward beam is
    // longer and wider because it has the whole moat to cross before it lands.
    // Owner 2026-07-31: the inward beam is WHITE and reaches further. Warm gold
    // on dark green marble reads as a stain, not as a lamp; white reads as
    // light. The outward beam keeps the warm tone — it lands on the tan rank
    // rings, where white would vanish.
    var beams = [
      { key: 'in', reach: -radius * 0.78 * k, half: radius * 0.115 * k, white: true },
      { key: 'out', reach: radius * 0.78 * k, half: radius * 0.230 * k, white: false }
    ].filter(function (beam) {
      // A row may light one way only — the corner lamps face the marble and
      // have nothing to say to the moat behind them.
      return !dirs || dirs.indexOf(beam.key) !== -1;
    });

    for (var b = 0; b < beams.length; b++) {
      var beam = beams[b];
      var tipX = bx + ux * beam.reach;
      var tipY = by + uy * beam.reach;
      var gradId = 'arena-crown-cone-' + beam.key + '-' + index;
      var stale = defs.querySelector('#' + gradId);
      if (stale) { stale.remove(); }

      var grad = el('linearGradient', {
        id: gradId,
        gradientUnits: 'userSpaceOnUse',
        x1: bx.toFixed(2), y1: by.toFixed(2),
        x2: tipX.toFixed(2), y2: tipY.toFixed(2)
      });
      // Faded to nothing at the far end — a beam with a hard edge reads as a
      // painted shape, not as light. White for the beam that crosses the green
      // marble, the lamp's own warm tone for the one that crosses the tans.
      var tone = beam.white
        ? ['#ffffff', '#f4f7ff', '#dfe8ff']
        : ['#ffd489', '#ffb347', '#ff8c1a'];
      grad.appendChild(el('stop', {
        offset: '0%', 'stop-color': tone[0], 'stop-opacity': far ? '0.5' : '0.62'
      }));
      grad.appendChild(el('stop', {
        offset: '45%', 'stop-color': tone[1], 'stop-opacity': far ? '0.16' : '0.22'
      }));
      grad.appendChild(el('stop', {
        offset: '100%', 'stop-color': tone[2], 'stop-opacity': '0'
      }));
      defs.appendChild(grad);

      group.appendChild(el('polygon', {
        points: [
          bx.toFixed(2) + ',' + by.toFixed(2),
          (tipX + px * beam.half).toFixed(2) + ',' + (tipY + py * beam.half).toFixed(2),
          (tipX - px * beam.half).toFixed(2) + ',' + (tipY - py * beam.half).toFixed(2)
        ].join(' '),
        fill: 'url(#' + gradId + ')',
        'pointer-events': 'none',
        // Owner 2026-07-31: every beam sweeps, 90 degrees right and 90 left of
        // where it starts. The pivot has to be the lamp itself, so the origin is
        // written per beam in viewBox units — `transform-box: view-box` makes
        // those two numbers mean the same coordinates the polygon is drawn in.
        // The sweep is a CSS animation rather than SMIL for one reason: CSS is
        // what `prefers-reduced-motion` can switch off.
        style: 'transform-origin: ' + bx.toFixed(2) + 'px ' + by.toFixed(2) + 'px',
        class: 'arena-floor-crown__cone arena-floor-crown__cone--' + beam.key
      }));
    }
  }

  /**
   * Reference (Capture2): raised green marble + thin bright gold lip;
   * separate sunken moat outside gold with bulbs on flat edges — not on vertices.
   */
  function drawCrownStageFrame(stack, svg, cx, cy, radius) {
    ensureCrownStageDefs(svg);
    // Ring footprint halved vs v664; gold sits tight on the marble edge.
    var goldOuterR = radius + radius * 0.006;
    var moatGap = radius * 0.035;
    var recessInnerR = goldOuterR + moatGap;
    var recessOuterR = recessInnerR + radius * 0.085;
    var frame = el('g', { class: 'arena-floor-crown__frame', 'pointer-events': 'none' });

    frame.appendChild(el('path', {
      d: octagonPathD(cx, cy, recessOuterR) + ' ' + octagonPathD(cx, cy, recessInnerR),
      'fill-rule': 'evenodd',
      fill: 'url(#arena-crown-recess-grad)',
      stroke: 'none',
      class: 'arena-floor-crown__recess'
    }));

    frame.appendChild(el('path', {
      d: octagonPathD(cx, cy, recessInnerR),
      fill: 'none',
      stroke: '#120c08',
      'stroke-width': '0.9',
      opacity: '0.55',
      class: 'arena-floor-crown__recess-wall'
    }));

    var defs = svg.querySelector('defs');
    // Owner 2026-07-31: every lamp throws a wedge of light BOTH ways along its
    // face normal — inward across the marble toward the crown, outward over the
    // moat into the rank rings. A bulb's halo is a circle and a circle has no
    // direction; the direction is the whole point of the light, so the beam is
    // a triangle with its apex on the lamp. Cones are their own group, laid
    // down before the bulbs, so a beam never paints over the lamp that casts it.
    var cones = el('g', { class: 'arena-floor-crown__cones' });
    var bulbs = el('g', { class: 'arena-floor-crown__bulbs' });
    // Centre of the brown band, measured along the edge normal. octagonPathD
    // takes a CIRCUMradius, but a bulb sits on a flat edge, whose distance from
    // the centre is the APOTHEM — shorter by cos(PI/8). Using the circumradius
    // here pushed every bulb about 7.6% of the radius too far out, past the
    // outer wall, so none of them sat in the band they belong to.
    var apothem = Math.cos(Math.PI / 8);
    var bandMid = (recessInnerR + recessOuterR) / 2;

    // Owner 2026-07-31: a SECOND row of lamps, turned against the first.
    //
    // Row one stands on the eight flat edges, so its beams leave along the edge
    // normals and the eight directions between them stay dark. Row two stands
    // on the eight vertices — the same band, rotated by half a face — and fills
    // exactly those gaps, so the light leaves the plate in sixteen directions.
    //
    // The two rows do NOT share a radius. A lamp on a flat edge sits an APOTHEM
    // from the centre; a lamp on a vertex sits a full CIRCUMradius out. Using
    // one number for both would sink the vertex lamps into the plate — the same
    // mistake the apothem note above was written for, in the other direction.
    // The two rows are no longer "on the edges" and "on the corners" — the Owner
    // moved them on the lamp console, so they are named by which one is outside
    // the other and nothing here assumes an angle. Both radius and angle come
    // from lampLayout(), which is the console's value when he has set one and
    // LAMP_DEFAULTS otherwise.
    var layout = lampLayout();
    var rows = [
      {
        key: 'outer', offset: layout.outer.deg * Math.PI / 180,
        lampR: radius * layout.outer.r, scale: 1, dirs: ['in', 'out']
      },
      {
        key: 'inner', offset: layout.inner.deg * Math.PI / 180,
        lampR: radius * layout.inner.r, scale: 0.82, dirs: ['in']
      }
    ];
    var i, r;
    for (r = 0; r < rows.length; r++) {
      var row = rows[r];
      var bulbR = row.lampR;
      for (i = 0; i < 8; i++) {
        var angle = i * Math.PI / 4 + row.offset;
        var bx = cx + bulbR * Math.cos(angle);
        var by = cy + bulbR * Math.sin(angle);
        var far = Math.sin(angle) < -0.05;
        // Glow reaches the gold lip: the halo is sized by the DISTANCE between
        // the bulb and the lip, so a halo smaller than that gap could never
        // light it. Sized from the radius, not a fixed number, so it survives a
        // stage resize.
        //
        // THE DISTANCE, not the difference. The lamp rows are positioned from
        // the lamp console - the Owner's own numbers - and he has moved the
        // inner row INSIDE the gold lip, where bulbR is smaller than the lip
        // radius and the subtraction goes negative. SVG refuses a negative r,
        // so every repaint threw 34 console errors and both halo rings were
        // dropped: the lamps were lit and their glow was silently missing. It
        // is a distance in both directions - a bulb inside the lip lights it
        // just as a bulb outside does - with a floor so a bulb sitting exactly
        // on the lip still glows. The floor is keyed to the radius for the same
        // reason the rest of this block is.
        var lipGap = Math.abs(bulbR - goldOuterR * apothem);
        var glowR = Math.max(radius * 0.006,
                             lipGap * (far ? 1.15 : 1.45) * row.scale);
        bulbs.appendChild(el('circle', {
          cx: bx.toFixed(2),
          cy: by.toFixed(2),
          r: glowR.toFixed(2),
          fill: 'url(#arena-crown-bulb-grad)',
          class: 'arena-floor-crown__bulb-glow' + (far ? ' arena-floor-crown__bulb-glow--far' : '')
        }));
        bulbs.appendChild(el('circle', {
          cx: bx.toFixed(2),
          cy: by.toFixed(2),
          r: (radius * (far ? 0.0104 : 0.0140) * row.scale).toFixed(2),
          fill: 'url(#arena-crown-bulb-grad)',
          class: 'arena-floor-crown__bulb-core' + (far ? ' arena-floor-crown__bulb-core--far' : '')
        }));

        if (defs) {
          addLampCones(defs, cones, bx, by, angle, radius, row.key + '-' + i, far, row.scale, row.dirs);
        }
      }
    }
    // Soft under-edge so gold reads as a raised lip, then bright gold stroke.
    frame.appendChild(el('path', {
      d: octagonPathD(cx, cy, goldOuterR),
      fill: 'none',
      stroke: '#6b4510',
      'stroke-width': '3.2',
      opacity: '0.45',
      class: 'arena-floor-crown__gold-shadow'
    }));
    frame.appendChild(el('path', {
      d: octagonPathD(cx, cy, goldOuterR),
      fill: 'none',
      stroke: 'url(#arena-crown-rim-grad)',
      'stroke-width': '1.8',
      class: 'arena-floor-crown__gold-lip'
    }));

    stack.appendChild(frame);

    // Bulbs go on TOP of the gold. Drawn under it, as they were, the lip
    // painted over every glow and no light could reach the gold at all — and
    // the same trap sits one layer further out: the marble pad is appended
    // AFTER this frame and clipped to the plate, so anything drawn here that
    // falls inside the plate is painted over by the marble. That is where the
    // whole inward half of the light went. The lamps and their beams are handed
    // back instead of appended, for the caller to lay down after the marble.
    var over = el('g', { class: 'arena-floor-crown__light', 'pointer-events': 'none' });
    over.appendChild(cones);
    over.appendChild(bulbs);

    // Owner 2026-07-31: the travelling spot from the Enter Arena button, on the
    // gold ring. That button does it with a conic gradient masked to its border
    // (header.css, ce-glint-spin) and none of that transfers to SVG — a path has
    // no background to mask. Same effect, SVG's own mechanics: one short bright
    // dash chasing its way round the ring. pathLength = 100 normalises the
    // octagon's perimeter, so the dash and its speed are written in percent and
    // do not have to be recomputed when the stage is resized.
    over.appendChild(el('path', {
      d: octagonPathD(cx, cy, goldOuterR),
      pathLength: '100',
      fill: 'none',
      class: 'arena-floor-crown__gold-spot'
    }));
    return over;
  }

  function drawFloorCrown(layer, cx, cy, radius, center) {
    var assets = global.ARENA_CROWN_ASSETS || {};
    var svg = layer.ownerSVGElement || document.getElementById('arena-render');
    var stack = el('g', {
      class: 'arena-floor-crown',
      'pointer-events': 'none'
    });

    var crownLight = drawCrownStageFrame(stack, svg, cx, cy, radius);

    var group = el('g', {
      class: 'arena-floor-crown__inner',
      'clip-path': 'url(#arena-clip-0-0)'
    });
    var size = radius * 2;

    if (assets.pad) {
      group.appendChild(el('image', {
        href: assets.pad,
        x: (cx - size / 2).toFixed(2),
        y: (cy - size / 2).toFixed(2),
        width: size.toFixed(2),
        height: size.toFixed(2),
        preserveAspectRatio: 'xMidYMid slice',
        class: 'arena-floor-crown__pad'
      }));
    }

    if (assets.glyph) {
      // A10, second half - the type hierarchy inside the hub, measured off the
      // same reference. Its crown block is 190 wide and its glyph is set at
      // 52px: 0.274 of the block. Ours was 0.62 of the RADIUS, which is 0.31 of
      // the block - 13 per cent oversized, the only figure in the hub that was
      // out of family. The CROWN HOLDER label (0.050 against 0.047) and the
      // fitted name (up to 0.120 against 0.116) were already inside measurement
      // noise of the reference and are left exactly as they are.
      var gSize = radius * 0.547;
      group.appendChild(el('image', {
        href: assets.glyph,
        x: (cx - gSize / 2).toFixed(2),
        y: (cy - radius * 0.60).toFixed(2),
        width: gSize.toFixed(2),
        height: gSize.toFixed(2),
        preserveAspectRatio: 'xMidYMid meet',
        class: 'arena-floor-crown__glyph'
      }));
    }

    var label = el('text', {
      x: cx.toFixed(2),
      y: (cy + radius * 0.20).toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      'font-size': (radius * 0.10).toFixed(1),
      class: 'arena-floor-crown__label'
    });
    label.textContent = 'CROWN HOLDER';
    group.appendChild(label);

    var nameY = cy + radius * CROWN_NAME_Y_FACTOR;
    var name = el('text', {
      x: cx.toFixed(2),
      y: nameY.toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      class: 'arena-floor-crown__name'
    });
    group.appendChild(name);
    stack.appendChild(group);

    // Gold lip must paint over marble edge (raised rim, not recessed).
    ['.arena-floor-crown__gold-shadow', '.arena-floor-crown__gold-lip'].forEach(function (sel) {
      var node = stack.querySelector(sel);
      if (node && node.parentNode) {
        node.parentNode.removeChild(node);
        stack.appendChild(node);
      }
    });

    // Last of all: the lamps and their beams, so the marble cannot swallow the
    // inward half of the light and the gold lip cannot swallow the lamps.
    if (crownLight) { stack.appendChild(crownLight); }

    layer.appendChild(stack);
    fitCrownName(
      name,
      (center && center.name) || '',
      crownNameMaxWidth(radius, nameY - cy),
      radius
    );
  }

  /** Half-width of the stage octagon (verts at 0°/45°/…) at vertical offset dy. */
  function octagonHalfWidthAt(radius, dy) {
    var c22 = Math.cos(Math.PI / 8);
    var s22 = Math.sin(Math.PI / 8);
    var ady = Math.abs(dy);
    if (ady <= radius * s22) { return radius * c22; }
    var x1 = radius * c22;
    var y1 = radius * s22;
    var x2 = radius * s22;
    var y2 = radius * c22;
    var t = (ady - y1) / (y2 - y1);
    return x1 + t * (x2 - x1);
  }

  function crownNameMaxWidth(radius, dy) {
    return Math.max(0, 2 * octagonHalfWidthAt(radius, dy) - 2 * CROWN_NAME_PAD);
  }

  /**
   * Adaptive crown nick: shorter names render larger (up to FONT_MAX), longer
   * names settle smaller. Binary-search the largest size that still fits the
   * octagon chord; char ceiling stays CROWN_NAME_MAX_CHARS.
   */
  function fitCrownName(textNode, raw, maxWidth, radius) {
    var full = String(raw || '').trim();
    if (!full) {
      textNode.textContent = '';
      return;
    }

    var display = full.length > CROWN_NAME_MAX_CHARS
      ? full.slice(0, CROWN_NAME_MAX_CHARS - 1) + '\u2026'
      : full;
    textNode.textContent = display;

    var maxFs = radius * CROWN_NAME_FONT_MAX;
    var minFs = radius * CROWN_NAME_FONT_MIN;
    var hardMax = maxWidth > 0 ? maxWidth : Infinity;
    // Leave a little air from the gold rim so the nick does not kiss the edge.
    var fitMax = maxWidth > 0 ? maxWidth * CROWN_NAME_FILL : hardMax;

    var lo = minFs;
    var hi = maxFs;
    var best = minFs;
    var i;
    for (i = 0; i < 18; i++) {
      var mid = (lo + hi) / 2;
      textNode.setAttribute('font-size', mid.toFixed(1));
      var w = textNode.getComputedTextLength();
      if (w <= fitMax) {
        best = mid;
        lo = mid;
      } else {
        hi = mid;
      }
    }
    textNode.setAttribute('font-size', best.toFixed(1));

    // Floor size still overflows (very wide glyphs) — trim characters.
    if (textNode.getComputedTextLength() > hardMax) {
      textNode.setAttribute('font-size', minFs.toFixed(1));
      var limit = Math.min(full.length, CROWN_NAME_MAX_CHARS);
      var loC = 1;
      var hiC = limit;
      var bestC = 1;
      while (loC <= hiC) {
        var midC = (loC + hiC) >> 1;
        var candidate = midC < full.length
          ? full.slice(0, midC) + '\u2026'
          : full.slice(0, midC);
        textNode.textContent = candidate;
        if (textNode.getComputedTextLength() <= hardMax) {
          bestC = midC;
          loC = midC + 1;
        } else {
          hiC = midC - 1;
        }
      }
      textNode.textContent = bestC < full.length
        ? full.slice(0, bestC) + '\u2026'
        : full.slice(0, bestC);
    }
  }

  function drawFloorVs(layer, cx, cy, radius, center) {
    var tpl = global.ArenaOctagon;
    // Same octagon math as .arena-stage — not a hex — so VS sits in the true centre pad.
    var points = tpl
      ? tpl.octagonPoints(cx, cy, radius)
      : hexPoints(cx, cy, radius).map(pointString).join(' ');
    var group = el('g', {
      class: 'arena-floor-vs',
      'pointer-events': 'none'
    });
    group.appendChild(el('polygon', {
      points: points,
      class: 'arena-floor-vs__tile',
      'vector-effect': 'non-scaling-stroke'
    }));
    var status = el('text', {
      x: cx.toFixed(2),
      y: (cy - radius * 0.42).toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      class: 'arena-floor-vs__status'
    });
    status.textContent = (center && center.status_display) || '';
    group.appendChild(status);
    var vs = el('text', {
      x: cx.toFixed(2),
      y: cy.toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      class: 'arena-floor-vs__mark'
    });
    vs.textContent = 'VS';
    group.appendChild(vs);
    if (center && center.theme) {
      var theme = el('text', {
        x: cx.toFixed(2),
        y: (cy + radius * 0.42).toFixed(2),
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        class: 'arena-floor-vs__theme'
      });
      theme.textContent = center.theme;
      group.appendChild(theme);
    }
    layer.appendChild(group);
  }

  function drawFloorFighter(svg, layer, fighter, centre, radius, side) {
    if (!fighter || !centre) { return; }
    var pts = hexPoints(centre.x, centre.y, radius);
    var points = pts.map(pointString).join(' ');
    var clipId = 'arena-floor-clip-' + side;
    var defs = svg.querySelector('defs');
    if (defs) {
      var old = svg.querySelector('#' + clipId);
      if (old) { old.parentNode.removeChild(old); }
      var clip = el('clipPath', { id: clipId });
      clip.appendChild(el('polygon', { points: points }));
      defs.appendChild(clip);
    }

    var group = el('g', {
      class: 'arena-floor-fighter arena-floor-fighter--' + side,
      'data-floor-side': side,
      'data-entity-slug': fighter.slug || '',
      'pointer-events': 'none'
    });
    group.appendChild(el('polygon', {
      points: points,
      class: 'arena-floor-fighter__tile',
      'vector-effect': 'non-scaling-stroke'
    }));
    if (fighter.avatar_url) {
      // Flat on the pad — same floor plane / rotateX as the octagon (no nested
      // 3D billboard: preserve-3d on SVG children shattered the camera).
      var size = radius * 1.55;
      group.appendChild(el('image', {
        href: fighter.avatar_url,
        x: (centre.x - size / 2).toFixed(2),
        y: (centre.y - size / 2).toFixed(2),
        width: size.toFixed(2),
        height: size.toFixed(2),
        preserveAspectRatio: 'xMidYMid slice',
        'clip-path': 'url(#' + clipId + ')',
        class: 'arena-floor-fighter__avatar'
      }));
    }

    // Identity belongs inside the octagon on a dark lower fade. This remains
    // part of the existing floor fighter, not a separate support panel.
    group.appendChild(el('rect', {
      x: (centre.x - radius).toFixed(2),
      y: (centre.y + radius * 0.20).toFixed(2),
      width: (radius * 2).toFixed(2),
      height: (radius * 0.80).toFixed(2),
      'clip-path': 'url(#' + clipId + ')',
      class: 'arena-floor-fighter__identity-shade'
    }));
    if (fighter.name) {
      var label = el('text', {
        x: centre.x.toFixed(2),
        y: (centre.y + radius * 0.48).toFixed(2),
        'text-anchor': 'middle',
        'dominant-baseline': 'middle',
        class: 'arena-floor-fighter__name'
      });
      label.textContent = fighter.name;
      group.appendChild(label);
    }
    var country = el('text', {
      x: centre.x.toFixed(2),
      y: (centre.y + radius * 0.73).toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      class: 'arena-floor-fighter__country'
    });
    country.textContent = ((fighter.flag || '\uD83C\uDDEE\uD83C\uDDEA') + ' ' +
      (fighter.country || 'Ireland')).trim();
    group.appendChild(country);
    layer.appendChild(group);
  }

  /**
   * Chefs have just taken the centre. Fired on the centre's identity changing,
   * not on anyone's slug: _arena_center() emits no slug, which is why the legacy
   * flash — keyed on `!prevSlugs[chef.slug]` — was true on every poll and
   * strobed instead of marking an arrival.
   */
  function flashTeleport(svg) {
    var ring = el('circle', {
      cx: TPL_CX, cy: TPL_CY, r: STAGE_RADIUS,
      fill: 'none', 'pointer-events': 'none',
      class: 'arena-teleport-flash'
    });
    svg.appendChild(ring);
    global.setTimeout(function () { ring.remove(); }, 900);
  }

  /* ---------------------------------------------------------------- */
  /* Interaction — ported from arena_puzzle.js                         */
  /* ---------------------------------------------------------------- */

  function tooltipEl() { return document.getElementById('arena-tooltip'); }

  /** The card's own label, remembered from the template on first use. */
  var linkLabel = null;
  function defaultLinkLabel(link) {
    if (linkLabel === null) { linkLabel = link.textContent; }
    return linkLabel;
  }

  /**
   * The sponsor's card — the chef's card, carrying a sponsor.
   *
   * Owner 2026-08-03: a sponsor must get the same card a chef gets, with a link
   * on it. So this fills the ONE card the arena has rather than building a
   * second: same element, same placement, same close behaviour. Everything that
   * belongs to a chef and not to a sponsor — rating, badges, wins and losses,
   * the challenge button — is hidden rather than left showing a chef's numbers
   * under a sponsor's name.
   */
  function showSponsorTooltip(sponsor, anchor) {
    var tip = tooltipEl();
    if (!tip) { return; }

    tip.setAttribute('data-rank', '');
    var avatar = tip.querySelector('.arena-tooltip__avatar');
    if (avatar) { avatar.src = sponsor.logo || ''; avatar.alt = sponsor.name || ''; }
    tip.querySelector('.arena-tooltip__name').textContent = sponsor.name || '';
    tip.querySelector('.arena-tooltip__rank').textContent = sponsor.tagline || 'Arena Sponsor';

    var rating = tip.querySelector('.arena-tooltip__rating');
    rating.textContent = '';
    rating.hidden = true;

    var link = tip.querySelector('.arena-tooltip__link');
    defaultLinkLabel(link);
    if (sponsor.url) {
      link.href = sponsor.url;
      link.textContent = 'Visit sponsor';
      // The sponsor's site opens in its own tab and gets no handle on ours.
      link.setAttribute('target', '_blank');
      link.setAttribute('rel', 'noopener noreferrer');
      link.hidden = false;
    } else {
      // A sponsor who gave no address gets a card without a dead link on it.
      link.hidden = true;
    }

    setHidden(tip.querySelector('.arena-tooltip__badge--battle'), true);
    setHidden(tip.querySelector('.arena-tooltip__badge--online'), true);
    setHidden(tip.querySelector('.arena-tooltip__stats'), true);
    var potential = tip.querySelector('.js-chef-potential');
    if (potential) { potential.hidden = true; }
    var challenge = tip.querySelector('.js-challenge-btn');
    if (challenge) { challenge.hidden = true; }

    tip.hidden = false;
    position(tip, anchor);
  }

  function showTooltip(chef, anchor) {
    var tip = tooltipEl();
    if (!tip) { return; }
    var viewer = global.ARENA_VIEWER || {};

    tip.setAttribute('data-rank', chef.rank || '');
    var avatar = tip.querySelector('.arena-tooltip__avatar');
    if (avatar) { avatar.src = chef.avatar_url || ''; avatar.alt = chef.name || ''; }
    tip.querySelector('.arena-tooltip__name').textContent = chef.name || '';
    tip.querySelector('.arena-tooltip__rank').textContent = chef.rank_label || '';

    var rating = tip.querySelector('.arena-tooltip__rating');
    rating.textContent = chef.rating ? 'Rating: ' + chef.rating : '';
    rating.hidden = !chef.rating;
    var link = tip.querySelector('.arena-tooltip__link');
    link.href = '/chef-battle/profile/' + chef.slug + '/';
    // The sponsor card borrows this same link and sends it off-site. Reset it
    // here or a chef's profile would open in a new tab once a sponsor had been
    // looked at, which is the kind of state a shared card leaks if nobody clears
    // it.
    link.textContent = defaultLinkLabel(link);
    link.removeAttribute('target');
    link.removeAttribute('rel');
    link.hidden = false;

    setHidden(tip.querySelector('.arena-tooltip__badge--battle'), !chef.in_battle);
    setHidden(tip.querySelector('.arena-tooltip__badge--online'), !chef.is_online);
    setHidden(tip.querySelector('.arena-tooltip__stats'), !!chef.is_spectator);
    setText(tip.querySelector('.js-chef-wins'), chef.wins || 0);
    setText(tip.querySelector('.js-chef-losses'), chef.losses || 0);
    setText(tip.querySelector('.js-chef-streak'), chef.win_streak || 0);

    var potential = tip.querySelector('.js-chef-potential');
    if (potential) {
      // AA7: bands, not sums - the server sends "40–60" or "" and the exact
      // aggregate never reaches the client at all. The template's own "~"
      // prefix went with the change; a range says "approximate" by itself.
      var atk = chef.atk_band || '';
      var def = chef.def_band || '';
      var show = !chef.is_spectator && (atk !== '' || def !== '');
      setText(tip.querySelector('.js-chef-atk'), atk || '—');
      setText(tip.querySelector('.js-chef-def'), def || '—');
      potential.hidden = !show;
    }

    var challenge = tip.querySelector('.js-challenge-btn');
    if (challenge) {
      var canChallenge = viewer.enrolled && viewer.slug && viewer.slug !== chef.slug &&
        !chef.in_battle && !chef.is_spectator;
      if (canChallenge) { challenge.href = '/chef-battle/challenge/new/?opponent=' + chef.slug; }
      challenge.hidden = !canChallenge;
    }

    var ownerControls = tip.querySelector('.js-arena-owner-controls');
    if (ownerControls) {
      var ownerSlug = viewer.slug || '';
      ownerControls.hidden = !chef.slug || chef.slug === ownerSlug;
      var slugInput = ownerControls.querySelector('.js-owner-chef-slug');
      if (slugInput) { slugInput.value = chef.slug || ''; }
      var confirmDelete = ownerControls.querySelector('.js-owner-delete-confirm');
      if (confirmDelete) { confirmDelete.checked = false; }
    }

    tip.hidden = false;
    position(tip, anchor);
  }

  function position(tip, anchor) {
    var rect = anchor.getBoundingClientRect();
    var margin = 8;
    var left = rect.left + (rect.width / 2) - (tip.offsetWidth / 2);
    var maxLeft = global.innerWidth - tip.offsetWidth - margin;
    var below = rect.bottom + margin;
    var above = rect.top - tip.offsetHeight - margin;
    var top = below + tip.offsetHeight <= global.innerHeight - margin
      ? below
      : Math.max(margin, above);
    tip.style.left = Math.max(margin, Math.min(left, maxLeft)) + 'px';
    tip.style.top = top + 'px';
  }

  function setHidden(node, hidden) { if (node) { node.hidden = hidden; } }
  function setText(node, value) { if (node) { node.textContent = value; } }

  function hideTooltip() {
    var tip = tooltipEl();
    if (tip) { tip.hidden = true; }
  }

  /** One-shot ripple centred on the activated SVG cell.
   *
   * The Arena carries a CSS 3D rotateX transform. getScreenCTM() is a 2D
   * matrix and cannot reliably invert that projection, so client coordinates
   * put the ripple beside the clicked cell. The cell's own SVG bbox is already
   * in the correct user space and remains stable at every camera scale.
   */
  function fireRipple(svg, anchor) {
    if (!anchor || !anchor.getBBox) { return; }
    var box = anchor.getBBox();
    var at = {
      x: box.x + box.width / 2,
      y: box.y + box.height / 2
    };
    var circle = el('circle', {
      cx: at.x.toFixed(1), cy: at.y.toFixed(1), r: '0',
      fill: 'rgba(58,48,40,0.28)', 'pointer-events': 'none'
    });
    svg.appendChild(circle);

    var MAX_R = 110;
    var DURATION = 420;
    var start = null;
    function step(timestamp) {
      if (!start) { start = timestamp; }
      var progress = Math.min((timestamp - start) / DURATION, 1);
      var eased = 1 - Math.pow(1 - progress, 3);
      circle.setAttribute('r', (MAX_R * eased).toFixed(1));
      circle.setAttribute('fill-opacity', (0.28 * (1 - progress)).toFixed(3));
      if (progress < 1) { global.requestAnimationFrame(step); } else { circle.remove(); }
    }
    global.requestAnimationFrame(step);
  }

  function showSeatLabel(svg, polygon) {
    var label = svg.querySelector('.arena-seat-label');
    if (!label) { return; }
    var box = polygon.getBBox();
    label.setAttribute('x', (box.x + box.width / 2).toFixed(2));
    label.setAttribute('y', (box.y + box.height / 2).toFixed(2));
    // Long copy in a small tile would spill over its neighbours; the outer
    // galleries are roomy enough for words, the inner rank rings are not.
    label.setAttribute('font-size', Math.min(9, Math.max(4, box.width * 0.16)).toFixed(1));
    label.removeAttribute('hidden');
  }

  function hideSeatLabel(svg) {
    var label = svg.querySelector('.arena-seat-label');
    if (label) { label.setAttribute('hidden', 'hidden'); }
  }

  function attachEvents(svg) {
    var tip = tooltipEl();
    var close = tip && tip.querySelector('.arena-tooltip__close');
    if (close) {
      close.addEventListener('click', function (event) {
        event.preventDefault();
        event.stopPropagation();
        hideTooltip();
      });
    }

    svg.addEventListener('mouseover', function (event) {
      var seat = event.target.closest && event.target.closest('.arena-cell[data-seatable]');
      if (seat) { showSeatLabel(svg, seat); } else { hideSeatLabel(svg); }
    });
    svg.addEventListener('mouseleave', function () { hideSeatLabel(svg); });

    // The card is position:fixed, but fixed is relative to the nearest
    // TRANSFORMED ancestor — and the card ships inside .arena-floor-stage, which
    // carries the camera. That is why it opened on the other side of the floor:
    // a computed top of 320px was drawn at 494. Lifting it to <body> makes fixed
    // mean fixed, and the card lands beside the chef. Measured on production
    // before and after, not guessed.
    var tipNode = tooltipEl();
    if (tipNode && tipNode.parentElement !== document.body) {
      document.body.appendChild(tipNode);
    }

    // Bound to the CONTAINER, not the svg. Measured on production 2026-07-30:
    // over every chef on the floor, document.elementFromPoint returns the
    // container, never the cell — the floor is an SVG under the rotateX(42deg)
    // camera, and its hit area does not sit where its pixels are drawn. A
    // listener on the svg therefore never fired for a click aimed at a chef.
    // Clicks that DO land on the svg still bubble up here, so nothing is lost.
    svg.parentElement.addEventListener('click', function (event) {
      // T-AUDIT, 2026-08-15, section 2c (Owner, 2026-08-06): "a click on the
      // centre takes every spectator off the arena and onto the battle's own
      // page... the popup is a placeholder, and the target is a page." The
      // page (battle_broadcast) shipped as B01-B03/R01-R02 weeks ago; this
      // click never stopped opening the popup instead, so five finished
      // cards had no way in except typing the URL by hand. battle_url is
      // "the link the centre cell carries" (views.py, _arena_center) - so
      // that is what a click on the centre now follows, with the same
      // ripple feedback the popup click always gave.
      var stage = event.target.closest && event.target.closest('[data-arena-stage]');
      if (stage && stageCentre && stageCentre.battle_url) {
        event.stopPropagation();
        fireRipple(svg, stage);
        // The 150ms lets the ripple be seen before the browser leaves. It is a
        // post-click flourish, NOT a readiness gate - nothing waits on this
        // clock for something to become ready, which is the rule the two timer
        // guards exist to keep. Bolt renamed and sharpened both of them in
        // T11 so they name the timers they allow instead of counting; I had
        // briefly deleted this line to satisfy the old blunt count, which
        // would have thrown away his work to save 150ms nobody asked me to.
        var destination = stageCentre.battle_url;
        global.setTimeout(function () { global.location.href = destination; }, 150);
        return;
      }
      // Owner 2026-08-03: every VIP box answers a click, sold or not. A sold one
      // goes to its sponsor — that visit is what the box was bought for — and a
      // free one goes to the page where it can be bought. Handled here rather
      // than on a listener of its own: one interactive behaviour, one event
      // owner (TECHNICAL_STANDARDS 6).
      var vipBox = event.target.closest && event.target.closest('.arena-cell--vip');
      if (vipBox) {
        event.stopPropagation();
        fireRipple(svg, vipBox);
        if (vipBox.sponsorRecord) {
          // A sold box opens the same card a chef opens, carrying the sponsor.
          // The link lives ON the card (Owner, 2026-08-03) rather than the click
          // throwing the viewer straight off the site.
          showSponsorTooltip(vipBox.sponsorRecord, vipBox);
        } else {
          hideTooltip();
          global.location.href = '/sponsors/';
        }
        return;
      }

      var seat = event.target.closest && event.target.closest('.arena-cell[data-ring]');
      if (!seat || !seat.chefRecord) {
        // Fall back to what the viewer actually aimed at: the portrait's own
        // on-screen box. getBoundingClientRect is the browser's own answer for
        // where that portrait is, so this holds whatever the camera does to the
        // geometry underneath it.
        var portraits = svg.querySelectorAll('.arena-occupant[data-entity-slug]');
        var picked = null;
        var pickedArea = Infinity;
        for (var i = 0; i < portraits.length; i++) {
          var box = portraits[i].getBoundingClientRect();
          if (!box.width || !box.height) { continue; }
          if (event.clientX < box.left || event.clientX > box.right) { continue; }
          if (event.clientY < box.top || event.clientY > box.bottom) { continue; }
          var area = box.width * box.height;
          // Smallest box wins, so two overlapping portraits resolve to the one
          // the click is most precisely inside rather than to draw order.
          if (area < pickedArea) { pickedArea = area; picked = portraits[i]; }
        }
        if (picked) {
          seat = svg.querySelector(
            '.arena-cell[data-entity-slug="' + picked.getAttribute('data-entity-slug') + '"]'
          );
        }
      }
      if (!seat || !seat.chefRecord) { hideTooltip(); return; }
      event.stopPropagation();
      fireRipple(svg, seat);
      showTooltip(seat.chefRecord, seat);
    });
    document.addEventListener('click', function (event) {
      var tip = tooltipEl();
      if (!tip || tip.hidden) { return; }
      if (!tip.contains(event.target) && !event.target.closest('#arena-render')) { hideTooltip(); }
    });
  }

  /* ---------------------------------------------------------------- */
  /* Live wiring                                                       */
  /* ---------------------------------------------------------------- */

  function csrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function post(url) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken() }
    });
  }

  /**
   * The poll URL carries ?demo=vs when the page was opened with it, and the
   * geometry_version we last saw (AA1) so the server can skip resending the
   * geometry payload when nothing about it has changed.
   *
   * The poll is a POST to a bare path, so the server could not see the query
   * string the page was rendered with — it answered with the real centre and
   * wiped the preview on the first tick. The flag is only ever honoured for a
   * moderator, server-side; passing it here grants nothing. geometry_version
   * rides the same query string rather than a request body: this endpoint's
   * own post() sends no body today, and request.GET is the established
   * precedent this same view already reads the demo flag from.
   */
  function stateUrl() {
    var base = '/chef-battle/arena/state/';
    var params = [];
    var flag = /(^|[?&])demo=(vs|next)(&|$)/.exec(global.location.search);
    if (flag) { params.push('demo=' + flag[2]); }
    if (lastGeometryVersion) {
      params.push('geometry_version=' + encodeURIComponent(lastGeometryVersion));
    }
    return params.length ? base + '?' + params.join('&') : base;
  }

  function poll(svg) {
    post(stateUrl())
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (payload) {
        if (!payload) { return; }
        if (payload.geometry_version) { lastGeometryVersion = payload.geometry_version; }
        // Geometry is re-read only when the server actually sent it: AA1
        // omits the key entirely once the client's reported version matches,
        // so "geometry present" already means "geometry changed."
        if (payload.geometry) { bind(svg, payload, payload.geometry); fitScene(svg); }
        if (global.ArenaDeck) { global.ArenaDeck.refresh(payload); }
        paintRunway(payload.runway || null);
        if (global.ArenaBattleRoom) { global.ArenaBattleRoom.maybeCelebrate(payload.latest_result); }
      })
      .catch(function () { /* a dropped poll is retried on the next tick */ });
  }

  // Fit the tilted scene inside its frame (G4).
  //
  // rotateX(56deg) alone is a parallel projection: vertical compression is
  // cos(56) at every viewport. Measure PROJECTED STANDS (not the rank floor):
  // stands sit at 1.60× floor radius, so fitting the floor left them sticking
  // out by construction. Floor span 0.63 is an OUTPUT to verify, not the fit
  // target. Two measure/scale passes land under 1px of drift.
  /**
   * Ask the page for its own measurement. AN15 moved the number, the formula
   * and its four triggers into ArenaPageLayout - `static/js/arena_page_layout.js`,
   * which carries the two production faults that shaped them. This wrapper is
   * all the octagon keeps: it needs the deck's height to be current before it
   * announces the shell, and it does not care who measured it.
   *
   * Returns true when the value CHANGED, so a caller can skip a re-fit it does
   * not need - fitScene is a two-pass measure-and-scale and is not free.
   */
  function measureHeader() {
    return global.ArenaPageLayout ? global.ArenaPageLayout.measure() : false;
  }

  // ============================================================
  // THE ARENA'S READINESS LIFECYCLE
  // ============================================================
  //
  // OWNER, 2026-08-08: on a cold load the rank ladder is visible in the CENTRE
  // of the page before the octagon exists, and jumps right once it renders.
  //
  // Measured before this existed: one layout shift at 943ms, CLS 0.0255, the
  // rank spine travelling 441px right and 102px down - from the position its
  // stylesheet gives it to the position placeRankSpine() writes. The element
  // was painted in a place nobody intended, because nothing said it was too
  // early to paint it.
  //
  // NOT SOLVED WITH TIME. No setTimeout, no animation-delay, no "hide it for
  // 500ms". A timing constant is a guess about a machine we do not own, and it
  // is wrong on the machine that is slower than the guess. What is missing is
  // not a delay but a STATE: the page knows whether the geometry the ladder
  // depends on exists yet, and geometry-dependent furniture is painted only
  // once it does.
  //
  //   boot        the script has run, nothing is measured
  //   shell       the page's own furniture is laid out and correct
  //   geometry    the octagon is drawn and its cells have real boxes
  //   scene       everything measured off that geometry has been placed
  //   interactive polling and events are attached
  //
  // The state is one attribute on the deck. CSS hides what depends on geometry
  // until "scene", and nothing anywhere waits on a clock.
  var ARENA_STATES = ['boot', 'shell', 'geometry', 'scene', 'interactive'];

  function arenaStateNode() {
    return document.querySelector('.arena-command-deck') || document.body;
  }

  function arenaState(next) {
    var node = arenaStateNode();
    if (!node) { return 'boot'; }
    var now = node.getAttribute('data-arena-state') || 'boot';
    if (!next) { return now; }
    // The lifecycle only ever moves forward. A late resize must not drop the
    // page back to "geometry" and blink the furniture the user is looking at.
    if (ARENA_STATES.indexOf(next) <= ARENA_STATES.indexOf(now)) { return now; }
    node.setAttribute('data-arena-state', next);
    return next;
  }

  // The octagon is real when its cells have boxes. Asking the DOM whether the
  // nodes EXIST is not the same question: they exist before layout has given
  // them a size, and a ladder measured against a zero-width floor lands in the
  // same wrong place it used to.
  function geometryIsValid(svg) {
    if (!svg) { return false; }
    var cell = svg.querySelector('.arena-cell');
    if (!cell) { return false; }
    var box = cell.getBoundingClientRect();
    return box.width > 0 && box.height > 0;
  }

  function fitScene(svg) {
    // The SVG's parent is the CAMERA VIEWPORT, and the viewport's parent is
    // the page region. Naming it says which is which: this file places the
    // camera in the region, and never the other way round.
    var camera = svg.parentElement;
    if (!camera) { return; }
    if (!geometryIsValid(svg)) { return; }
    arenaState('geometry');

    placeOctagon(svg, camera);

    placeRankSpine(svg);
    paintRankLadder(svg);
    // Everything measured off the octagon now holds a real position, so the
    // furniture may be shown. This is the only line that reveals it, and it is
    // reached by having done the work rather than by having waited.
    arenaState('scene');
  }
  // ============================================================
  // THE CAPTION IS NOT PLACED BY THIS FILE ANY MORE.
  //
  // AN-R1/B, 2026-08-09, on the Owner's choice between two designs.
  //
  // What stood here - placeFloorCaption() and reserveCaptionBand() - solved a
  // real problem the wrong way round. His words on 2026-08-07: "блоки опять
  // наезжают друг на друга - мы уже чинили это сегодня - исправь это раз и
  // навсегда." The caption used to sit at `top: 8.2%` of the floor, a fixed
  // share of a box whose contents are not fixed; on his window that share put
  // it at 234 while the ribbon above ran to 255 and the octagon began at 277 -
  // a 50px caption in a 22px gap, overlapping both and the metrics panel too.
  //
  // The answer then was to measure the three edges that bound it and place it
  // in what was left, and, when what was left was too short, to scale and
  // shift the OCTAGON through the camera until it fitted. That worked, and it
  // made the caption a second owner of the octagon's position.
  //
  // The band is layout now. `.arena-command-deck__floor` is three rows - what
  // the furniture above occupies, the writing, and the floor - so the caption
  // receives a region instead of taking one, and it cannot overlap the octagon
  // because they are in different rows. Nothing in this file writes the
  // caption's top, left or width, and nothing in this file needs to know how
  // tall it is.
  //
  // The rule it used to enforce by shedding lines is now enforced by the grid:
  // row two takes exactly the height the writing needs, and row three - the
  // octagon - gets what is left.
  // ============================================================

  // THE LADDER WEARS ITS RINGS' OWN COLOURS. Owner, 2026-08-07.
  //
  // The colour is READ OFF THE FLOOR rather than restated beside it. Three
  // sheets had an opinion about a rank ring's fill - the renderer named the
  // tokens, arena_deck_polish.css repeated them as literals under a heavier
  // selector, arena_atmosphere.css won with !important - and a fourth list,
  // written here, would be a fourth thing to keep in step. Two of those files
  // are gone since AN12 and AN13, and the argument is the same: whatever the
  // ring ACTUALLY paints, the rung takes.
  //
  // Rings 7 and 8 (Prep Chef, Kitchen Porter) come back the same colour,
  // because the floor paints them the same colour: there are six ramp tokens
  // for eight ranks. The Owner ruled on 2026-08-07 to leave it truthful rather
  // than invent two shades - the ladder is a key to the floor, and a key that
  // separates what the floor joins is a lie about the floor.
  // ============================================================

  /** The octagon's own rendered box - the thing the region has to hold. */
  function elementBox(svg) {
    var b = svg.getBoundingClientRect();
    if (!(b.width > 0) || !(b.height > 0)) { return null; }
    return { left: b.left, right: b.right, top: b.top, bottom: b.bottom,
             width: b.width, height: b.height,
             cx: b.left + b.width / 2, cy: b.top + b.height / 2 };
  }

  /**
   * Place the COMPLETE camera component inside its page region.
   *
   * Nothing here reaches into the camera. The three properties written are
   * the component's own placement - a uniform scale and a translation in
   * screen pixels, both applied OUTSIDE the perspective - so the projection
   * they carry is the one the camera already produced, magnified and moved.
   */
  function writePlacement(camera, scale, x, y) {
    camera.style.setProperty('--arena-camera-scale', scale.toFixed(5));
    camera.style.setProperty('--arena-camera-x', x.toFixed(2) + 'px');
    camera.style.setProperty('--arena-camera-y', y.toFixed(2) + 'px');
  }

  function placeOctagon(svg, camera) {
    // ============================================================
    // THE OCTAGON'S LAYOUT OWNER - Owner's correction of 2026-08-09.
    //
    // The chain, and the boundary that had been missing:
    //
    //     page layout      allocates the region
    //           |
    //     THIS FUNCTION    scales and moves the COMPLETE camera component
    //           |          into that region
    //     the camera       projects, and knows nothing above it
    //
    // What it used to do instead was reach through the camera. It wrote
    // --arena-fit and --arena-shift-* on the SVG, INSIDE rotateX(42deg)
    // under a 1500px perspective, which is why it needed a probe and two
    // refinements: a translation asked for in CSS pixels does not arrive on
    // the screen at that size, and a scale under a perspective does not grow
    // the box linearly. Every one of those passes was the code apologising
    // for having crossed a boundary it should not have crossed.
    //
    // The camera now has its own viewport with its own intrinsic side (see
    // --arena-camera-side in arena.css), so the projection no longer depends
    // on the height of whatever box the page happened to give it. Placement
    // is a plain 2D scale and translate on that viewport, which is affine,
    // which is why the solve below is exact: two writes and one measurement,
    // no probe, no refinement loop, no accumulation.
    //
    // A page that provides no camera viewport - the Master Console mirror,
    // which carries `page--arena` on a completely different shell - gets
    // nothing written by this function. It is not a second layout path; it
    // is the precondition of this one not being met.
    // ============================================================
    if (!camera || !camera.parentElement) { return; }
    if (!global.getComputedStyle(camera)
               .getPropertyValue('--arena-camera-side').trim()) {
      return;
    }
    var region = camera.parentElement.getBoundingClientRect();
    if (!(region.width > 0) || !(region.height > 0)) { return; }

    // A KNOWN BASE, so the answer cannot depend on what the last pass left.
    writePlacement(camera, 1, 0, 0);
    var natural = elementBox(svg);
    if (!natural || !(natural.width > 0) || !(natural.height > 0)) { return; }

    // THE SIZE. One division, because the scale is outside the projection.
    var scale = region.width * OCTAGON_VISUAL_WIDTH_SHARE / natural.width;
    // The ceiling, applied to the same known base rather than to a result.
    if (natural.height * scale > region.height * REGION_MAX_Y) {
      scale = region.height * REGION_MAX_Y / natural.height;
    }

    // THE POSITION. Measured once at the chosen scale, then corrected once.
    // The correction is exact: the translation is applied after the scale and
    // in screen pixels, so what is asked for is what arrives.
    writePlacement(camera, scale, 0, 0);
    var sized = elementBox(svg);
    if (!sized) { writePlacement(camera, 1, 0, 0); return; }
    var targetX = region.left + region.width * OCTAGON_VISUAL_CENTRE_X;
    var targetY = region.top + region.height * OCTAGON_VISUAL_CENTRE_Y;
    writePlacement(camera, scale, targetX - sized.cx, targetY - sized.cy);
  }

  function paintRankLadder(svg) {
    var steps = document.querySelectorAll('.arena-rank-spine__step[data-ring]');
    for (var i = 0; i < steps.length; i++) {
      var ring = steps[i].getAttribute('data-ring');
      var cell = svg.querySelector(
        '.arena-cell[data-ring-kind="rank"][data-ring="' + ring + '"]'
      );
      if (!cell) { continue; }
      var fill = global.getComputedStyle(cell).fill;
      if (!fill || fill === 'none') { continue; }
      steps[i].style.background = fill;
      // Ink or light, decided by the colour itself. The ramp runs from #52422e
      // to near-white, so one fixed text colour is unreadable at one end of it
      // whichever end is chosen. sRGB relative luminance, and the 0.55 line is
      // where the ramp's own middle step falls.
      var rgb = fill.match(/\d+(\.\d+)?/g);
      if (!rgb || rgb.length < 3) { continue; }
      var lum = (0.2126 * rgb[0] + 0.7152 * rgb[1] + 0.0722 * rgb[2]) / 255;
      // The chip needs this for its ink and its lift. The ITEM behind it, which
      // draws the rim, deliberately does not: the Owner ruled on 2026-08-07
      // that all eight rims are one colour, so nothing there varies with the
      // fill and the attribute was stamped on it for nobody.
      steps[i].setAttribute('data-on-dark', lum < 0.55 ? 'true' : 'false');
    }
  }

  // 3G R4 (Owner D1 Option B): desktop centred stack is CSS-owned
  // (left:50% + translateX), matching Ember rank-progression composition.
  // Below 768px the ladder is a wrapped flow row (Stage 3E). Tablet mid-band
  // may still measure against the floor so the stack sits between the near
  // edge and the crown without covering it.
  function placeRankSpine(svg) {
    var spine = document.querySelector('.arena-rank-spine');
    var camera = svg.parentElement;
    if (!spine || !camera) { return; }
    // THE FRAME IS THE PAGE REGION, NOT THE CAMERA.
    //
    // AN-R2/2, 2026-08-09. This read `svg.parentElement` and called it the
    // frame, which was true only while the camera viewport happened to be
    // stretched over the whole region. Now that the viewport has an
    // intrinsic side of its own, the ladder measured itself against a
    // 284px box and landed at x=204 instead of 935. The ladder stands
    // beside the octagon INSIDE the octagon's region; the region is the
    // element that says how much room there is, and it is also the ladder's
    // own offset parent, which is what its top and left are relative to.
    var container = spine.offsetParent || camera.parentElement || camera;

    // Below 767 the arena is untouched by the Owner's own instruction of
    // 2026-08-03, so CSS keeps layout there and nothing is measured.
    if (window.matchMedia && window.matchMedia('(max-width: 767px)').matches) {
      spine.style.top = '';
      spine.style.left = '';
      spine.style.width = '';
      spine.style.transform = '';
      return;
    }

    // AN16: the ranks' own box, from the octagon rather than from its cells.
    var ranks = global.ArenaOctagon && global.ArenaOctagon.rankRegion(svg);
    if (!ranks) { return; }
    var top = ranks.top, bottom = ranks.bottom, right = ranks.right;

    var frame = container.getBoundingClientRect();
    var floorH = bottom - top;

    // THE LADDER STANDS BESIDE THE OCTAGON, NOT ON IT.
    //
    // OWNER, 2026-08-07: "убери лестницу рангов с октагона совсем - пусть
    // стоит справа от октагона по центру."
    //
    // Everything before this tried to fit the stack into the band ABOVE the
    // floor: the reference's 0.1995-of-floor-height offset, then a rule to sit
    // directly above the floor's top edge when that offset would land inside
    // the octagon, then a shrink when even that band was too thin. On a short
    // deck the band ran out, the offset clamped to zero, and the stack ended up
    // at the very top of the deck standing on the floor caption - four text
    // blocks in one strip, which is the pile he photographed.
    //
    // There is no band to fight over now. The stack sits to the RIGHT of the
    // floor and is centred on the floor's own vertical middle, where the space
    // is horizontal and there is far more of it.
    var GAP = 16;
    // CSS defines one centimetre as exactly 96/2.54 px, so this is the Owner's
    // centimetre and not an approximation of it.
    var ONE_CM = 96 / 2.54;
    var ladderBox = spine.getBoundingClientRect();
    var ladderH = ladderBox.height;
    var ladderW = ladderBox.width;

    // Horizontal: just clear of the floor's right edge, plus the Owner's
    // centimetre (2026-08-07: "отодвинь вправо на 1 см"), and never past the
    // frame. If the room to the right is narrower than the stack, it is pulled
    // back to the frame's edge rather than allowed to leave the deck.
    var x = right - frame.left + GAP + ONE_CM;
    if (x + ladderW > frame.width) { x = frame.width - ladderW; }
    if (x < 0) { x = 0; }

    // Vertical: THE SPONSORS CORNER LANDS BETWEEN CHEF DE PARTIE AND SOUS CHEF.
    //
    // OWNER, 2026-08-07: "подними лестницу рангов выше так, чтоб угол ячейки
    // Sponsors - был ровно между Chef de Partie и Sous Chef."
    //
    // Two corrections in one, and the first is why the second was needed. The
    // corner he names is NOT the middle of the floor's bounding box: the camera
    // is rotateX(42deg), so the far half of the octagon is compressed and the
    // box's centre sits BELOW the right-hand vertex - measured 439 against 423
    // at his own window, sixteen pixels of it. Centring the stack on the box,
    // which is what shipped in v2.5.876, therefore hangs it below the corner.
    // The anchor is the rightmost VIP (Sponsors) cell's own vertical middle,
    // which IS that vertex, with the rank box kept only as a fallback.
    var corner = global.ArenaOctagon && global.ArenaOctagon.sponsorsCorner(svg);
    var vertexY = corner ? corner.y : (top + bottom) / 2;

    // And the stack is hung by the seam between its fourth and fifth rungs
    // rather than by its own middle. With eight rungs the two are the same
    // number today; they stop being the same the moment a rank is added or the
    // label above the list is given a height, and his instruction names the
    // seam, not the middle.
    var seam = ladderH / 2;
    var rungs = spine.querySelectorAll('.arena-rank-spine__list > *');
    if (rungs.length >= 5) {
      var above = rungs[3].getBoundingClientRect();
      var below = rungs[4].getBoundingClientRect();
      seam = (above.bottom + below.top) / 2 - ladderBox.top;
    }

    var y = vertexY - frame.top - seam;
    if (y + ladderH > frame.height) { y = frame.height - ladderH; }
    if (y < 0) { y = 0; }

    // And it shrinks rather than overflowing, on the same floor of 0.85 the
    // vertical band used: below that it is the Owner's call whether to
    // abbreviate the titles, not an agent's to decide by shrinking type.
    var scale = 1;
    if (ladderH > frame.height) { scale = frame.height / ladderH; }
    if (scale < 0.85) { scale = 0.85; }

    spine.style.transformOrigin = 'top left';
    spine.style.transform = scale < 1 ? 'scale(' + scale.toFixed(3) + ')' : 'none';
    // WHOLE PIXELS. Owner, 2026-08-07: the rungs look like different heights
    // and the type inside them sits at different levels. Measured: they are
    // identical to the hundredth - 21.59px each, text centred with zero offset,
    // no rotation and no skew anywhere above them. What differs is where each
    // one LANDS: a fractional top puts every rung on a different subpixel, so
    // the browser renders one 1px rim as 1px and the next as 2px and rasterises
    // the type against a different grid each time. Rounding here, and an
    // integer row pitch in the stylesheet, put every edge on a device pixel.
    spine.style.top = Math.round(y) + 'px';
    spine.style.left = Math.round(x) + 'px';
    // WIDTH IS NOT SET HERE. It was 0.1253 of the floor - the reference's own
    // share - and at his window that clipped CULINARY MASTER and EXECUTIVE CHEF
    // mid-word, because the reference's share is a consequence of ITS type size
    // and ours is larger. The stylesheet sizes the stack by its content, which
    // is what a nowrap chip needs.
    spine.style.width = '';
  }




  function init() {
    var svg = document.getElementById('arena-render');
    var node = document.getElementById('arena-data-json');
    if (!svg || !node || !global.ArenaGeometry) { return; }

    var payload;
    try { payload = JSON.parse(node.textContent); } catch (error) { return; }
    var geometry = payload && payload.geometry;
    if (!geometry || !Array.isArray(geometry.rings) || !geometry.rings.length) { return; }
    lastGeometryVersion = payload.geometry_version || null;

    drawGrid(svg, geometry);
    bind(svg, payload, geometry);
    attachEvents(svg);
    // THE SHELL IS NOT READY UNTIL THE HEADER HAS BEEN MEASURED.
    //
    // The deck is `calc(100svh - var(--arena-header-h, 146px))`, and 146 is the
    // desktop header. Measured on production at 1170x820 the real header is 172,
    // so the first paint gave the deck 26px too much and measureHeader() then
    // took it back: one layout shift at 981ms, CLS 0.0111, with the crowd rail,
    // the gifts card, the crown ladder, the metrics and the whole SVG sliding up
    // together. Nothing was wrong with any of them - they were correct twice, at
    // two different heights.
    //
    // measureHeader() runs BEFORE the shell is announced now, so the deck is not
    // painted at a height that is about to change. This is the same rule the
    // ladder got: an element appears when the number it depends on is known.
    measureHeader();
    arenaState('shell');
    fitScene(svg);
    arenaState('interactive');
    // THE OBSERVER WATCHES THE REGION, NOT THE CAMERA.
    //
    // AN-R2/3, 2026-08-09, found by the lifecycle audit and not by a test.
    // This observed `svg.parentElement` - which used to be the camera
    // viewport stretched over the page region, so watching it WAS watching
    // the region. The viewport has an intrinsic 440px side now and its box
    // never changes, so the observer had quietly become one that can never
    // fire. A trigger that cannot fire is worse than one that is missing:
    // it reads as covered.
    //
    // The box that actually varies is the REGION, one level up, and it is
    // still exactly one ResizeObserver in this file.
    var region = svg.parentElement && svg.parentElement.parentElement;
    if (global.ResizeObserver && region) {
      new global.ResizeObserver(function () { fitScene(svg); }).observe(region);
    }
    // AN15, master task section 9: the page owns its own layout and the
    // octagon re-fits inside whatever it is handed. The four triggers that can
    // move the deck - the site header's own box, the window, the moment the
    // fonts settle, and one late pass - live in ArenaPageLayout now. This
    // renderer no longer knows the site has a header.
    //
    // `force` is a window resize or the late pass: re-fit even when the
    // header's number held, because the FRAME changed under a scene that was
    // already measured. Without it, measured on production at 1280x520, the
    // ladder hung 19px below the fold and 133px off the floor's centre line -
    // a change of window HEIGHT never touches the header, so nothing asked the
    // scene to measure itself again.
    if (global.ArenaPageLayout) {
      global.ArenaPageLayout.subscribe(function (changed, force) {
        if (changed || force) { fitScene(svg); }
      });
      global.ArenaPageLayout.watch();
    }
    if (global.ArenaDeck) { global.ArenaDeck.refresh(payload); }
    paintRunway(payload.runway || null);
    if (global.ArenaBattleRoom) { global.ArenaBattleRoom.init(payload.latest_result); }

    pollTimer = global.setInterval(function () { poll(svg); }, POLL_INTERVAL);
    arenaSvg = svg;
    pingTimer = global.setInterval(function () { post('/chef-battle/arena/ping/').catch(function () {}); }, PING_INTERVAL);

    // AA1: a hidden tab issues no polls. This pauses only the state poll,
    // not pingTimer — the presence ping is what keeps THIS viewer visible to
    // everyone else's screen, and stopping it too on a merely-backgrounded
    // tab would make a chef vanish from other people's arenas, a bigger and
    // different change than "stop re-fetching a 30KB payload nobody's
    // looking at." Resumes at the runway's own faster cadence if one is
    // active, matching paintRunway's own swap logic.
    if (global.document && typeof global.document.addEventListener === 'function') {
      global.document.addEventListener('visibilitychange', function () {
        if (global.document.hidden) {
          if (pollTimer) { global.clearInterval(pollTimer); pollTimer = null; }
        } else if (arenaSvg && !pollTimer) {
          poll(arenaSvg);
          pollTimer = global.setInterval(function () { poll(arenaSvg); }, runwayPollMs || POLL_INTERVAL);
        }
      });
    }
  }

  /**
   * Repaint everything the lamp layout touches, and nothing else. The crown
   * lamps live in the centre layer, which stampFloorCentre already rebuilds from
   * scratch; the moat lanterns live in the cell grid, so they are moved in place
   * rather than redrawing 200 floor tiles for two circles each.
   */
  /* ── The runway: countdown, pace, and one line of narration ─────────────
   * OWNER, 2026-08-06: "перед началом эмуляции выводи на живую арену - 3 - 2 -
   * 1 - и поехали, с шагом в 5 секунд".
   *
   * The server does NOT send the digits. It sends the moment the run begins,
   * once, and this counts down to it off the browser's own clock - three ticks
   * cannot be delivered by a ten-second poll, and a watcher who arrives late
   * must see the right number rather than a stale one.
   *
   * And while a run is live the poll speeds up, because a five-second step seen
   * through a ten-second poll is a step the Owner is TOLD about and never
   * watches. The arena drops back to ten seconds the moment the server stops
   * sending a runway - the fast cadence cannot outlive the run.
   */
  var arenaSvg = null;
  var runwayTimer = null;
  var runwayPollMs = null;

  function runwayLayer() {
    var el = document.getElementById('arena-runway');
    if (el) { return el; }
    // THE RUNWAY IS PAGE FURNITURE, NOT PART OF THE CAMERA.
    //
    // AN-R2/3: it used to be appended to `.arena-render-container`, which
    // was the whole region. That element is the camera viewport now - 440px
    // square and carrying the placement scale - so the countdown would have
    // been shrunk and moved by the octagon's fit. It belongs to the region,
    // which is the box it was always positioned against.
    var host = document.querySelector('.arena-floor-stage')
      || document.querySelector('.arena-command-deck__floor')
      || document.body;
    el = document.createElement('div');
    el.id = 'arena-runway';
    el.className = 'arena-runway';
    el.setAttribute('aria-live', 'assertive');
    host.appendChild(el);
    return el;
  }

  function paintRunway(runway) {
    var layer = runwayLayer();

    if (!runway) {
      layer.className = 'arena-runway';
      layer.textContent = '';
      if (runwayTimer) { global.clearInterval(runwayTimer); runwayTimer = null; }
      if (runwayPollMs !== null) {
        // Back to the ordinary cadence.
        runwayPollMs = null;
        if (pollTimer) { global.clearInterval(pollTimer); }
        pollTimer = global.setInterval(function () { poll(arenaSvg); }, POLL_INTERVAL);
      }
      return;
    }

    var wanted = Number(runway.poll_ms) || POLL_INTERVAL;
    if (wanted !== runwayPollMs) {
      runwayPollMs = wanted;
      if (pollTimer) { global.clearInterval(pollTimer); }
      pollTimer = global.setInterval(function () { poll(arenaSvg); }, wanted);
    }

    var startsAt = runway.starts_at ? new Date(runway.starts_at).getTime() : 0;
    var countFrom = Number(runway.count_from) || 3;

    function tick() {
      var left = Math.ceil((startsAt - Date.now()) / 1000);
      if (left > countFrom) {
        // Armed but not counting yet: say nothing, show nothing.
        layer.className = 'arena-runway';
        layer.textContent = '';
        return;
      }
      if (left > 0) {
        layer.className = 'arena-runway is-counting';
        layer.textContent = String(left);
        return;
      }
      if (left > -3) {
        layer.className = 'arena-runway is-go';
        layer.textContent = runway.label || 'GO';
        return;
      }
      // The off has passed: the digits give way to whatever the run is saying.
      if (runway.note) {
        layer.className = 'arena-runway is-note';
        layer.textContent = runway.note;
      } else {
        layer.className = 'arena-runway';
        layer.textContent = '';
      }
    }

    if (runwayTimer) { global.clearInterval(runwayTimer); }
    tick();
    runwayTimer = global.setInterval(tick, 250);
  }

  function applyLampLayout() {
    var svg = document.getElementById('arena-render');
    if (!svg) { return; }

    if (stageCentre) { stampFloorCentre(svg, stageCentre); }

    var set = lampLayout().moat;
    var lamps = svg.querySelectorAll('.arena-lantern');
    for (var i = 0; i < lamps.length; i++) {
      var a = i * Math.PI / 4 + set.deg * Math.PI / 180;
      var r = STAGE_RADIUS * set.r;
      var x = (TPL_CX + r * Math.cos(a)).toFixed(2);
      var y = (TPL_CY + r * Math.sin(a)).toFixed(2);
      lamps[i].setAttribute('cx', x);
      lamps[i].setAttribute('cy', y);

      // The three strobe rings ride with their lamp, pivot included — a ring
      // left behind would grow out of a place with no lamp in it.
      var rings = svg.querySelectorAll('.arena-lamp-strobe');
      for (var s = 0; s < STROBE_RINGS.length; s++) {
        var ring = rings[i * STROBE_RINGS.length + s];
        if (!ring) { continue; }
        ring.setAttribute('cx', x);
        ring.setAttribute('cy', y);
        ring.setAttribute('style', 'transform-origin: ' + x + 'px ' + y + 'px');
      }
    }
  }

  global.ArenaRender = {
    init: init,
    buildAssignments: buildAssignments,
    isDisplaced: isDisplaced,
    applyLampLayout: applyLampLayout,
    lampDefaults: LAMP_DEFAULTS
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
