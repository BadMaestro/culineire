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
  var COMPOSITION_CX = 0.50;
  var COMPOSITION_CY = 0.51;
  // The site header the deck's height is measured against — see measureHeader().
  var HEADER_SELECTOR = '.ce-header';
  // A09: clear floor between the crown block and a fighter block, as a fraction
  // of the floor's width. Measured off the reference — see fighterOffset().
  var REFERENCE_FIGHTER_GAP = 0.044153;

  var pollTimer = null;
  var pingTimer = null;
  // Latest centre payload, so a stage click knows which battle room to open.
  var stageCentre = null;
  // Ring the viewer currently occupies, or null while they are off the floor.
  var seatedRing = null;
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
    var standsOuter = Math.min(520, floorOuter + 48);
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

  // Owner 2026-07-24: spectators sit in an oval around the chef octagon
  // (3 rows L/R, 2 rows T/B) — not in floor cells.
  // Prefer BE spectator_oval.seats (centre-relative) so ring/cell ids match
  // ArenaSeat; scale them onto the drawn floor outer radius.
  function drawSpectatorOval(svg, geometry, step, defs) {
    var project = projector();
    var layer = el('g', { 'data-arena-layer': 'spectator-oval' });
    var props = g1Radii(geometry);
    var floorR = props.floorOuter;
    var standsOuter = props.standsOuter;
    var oval = geometry.spectator_oval || {};
    // The backend owns the stable seat contract. Keep its ring/cell ids intact;
    // the fallback mirrors ArenaGeometry's AR4 layout — two rows top, two
    // bottom, 114 author seats. The left and right banks are gone (§2a).
    var rowsBySide = oval.rows_by_side || { top: 2, bottom: 2 };
    var countsBySide = oval.counts_by_side || {
      top: [28, 29],
      bottom: [28, 29]
    };
    var beFloor = oval.floor_outer_radius || 220;
    var seats = (Array.isArray(oval.seats) && oval.seats.length)
      ? oval.seats
      : (global.ArenaGeometry.ovalSeats
        ? global.ArenaGeometry.ovalSeats(0, 0, beFloor, rowsBySide, Math.max(8, beFloor * 0.032), countsBySide)
        : []);

    // Remap radial depth so outermost seat CENTRE sits at STANDS_RATIO
    // (G5: ~1.46 so bbox ≈ 1.60). Angle preserved.
    var maxBe = beFloor;
    seats.forEach(function (seat) {
      var rb = Math.hypot(seat.x || 0, seat.y || 0);
      if (rb > maxBe) { maxBe = rb; }
    });
    var depthBe = Math.max(1e-6, maxBe - beFloor);
    var depthSvg = standsOuter - floorR;

    seats.forEach(function (seat) {
      var rBe = Math.hypot(seat.x || 0, seat.y || 0);
      var ang = Math.atan2(seat.y || 0, seat.x || 0);
      var rSvg;
      if (rBe <= beFloor) {
        rSvg = rBe * (floorR / beFloor);
      } else {
        rSvg = floorR + ((rBe - beFloor) / depthBe) * depthSvg;
      }
      var planX = TPL_CX + Math.cos(ang) * rSvg;
      var planY = TPL_CY + Math.sin(ang) * rSvg;
      var pt = project({ x: planX, y: planY });
      var pitch = Math.max(8, floorR * 0.032);
      var depth = (seat.row || 0) / Math.max(1, (rowsBySide[seat.side] || 4) - 1);
      var r = Math.max(3.6, pitch * (0.40 - 0.06 * depth));
      // G6-FIX: seat circle + crowd face share this host for one transform chain.
      var seatGroup = el('g', { class: 'arena-seat-group', 'data-arena-seat-host': 'true' });
      var circle = el('circle', {
        cx: pt.x.toFixed(2),
        cy: pt.y.toFixed(2),
        r: r.toFixed(2),
        'data-ring': String(seat.ring),
        'data-ring-key': 'oval_' + (seat.side || 'x') + '_' + (seat.row || 0),
        'data-ring-kind': 'spectator',
        'data-cell': String(seat.cell),
        'data-side': seat.side || '',
        'data-row': String(seat.row != null ? seat.row : ''),
        'data-centroid-x': pt.x.toFixed(2),
        'data-centroid-y': pt.y.toFixed(2),
        'data-occupancy': 'empty',
        'data-state': 'idle',
        'vector-effect': 'non-scaling-stroke',
        class: 'arena-cell arena-cell--oval-seat'
      });
      seatGroup.appendChild(circle);
      layer.appendChild(seatGroup);
      var clip = el('clipPath', { id: 'arena-clip-' + seat.ring + '-' + seat.cell });
      clip.appendChild(el('circle', {
        cx: pt.x.toFixed(2), cy: pt.y.toFixed(2), r: r.toFixed(2)
      }));
      defs.appendChild(clip);
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
  // Atmospheric crowd stand-ins. Currently unreachable on purpose: the
  // Owner switched the figures off and arena_atmosphere.css hides
  // .arena-crowd-figure. Card A08 (crowd bowl depth / atmospheric
  // population) is what turns them back on, so this stays disconnected
  // rather than deleted, and the paid face assets stay in static/.
  function appendCrowdFigure(svg, ring, cell, geometry, radius) {
    var href = crowdFaceFor(ring, cell, geometry);
    if (!href) { return; }
    var seat = svg.querySelector('.arena-cell[data-ring="' + ring + '"][data-cell="' + cell + '"]');
    if (!seat) { return; }
    var seatGroup = seat.parentNode;
    if (!seatGroup) { return; }
    var cx = parseFloat(seat.getAttribute('cx'));
    var cy = parseFloat(seat.getAttribute('cy'));
    var seatR = parseFloat(seat.getAttribute('r'));
    var seatSize = seatR * 2;
    var jitter = seatJitter(ring, cell);
    // A portrait sits IN its seat, so it never grows past the seat either.
    var size = Math.min(faceDiameter(geometry, ring, radius) * jitter.scale, seatSize);
    // Off-centre by up to a fifth of the seat in each direction.
    var offsetX = jitter.x * seatSize * 0.4;
    var offsetY = jitter.y * seatSize * 0.4;

    var figure = el('g', {
      'pointer-events': 'none',
      class: 'arena-crowd-figure'
    });
    // Round portrait, not a slice of the seat's polygon. One shared clip path
    // in objectBoundingBox units serves every face whatever its size.
    var image = el('image', {
      href: href,
      x: (cx - size / 2 + offsetX).toFixed(2),
      y: (cy - size / 2 + offsetY).toFixed(2),
      width: size.toFixed(2), height: size.toFixed(2),
      // The portraits are cut out now, so the seat behind them shows through.
      // No circular clip: a round mask over a head-and-shoulders cut-out chops
      // the shoulders off and puts the carton back.
      preserveAspectRatio: 'xMidYMid meet'
    });
    image.style.filter = faceLighting(geometry, ring);
    figure.appendChild(image);
    seatGroup.appendChild(figure);
  }

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
    shell.appendChild(el('g', { 'data-arena-layer': 'crowd' }));
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

  function crowdFaceFor(ring, cell, geometry) {
    var faces = global.ARENA_CROWD_FACES || [];
    if (!faces.length) { return null; }
    // C4: round/ only (96). Near/mid/far is faceLighting() via rowDepth — no tiers/ rewrite.
    return faces[seatHash(ring, cell) % faces.length];
  }

  // Nobody in a hall sits perfectly on the centre of their seat, and a grid of
  // heads on exact centres is what made the stands read as a carton. Each face
  // is nudged off centre by a fraction of the seat, and its size varies a
  // little around the row's own size — both from the same seat hash, so they
  // never move between polls.
  function seatJitter(ring, cell) {
    var h = seatHash(ring, cell);
    return {
      x: (((h >>> 4) & 0xff) / 255 - 0.5),
      y: (((h >>> 12) & 0xff) / 255 - 0.5),
      scale: 0.9 + ((h >>> 20) & 0xff) / 255 * 0.2
    };
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

  function faceDiameter(geometry, ring, radius) {
    return radius * (FACE_NEAR + (FACE_FAR - FACE_NEAR) * rowDepth(geometry, ring));
  }

  // Depth of light. Size alone does not read as distance: with every face at
  // full brightness the back row shines as hard as the front and the
  // perspective flattens out. The mockup (§4) drops roughly 35% of brightness
  // from the near row to the far one; G8 pushes that to ~45% so four oval rows
  // actually read as a mass receding into the bowl (tokens via filter only).
  var FACE_DIM = 0.45;
  var FACE_DESATURATE = 0.38;

  // The seats fall into the dark on the same curve as the faces sitting in
  // them. arena_render.css reads --row-light; it used to hold a hand-written
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

  function faceLighting(geometry, ring) {
    var depth = rowDepth(geometry, ring);
    var brightness = 1 - FACE_DIM * depth;
    var saturation = 1 - FACE_DESATURATE * depth;
    return 'brightness(' + brightness.toFixed(3) + ') saturate(' + saturation.toFixed(3) + ')';
  }

  // G6: atmospheric stand-ins in EMPTY spectator seats — DISABLED (Owner 2026-07-27).
  // The paid face assets under static/images/crowd/ stay on disk for a later
  // real crowd pass; do not delete them. fillCrowd only clears leftover
  // .arena-crowd-figure nodes so polls do not leave ghosts. Real payload
  // spectators still render via appendOccupant / occupants layer.
  // A08 — how many atmospheric rows stand behind the real ones, and how far
  // apart. Fractions of the distance from the floor centre, so the bowl grows
  // with the stage instead of drifting off it at another size.
  var CROWD_ROWS = 3;
  var CROWD_ROW_STEP = 0.085;

  /**
   * The atmospheric crowd: the hall BEHIND the seats, never the seats.
   *
   * On 2026-07-27 the Owner had the crowd faces stopped (v2.5.612) because they
   * were stand-in portraits sitting IN EMPTY SEATS — a face where a person was
   * not. The files were kept, in his words, "for a later real crowd pass", and
   * this is that pass. The line he drew is the one thing this function must not
   * cross, so nothing here ever touches a seat element: the figures live in
   * their own layer, behind the stands, carry no slug, no occupancy, no online
   * state and no pointer events. They are scenery, and they cannot be clicked,
   * hovered, counted or mistaken for somebody who is present.
   *
   * Placement is derived from the seats that were actually drawn rather than
   * from a second copy of the seating geometry: each figure is a real seat's own
   * position pushed further from the floor centre. So if the seat contract
   * changes again, the crowd follows it instead of drifting behind it — which is
   * exactly how the last seating change left a whole rank ring with no beacon.
   *
   * Left and right are deliberately left empty: that is where AR5 puts the
   * spirit balconies, and painting them now would only be repainted then.
   */
  function fillCrowd(svg, geometry, assignments) {
    var layer = svg.querySelector('[data-arena-layer="crowd"]');
    if (!layer) { return; }
    while (layer.firstChild) { layer.removeChild(layer.firstChild); }
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-crowd-figure'), function (figure) {
      if (figure.parentNode) { figure.parentNode.removeChild(figure); }
    });

    var faces = global.ARENA_CROWD_FACES || [];
    if (!faces.length) { return; }

    // The outermost real row on each side is what the crowd stands behind.
    var anchors = [];
    ['top', 'bottom'].forEach(function (side) {
      var seats = svg.querySelectorAll('[data-ring-kind="spectator"][data-side="' + side + '"]');
      var outerRow = -1;
      Array.prototype.forEach.call(seats, function (seat) {
        var row = parseInt(seat.getAttribute('data-row'), 10);
        if (isFinite(row) && row > outerRow) { outerRow = row; }
      });
      Array.prototype.forEach.call(seats, function (seat) {
        if (parseInt(seat.getAttribute('data-row'), 10) !== outerRow) { return; }
        var x = parseFloat(seat.getAttribute('cx'));
        var y = parseFloat(seat.getAttribute('cy'));
        var r = parseFloat(seat.getAttribute('r'));
        if (isFinite(x) && isFinite(y)) { anchors.push({ x: x, y: y, r: isFinite(r) ? r : 5.6, side: side }); }
      });
    });
    if (!anchors.length) { return; }

    var defs = svg.querySelector('defs');
    var clipReady = svg.querySelector('#arena-crowd-face-clip') !== null;
    if (defs && !clipReady) {
      var clip = el('clipPath', { id: 'arena-crowd-face-clip', clipPathUnits: 'objectBoundingBox' });
      clip.appendChild(el('circle', { cx: '0.5', cy: '0.5', r: '0.5' }));
      defs.appendChild(clip);
    }

    var index = 0;
    for (var row = 1; row <= CROWD_ROWS; row++) {
      var push = 1 + row * CROWD_ROW_STEP;
      // Further back is smaller and dimmer. Opacity, not filter: every filter on
      // this floor is killed by an !important in arena_atmosphere.css written to
      // stop avatar glow escaping the rim, and that is what silently swallowed
      // the seat rows' own depth until A08 measured it.
      var scale = 1 - row * 0.11;
      var dim = 0.62 - (row - 1) * 0.16;
      for (var i = 0; i < anchors.length; i++) {
        // Alternate rows are offset by half a seat so the crowd does not read as
        // a grid of columns marching away from the floor.
        if (row % 2 === 1 && i === anchors.length - 1) { continue; }
        var a = anchors[i];
        var b = row % 2 === 1 ? anchors[i + 1] : null;
        // NEVER PAIR ACROSS THE TWO BANKS. Owner, 2026-08-06: he circled a
        // smudge on the floor at three o'clock. The anchors are the top bank
        // followed by the bottom bank in one list, so on an offset row the pair
        // (i, i+1) at the seam was the LAST seat of the top row and the FIRST of
        // the bottom one — and the midpoint of a seat above the floor and a seat
        // below it lands in the middle of the floor. Three rows, two of them
        // offset, so it put exactly two faces on the boards: measured at radius
        // 420, inside the rank rings, and 485, on the sponsors' ring, both at
        // angle 0. A crowd figure belongs behind the seats and nowhere else.
        if (b && b.side !== a.side) { continue; }
        var ax = b ? (a.x + b.x) / 2 : a.x;
        var ay = b ? (a.y + b.y) / 2 : a.y;
        var x = TPL_CX + (ax - TPL_CX) * push;
        var y = TPL_CY + (ay - TPL_CY) * push;
        var size = a.r * 2 * scale;

        var figure = el('image', {
          href: faces[index % faces.length],
          x: (x - size / 2).toFixed(2),
          y: (y - size / 2).toFixed(2),
          width: size.toFixed(2),
          height: size.toFixed(2),
          preserveAspectRatio: 'xMidYMid slice',
          'clip-path': 'url(#arena-crowd-face-clip)',
          // Depth as a custom property, not an opacity attribute: the stylesheet
          // sets opacity from it, and a CSS declaration outranks an SVG
          // attribute — an attribute here would simply be ignored.
          style: '--crowd-dim: ' + dim.toFixed(2),
          'pointer-events': 'none',
          'aria-hidden': 'true',
          class: 'arena-crowd-figure'
        });
        layer.appendChild(figure);
        index++;
      }
    }
  }

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
  }

  function bind(svg, payload, geometry) {
    var occupants = svg.querySelector('[data-arena-layer="occupants"]');
    while (occupants.firstChild) { occupants.removeChild(occupants.firstChild); }

    // The balconies are not seats and hold no occupant records, so they are
    // settled here, before the seat machinery runs, and never touched by it.
    bindSpirits(svg, payload);

    // Clear every transient attribute first: a poll may free a cell, and a
    // stale occupancy left on it would outlive its occupant.
    seatedRing = null;
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell[data-ring]'), function (seat) {
      seat.setAttribute('data-occupancy', 'empty');
      seat.setAttribute('data-state', 'idle');
      seat.removeAttribute('data-entity-slug');
      seat.chefRecord = null;
    });
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell-spark'), function (spark) {
      spark.removeAttribute('data-lit');
    });

    lightRows(svg, geometry);

    var assignments = buildAssignments(payload, geometry);
    fillCrowd(svg, geometry, assignments);

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
      seat.chefRecord = assignment.occupancy === 'spectator' ? asSpectator(entity) : entity;

      // The spark belongs to chefs, not to every occupant: a gallery spectator
      // is atmosphere and does not get a ring of light on the floor.
      if (assignment.occupancy === 'chef') {
        var spark = svg.querySelector(
          '.arena-cell-spark[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]'
        );
        if (spark) { spark.setAttribute('data-lit', 'true'); }
      }
      if (entity.slug && entity.slug === viewerSlug()) { seatedRing = assignment.ring; }

      appendOccupant(svg, occupants, assignment);
    });

    seatSponsors(svg, payload.vip_sponsors);

    markSeatable(svg, geometry);
    stampStage(svg, payload.center || { type: 'empty' });
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
   * Which free seats this viewer may take. Derived from where they are sitting
   * right now rather than from a hardcoded rule: a chef reseats inside their own
   * rank ring, a spectator anywhere in the galleries. Anonymous visitors cannot
   * sit at all, so they are never offered a seat.
   */
  function markSeatable(svg, geometry) {
    var kindByRing = {};
    geometry.rings.forEach(function (ring) { kindByRing[ring.index] = ring.kind; });

    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell[data-ring]'), function (polygon) {
      var ring = Number(polygon.getAttribute('data-ring'));
      var seatable = false;
      if (viewerSlug() && polygon.getAttribute('data-occupancy') === 'empty') {
        if (seatedRing !== null) {
          seatable = kindByRing[seatedRing] === 'rank'
            ? ring === seatedRing
            : kindByRing[ring] === 'spectator';        } else {
          // Not on the floor yet: a chef's rank ring is unknown until the
          // payload seats them, so only the galleries can be offered.
          seatable = kindByRing[ring] === 'spectator';
        }
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
    stage.style.cursor = center.popup_url ? 'pointer' : 'default';
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

    // The pads belong to the floor and are drawn whatever the centre is doing -
    // including when it is doing nothing at all, which is the state an empty
    // arena is in most of the time.
    if (type !== 'active_battle' && type !== 'facing_pair') {
      drawEmptyFighterPad(layer, { x: cx - offset, y: cy }, padR, 'challenger');
      drawEmptyFighterPad(layer, { x: cx + offset, y: cy }, padR, 'opponent');
    }
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

  /**
   * The pad with nobody on it. Same hex, same place, same plane as the filled
   * one - it is the floor's own shape and must not come and go with a battle.
   * No avatar, no name shade, no label: an empty seat, not a ghost of a chef.
   */
  function drawEmptyFighterPad(layer, centre, radius, side) {
    if (!layer || !centre) { return; }
    var points = hexPoints(centre.x, centre.y, radius).map(pointString).join(' ');
    var group = el('g', {
      class: 'arena-floor-fighter arena-floor-fighter--' + side
        + ' arena-floor-fighter--empty',
      'data-floor-side': side,
      'data-floor-state': 'empty',
      'pointer-events': 'none'
    });
    group.appendChild(el('polygon', {
      points: points,
      class: 'arena-floor-fighter__tile',
      'vector-effect': 'non-scaling-stroke'
    }));
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
      var atk = chef.atk || 0;
      var def = chef['def'] || 0;
      var show = !chef.is_spectator && (atk > 0 || def > 0);
      setText(tip.querySelector('.js-chef-atk'), atk);
      setText(tip.querySelector('.js-chef-def'), def);
      potential.hidden = !show;
    }

    var challenge = tip.querySelector('.js-challenge-btn');
    if (challenge) {
      var canChallenge = viewer.enrolled && viewer.slug && viewer.slug !== chef.slug &&
        !chef.in_battle && !chef.is_spectator;
      if (canChallenge) { challenge.href = '/chef-battle/challenge/new/?opponent=' + chef.slug; }
      challenge.hidden = !canChallenge;
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
      // The centre stage opens the live battle room, exactly as the legacy
      // centre cells did.
      var stage = event.target.closest && event.target.closest('[data-arena-stage]');
      if (stage && stageCentre && stageCentre.popup_url) {
        event.stopPropagation();
        fireRipple(svg, stage);
        global.ArenaBattleRoom.open(stageCentre.popup_url, stageCentre.battle_url);
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
   * The poll URL carries ?demo=vs when the page was opened with it.
   *
   * The poll is a POST to a bare path, so the server could not see the query
   * string the page was rendered with — it answered with the real centre and
   * wiped the preview on the first tick. The flag is only ever honoured for a
   * moderator, server-side; passing it here grants nothing.
   */
  function stateUrl() {
    var base = '/chef-battle/arena/state/';
    var flag = /(^|[?&])demo=(vs|next)(&|$)/.exec(global.location.search);
    return flag ? base + '?demo=' + flag[2] : base;
  }

  function poll(svg) {
    post(stateUrl())
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (payload) {
        if (!payload) { return; }
        // Geometry is re-read from every payload: ring capacity is a server
        // decision and may change between polls.
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
   * Publish the real header height as --arena-header-h.
   *
   * A07, Owner 2026-08-05: the arena fits the screen whole, on every screen.
   * arena_command_deck.css sizes the deck as `100svh - var(--arena-header-h)`,
   * and that variable had never been set by anything — the rule ran on its
   * 146px fallback, which is the DESKTOP header and is wrong by whatever the
   * header actually measures anywhere else. A fit computed from a constant
   * that only holds at one width is not a fit.
   *
   * Returns true when the value changed, so the caller can avoid a redundant
   * re-fit: fitScene is a two-pass measure-and-scale and is not free.
   */
  function measureHeader() {
    var header = document.querySelector(HEADER_SELECTOR);
    if (!header) { return false; }
    var height = Math.round(header.getBoundingClientRect().height);
    if (!(height > 0)) { return false; }
    var next = height + 'px';
    if (document.documentElement.style.getPropertyValue('--arena-header-h') === next) {
      return false;
    }
    document.documentElement.style.setProperty('--arena-header-h', next);
    return true;
  }

  function fitScene(svg) {
    var container = svg.parentElement;
    if (!container) { return; }

    for (var pass = 0; pass < 2; pass++) {
      // Prefer the sponsors-template floor (rank cells); fall back to oval seats.
      var cells = svg.querySelectorAll('.arena-cell--sponsors-tpl');
      if (!cells.length) {
        cells = svg.querySelectorAll('.arena-cell[data-ring-kind="spectator"]');
      }
      if (!cells.length) {
        cells = svg.querySelectorAll('.arena-cell--oval-seat');
      }
      if (!cells.length) { return; }

      var left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
      for (var i = 0; i < cells.length; i++) {
        var box = cells[i].getBoundingClientRect();
        if (!box.width || !box.height) { continue; }
        if (box.left < left) { left = box.left; }
        if (box.right > right) { right = box.right; }
        if (box.top < top) { top = box.top; }
        if (box.bottom > bottom) { bottom = box.bottom; }
      }
      if (!(right > left) || !(bottom > top)) { return; }

      var frame = container.getBoundingClientRect();
      var width = right - left, height = bottom - top;
      if (!(width > 0) || !(height > 0)) { return; }
      if (!(frame.width > 0) || !(frame.height > 0)) { return; }

      // Fit stands inside the frame at 64% — Owner 2026-07-27: shrink octagon
      // 20% from the prior 80% fit so the floor leaves more hall margin.
      var viewPad = 0.64;
      var byWidth = frame.width * viewPad / width;
      var byHeight = frame.height * viewPad / height;
      var factor = Math.min(byWidth, byHeight);
      var current = parseFloat(svg.style.getPropertyValue('--arena-fit')) || 1;
      svg.style.setProperty('--arena-fit', (current * factor).toFixed(4));

      // Composition centre: 0.50 W / 0.51 H of the frame (spec).
      var targetX = frame.left + frame.width * COMPOSITION_CX;
      var targetY = frame.top + frame.height * COMPOSITION_CY;
      var driftY = targetY - (top + bottom) / 2;
      var driftX = targetX - (left + right) / 2;
      var shiftY = parseFloat(svg.style.getPropertyValue('--arena-shift-y')) || 0;
      var shiftX = parseFloat(svg.style.getPropertyValue('--arena-shift-x')) || 0;
      svg.style.setProperty('--arena-shift-y', (shiftY + driftY).toFixed(2) + 'px');
      svg.style.setProperty('--arena-shift-x', (shiftX + driftX).toFixed(2) + 'px');
    }

    billboardFaces(svg);
    placeRankSpine(svg);
  }

  // 3G R4 (Owner D1 Option B): desktop centred stack is CSS-owned
  // (left:50% + translateX), matching Ember rank-progression composition.
  // Below 768px the ladder is a wrapped flow row (Stage 3E). Tablet mid-band
  // may still measure against the floor so the stack sits between the near
  // edge and the crown without covering it.
  function placeRankSpine(svg) {
    var spine = document.querySelector('.arena-rank-spine');
    var container = svg.parentElement;
    if (!spine || !container) { return; }

    // Clear inline geometry wherever CSS owns layout, so measured placement
    // cannot fight the stylesheet (inline style beats CSS).
    if (window.matchMedia && (
      window.matchMedia('(max-width: 767px)').matches ||
      window.matchMedia('(min-width: 901px)').matches
    )) {
      spine.style.top = '';
      spine.style.left = '';
      spine.style.width = '';
      spine.style.transform = '';
      return;
    }

    var cells = svg.querySelectorAll('.arena-cell[data-ring-kind="rank"]');
    if (!cells.length) { return; }
    var top = Infinity, bottom = -Infinity, left = Infinity, right = -Infinity;
    for (var i = 0; i < cells.length; i++) {
      var box = cells[i].getBoundingClientRect();
      if (!box.width || !box.height) { continue; }
      if (box.top < top) { top = box.top; }
      if (box.bottom > bottom) { bottom = box.bottom; }
      if (box.left < left) { left = box.left; }
      if (box.right > right) { right = box.right; }
    }
    if (!(right > left)) { return; }

    var stage = svg.querySelector('.arena-stage');
    var crownTop = stage ? stage.getBoundingClientRect().top : (top + bottom) / 2;
    var frame = container.getBoundingClientRect();
    var height = spine.getBoundingClientRect().height;

    // Sit in the band between the floor's near edge and the crown, centred in
    // it, so the column never covers the centre it is a legend for.
    var band = crownTop - top;
    var offset = top - frame.top + Math.max(6, (band - height) / 2);

    spine.style.top = offset.toFixed(1) + 'px';
    spine.style.left = ((left + right) / 2 - frame.left).toFixed(1) + 'px';
    spine.style.width = Math.min(0.34 * (right - left), 190).toFixed(1) + 'px';
  }

  // Billboarding: a face lying on the tilted floor plane is squashed, and a
  // person in a hall looks at the camera instead. The old fix pre-stretched
  // every face by the same 1/cos(56deg) = 1.79, which only works for an
  // orthographic tilt. Under perspective the squash depends on how far the
  // seat is from the camera: measured on prod, the front row came out 0.75
  // wide-to-tall (over-corrected) while the back rows came out 1.16-1.34
  // (under-corrected). No single number is right for both.
  //
  // So each face is corrected by its own measurement: multiply its current
  // stretch by its rendered width/height until the box is square. One pass
  // lands it; the second is the residue.
  function billboardFaces(svg) {
    var faces = svg.querySelectorAll('.arena-crowd-figure image');
    if (!faces.length) { return; }

    for (var pass = 0; pass < 2; pass++) {
      for (var i = 0; i < faces.length; i++) {
        var face = faces[i];
        var box = face.getBoundingClientRect();
        if (!(box.width > 0) || !(box.height > 0)) { continue; }
        var current = parseFloat(face.getAttribute('data-billboard')) || 1;
        var corrected = current * (box.width / box.height);
        face.setAttribute('data-billboard', corrected.toFixed(4));
        face.style.transform = 'scaleY(' + corrected.toFixed(4) + ')';
      }
    }
  }

  function init() {
    var svg = document.getElementById('arena-render');
    var node = document.getElementById('arena-data-json');
    if (!svg || !node || !global.ArenaGeometry) { return; }

    var payload;
    try { payload = JSON.parse(node.textContent); } catch (error) { return; }
    var geometry = payload && payload.geometry;
    if (!geometry || !Array.isArray(geometry.rings) || !geometry.rings.length) { return; }

    drawGrid(svg, geometry);
    bind(svg, payload, geometry);
    attachEvents(svg);
    measureHeader();
    fitScene(svg);
    // The frame is fluid, so the fit is re-measured whenever it changes size.
    if (global.ResizeObserver && svg.parentElement) {
      new global.ResizeObserver(function () { fitScene(svg); }).observe(svg.parentElement);
    }
    // The header is what the deck's height is subtracted FROM, and it is not a
    // constant: it wraps at narrow widths and its social strip is not always
    // there. Re-measure it whenever the window changes, then re-fit.
    if (global.ResizeObserver && document.querySelector(HEADER_SELECTOR)) {
      new global.ResizeObserver(function () {
        if (measureHeader()) { fitScene(svg); }
      }).observe(document.querySelector(HEADER_SELECTOR));
    }
    if (global.ArenaDeck) { global.ArenaDeck.refresh(payload); }
    paintRunway(payload.runway || null);
    if (global.ArenaBattleRoom) { global.ArenaBattleRoom.init(payload.latest_result); }

    pollTimer = global.setInterval(function () { poll(svg); }, POLL_INTERVAL);
    arenaSvg = svg;
    pingTimer = global.setInterval(function () { post('/chef-battle/arena/ping/').catch(function () {}); }, PING_INTERVAL);
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
    var host = document.querySelector('.arena-render-container')
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
