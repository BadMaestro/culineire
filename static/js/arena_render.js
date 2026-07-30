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
    // The backend owns the stable 290-seat contract. Keep its ring/cell ids
    // intact; the fallback mirrors ArenaGeometry's frozen 2/3/2/3-row layout.
    var rowsBySide = oval.rows_by_side || { top: 2, right: 3, bottom: 2, left: 3 };
    var countsBySide = oval.counts_by_side || {
      top: [28, 29],
      right: [28, 29, 31],
      bottom: [28, 29],
      left: [28, 29, 31]
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
      // The crown plate is drawn once, below, as the stage polygon with its own
      // gold rim and bulbs. Drawing a cell for it as well put a second, LIGHT
      // octagon over the gold — the grey ring the Owner saw — and pushed the moat
      // out to where it no longer touched the crown.
      if (entry.kind === 'crown') { continue; }
      var innerR = entry.inner;
      var outerR = entry.outer;
      var sweep = (2 * Math.PI) / count;
      var offset = -Math.PI / 2 - sweep / 2;
      // Ranks keep the backend index in data-ring (the seating key). The moat
      // and the VIP ring hold no seats yet (AR3 / AR5), so they carry no
      // seating index at all rather than a made-up one.
      var ringAttr = entry.ring === null ? '' : String(entry.ring);

      for (var pos = 0; pos < count; pos++) {
        var startAngle = offset + pos * sweep + gap / outerR;
        var endAngle = offset + (pos + 1) * sweep - gap / outerR;
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

        // AR3 — the moat is lit, not decorated. One lantern at each cell centre;
        // the glow is CSS so the light stays a token and never a literal.
        if (entry.kind === 'moat') {
          // The glint each lamp throws INWARD, onto the gold Crown ring: same
          // angle as the lamp, placed at the moat's inner edge. Eight lamps make
          // eight glints — a single halo on the plate would read as one light
          // coming from nowhere.
          var midAng = (startAngle + endAngle) / 2;
          var gp = tpl.octPoint(cx, cy, midAng, innerR + gap);
          cells.appendChild(el('ellipse', {
            cx: gp[0].toFixed(2), cy: gp[1].toFixed(2), rx: '11', ry: '5',
            transform: 'rotate(' + (midAng * 180 / Math.PI + 90).toFixed(2) + ' ' +
              gp[0].toFixed(2) + ' ' + gp[1].toFixed(2) + ')',
            'pointer-events': 'none', class: 'arena-lantern-glint'
          }));

          var lamp = el('circle', {
            cx: centroid.x.toFixed(2), cy: centroid.y.toFixed(2), r: '4.2',
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
          // 11.25 degrees, a face is 45), so that box is folded by the corner.
          // The word is folded with it: half on each face, each half rotated to
          // its own side, so SPONSORS turns the corner instead of fighting it.
          // The three boxes between corners are flat and carry V, I and P.
          var mid = (startAngle + endAngle) / 2;
          var addLabel = function (text, a0, a1, cls) {
            var c = tpl.segmentCentroid(cx, cy, innerR + gap, outerR - gap / 2, a0, a1);
            var deg = ((a0 + a1) / 2) * 180 / Math.PI + 90;
            var node = el('text', {
              x: c.x.toFixed(2), y: c.y.toFixed(2),
              'text-anchor': 'middle', 'dominant-baseline': 'central',
              'pointer-events': 'none',
              transform: 'rotate(' + deg.toFixed(2) + ' ' + c.x.toFixed(2) + ' ' + c.y.toFixed(2) + ')',
              class: cls
            });
            node.textContent = text;
            cells.appendChild(node);
          };
          if ((pos % 4) === 0) {
            addLabel('SPON', startAngle, mid, 'arena-vip-label arena-vip-label--word');
            addLabel('SORS', mid, endAngle, 'arena-vip-label arena-vip-label--word');
          } else {
            addLabel(['', 'V', 'I', 'P'][pos % 4], startAngle, endAngle, 'arena-vip-label');
          }
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
    shell.appendChild(el('g', { 'data-arena-layer': 'occupants' }));
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

    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'rank') { return; }
      var chefs = ((payload.rings && payload.rings[ring.key]) || []).filter(function (chef) {
        return chef && !isDisplaced(chef, center);
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
  function fillCrowd(svg, geometry, assignments) {
    var layer = svg.querySelector('[data-arena-layer="crowd"]');
    if (layer) {
      while (layer.firstChild) { layer.removeChild(layer.firstChild); }
    }
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-crowd-figure'), function (figure) {
      if (figure.parentNode) { figure.parentNode.removeChild(figure); }
    });
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

    // Clear every transient attribute first: a poll may free a cell, and a
    // stale occupancy left on it would outlive its occupant.
    seatedRing = null;
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell[data-ring]'), function (seat) {
      seat.setAttribute('data-occupancy', 'empty');
      seat.setAttribute('data-state', 'idle');
      seat.removeAttribute('data-entity-slug');
      seat.chefRecord = null;
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
      if (entity.slug && entity.slug === viewerSlug()) { seatedRing = assignment.ring; }

      appendOccupant(svg, occupants, assignment);
    });

    markSeatable(svg, geometry);
    stampStage(svg, payload.center || { type: 'empty' });
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

  function stampFloorCentre(svg, center) {
    var layer = svg.querySelector('[data-arena-layer="centre"]');
    if (!layer) { return; }
    while (layer.firstChild) { layer.removeChild(layer.firstChild); }
    if (!center || !center.type) { return; }

    // Plan coords — CSS rotateX(42deg) on #arena-render tilts the whole floor
    // including these pads, so they share the octagon plane (mockup M07).
    var cx = TPL_CX;
    var cy = TPL_CY;
    var type = center.type;
    var padR = STAGE_RADIUS * 1.15;
    var offset = STAGE_RADIUS * 2.35;
    var stage = svg.querySelector('.arena-stage');
    if (stage) {
      stage.setAttribute('data-state', type);
      stage.setAttribute('data-occupancy', type === 'crown' ? 'crown' : 'stage');
    }

    if (type === 'active_battle' || type === 'facing_pair') {
      drawFloorFighter(svg, layer, center.challenger, { x: cx - offset, y: cy }, padR, 'challenger');
      drawFloorVs(layer, cx, cy, STAGE_RADIUS * 0.92, center);
      drawFloorFighter(svg, layer, center.opponent, { x: cx + offset, y: cy }, padR, 'opponent');
      return;
    }

    if (type === 'crown') {
      // Reference: centre octagon holds crown glyph + nick only — never the
      // holder avatar (that would cover / mis-read the stage pad).
      drawFloorCrown(layer, cx, cy, STAGE_RADIUS, center);
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

    var bulbs = el('g', { class: 'arena-floor-crown__bulbs' });
    // Centre of the brown band, measured along the edge normal. octagonPathD
    // takes a CIRCUMradius, but a bulb sits on a flat edge, whose distance from
    // the centre is the APOTHEM — shorter by cos(PI/8). Using the circumradius
    // here pushed every bulb about 7.6% of the radius too far out, past the
    // outer wall, so none of them sat in the band they belong to.
    var apothem = Math.cos(Math.PI / 8);
    var bulbR = ((recessInnerR + recessOuterR) / 2) * apothem;
    var i;
    for (i = 0; i < 8; i++) {
      var angle = i * Math.PI / 4 + Math.PI / 8;
      var bx = cx + bulbR * Math.cos(angle);
      var by = cy + bulbR * Math.sin(angle);
      var far = Math.sin(angle) < -0.05;
      // Glow reaches the gold lip: the bulb sits (bulbR - goldOuterR*apothem)
      // away from it, so a halo smaller than that gap can never light it. Sized
      // from the radius, not a fixed number, so it survives a stage resize.
      var glowR = (bulbR - goldOuterR * apothem) * (far ? 1.15 : 1.45);
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
        r: (radius * (far ? 0.0104 : 0.0140)).toFixed(2),
        fill: 'url(#arena-crown-bulb-grad)',
        class: 'arena-floor-crown__bulb-core' + (far ? ' arena-floor-crown__bulb-core--far' : '')
      }));
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

    // Bulbs go on TOP of the gold. Drawn under it, as they were, the lip
    // painted over every glow and no light could reach the gold at all.
    frame.appendChild(bulbs);

    stack.appendChild(frame);
  }

  function drawFloorCrown(layer, cx, cy, radius, center) {
    var assets = global.ARENA_CROWN_ASSETS || {};
    var svg = layer.ownerSVGElement || document.getElementById('arena-render');
    var stack = el('g', {
      class: 'arena-floor-crown',
      'pointer-events': 'none'
    });

    drawCrownStageFrame(stack, svg, cx, cy, radius);

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
      var gSize = radius * 0.62;
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
    tip.querySelector('.arena-tooltip__link').href = '/chef-battle/profile/' + chef.slug + '/';

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

  function poll(svg) {
    post('/chef-battle/arena/state/')
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (payload) {
        if (!payload) { return; }
        // Geometry is re-read from every payload: ring capacity is a server
        // decision and may change between polls.
        if (payload.geometry) { bind(svg, payload, payload.geometry); fitScene(svg); }
        if (global.ArenaDeck) { global.ArenaDeck.refresh(payload); }
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
    fitScene(svg);
    // The frame is fluid, so the fit is re-measured whenever it changes size.
    if (global.ResizeObserver && svg.parentElement) {
      new global.ResizeObserver(function () { fitScene(svg); }).observe(svg.parentElement);
    }
    if (global.ArenaDeck) { global.ArenaDeck.refresh(payload); }
    if (global.ArenaBattleRoom) { global.ArenaBattleRoom.init(payload.latest_result); }

    pollTimer = global.setInterval(function () { poll(svg); }, POLL_INTERVAL);
    pingTimer = global.setInterval(function () { post('/chef-battle/arena/ping/').catch(function () {}); }, PING_INTERVAL);
  }

  global.ArenaRender = { init: init, buildAssignments: buildAssignments, isDisplaced: isDisplaced };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
