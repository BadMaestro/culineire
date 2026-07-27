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
  // STAGE_RADIUS follows OctagonFloorTemplate centre (85 − gap).
  var STAGE_RADIUS = 82;
  var POLL_INTERVAL = 10000;
  var PING_INTERVAL = 20000;
  // Cells are inset toward their own centroid to open the seams. Proportional
  // rather than a fixed pixel gap so inner rings (small cells) keep the same
  // visual rhythm as the outer ones.
  var CELL_INSET = 0.94;

  // G1/G5 — docs/chef_battle/arena_mockup_spec.json proportions (NO tilt in this slice).
  // Mockup stands_outer 1.60 R_floor is the OUTERMOST VISIBLE EXTENT (bbox), not
  // seat centres. G4 measured bbox M3=1.7541 with centres at 1.60; G5 shrinks
  // construction so projected bbox lands on 1.60 (1.60²/1.7541 ≈ 1.4594).
  // Floor span 0.63 is an OUTPUT after fit-by-stands; stage = 0.13 × floor;
  // composition centre at 0.50 W / 0.51 H.
  var FLOOR_SHARE = 0.63;
  var STANDS_RATIO = 1.60 * 1.60 / 1.7541;
  var STAGE_RATIO = 0.13;
  var COMPOSITION_CX = 0.50;
  var COMPOSITION_CY = 0.51;
  // G2 acceptance: projected floor height/width ≈ cos(56deg).
  var VERTICAL_COMPRESSION = 0.56;

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

  function inset(vertices, centroid) {
    return vertices.map(function (point) {
      return {
        x: centroid.x + (point.x - centroid.x) * CELL_INSET,
        y: centroid.y + (point.y - centroid.y) * CELL_INSET
      };
    });
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
    var tpl = global.OctagonFloorTemplate;
    var floorOuter = tpl ? tpl.TEMPLATE_OUTER : 515;
    var stageR = tpl ? tpl.RING_RADII.centre[1] : 85;
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

  function radiusStepFor(geometry) {
    return g1Radii(geometry).rankStep;
  }

  function floorOuterRadius(geometry, step) {
    if (step == null) { return g1Radii(geometry).floorOuter; }
    var lastRank = 0;
    (geometry.rings || []).forEach(function (ring) {
      if (ring.kind === 'rank' && ring.index > lastRank) { lastRank = ring.index; }
    });
    return STAGE_RADIUS + lastRank * step;
  }

  /* ---------------------------------------------------------------- */
  /* Grid — drawn once from geometry, then only re-stamped by bind()   */
  /* ---------------------------------------------------------------- */

  // The octagon at a given radius, as an SVG points string.
  // Orientation matches the Sponsors puzzle template (vertices at 0°, 45°, …)
  // via OctagonFloorTemplate — same shell as /sponsors/.
  function ringOutline(radius, sides) {
    var tpl = global.OctagonFloorTemplate;
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
  function drawWalkway(svg, geometry, step) {
    var props = g1Radii(geometry);
    var tpl = global.OctagonFloorTemplate;
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
  function drawRingSeams(svg, geometry, step) {
    return;
  }

  // Solid underlay beneath the sponsors-template floor (no SVG Gaussian blur).
  function drawFloorPad(svg, geometry, step, defs) {
    var props = g1Radii(geometry);
    var sides = geometry.sides || 8;
    var outer = props.floorOuter;
    var layer = el('g', { 'data-arena-layer': 'floor-pad', 'pointer-events': 'none' });
    layer.appendChild(el('polygon', {
      points: ringOutline(outer + step * 0.22, sides),
      class: 'arena-floor-pad arena-floor-pad--glow'
    }));
    layer.appendChild(el('polygon', {
      points: ringOutline(outer + step * 0.06, sides),
      class: 'arena-floor-pad'
    }));
    svg.appendChild(layer);
  }

  // Primary rank key shown on each sponsors-template ring. Arena still has 8
  // culinary ranks in the payload; rings 6–8 share the outer template ring.
  var TEMPLATE_RING_KEYS = {
    1: 'culinary_master',
    2: 'executive_chef',
    3: 'head_chef',
    4: 'sous_chef',
    5: 'chef_de_partie',
    6: 'commis_chef'
  };

  /**
   * Draw the chef floor as a 1:1 copy of the Sponsors octagon shell
   * (same CX/CY, radii, counts, gaps, fills, strokes). Sponsors page code
   * is not modified — Arena only reads OctagonFloorTemplate constants.
   */
  function drawGrid(svg, geometry) {
    var props = g1Radii(geometry);
    var step = props.rankStep;
    var tpl = global.OctagonFloorTemplate;
    if (!tpl) {
      throw new Error('OctagonFloorTemplate missing — load octagon_floor_template.js before arena_render.js');
    }

    svg.setAttribute('viewBox', '0 0 1100 1100');

    var cx = TPL_CX;
    var cy = TPL_CY;
    var gap = tpl.GAP;
    var colours = tpl.RING_COLOURS.available;
    var defs = el('defs', {});
    var cells = el('g', { 'data-arena-layer': 'cells' });
    var stageRing = geometry.rings[0];

    // No cell-shadow — soft drop-shadows bled past the outer rim as junk.

    // Outer → inner — identical order to sponsors_puzzle.js drawPuzzle.
    for (var ring = 6; ring >= 1; ring--) {
      var count = tpl.RING_COUNTS[ring];
      var innerR = tpl.RING_RADII[ring][0];
      var outerR = tpl.RING_RADII[ring][1];
      var sweep = (2 * Math.PI) / count;
      var offset = -Math.PI / 2 - sweep / 2;
      var fill = colours[ring];
      var ringKey = TEMPLATE_RING_KEYS[ring] || '';

      for (var pos = 0; pos < count; pos++) {
        var startAngle = offset + pos * sweep + gap / outerR;
        var endAngle = offset + (pos + 1) * sweep - gap / outerR;
        var d = tpl.ringSegmentPath(
          cx, cy, innerR + gap, outerR - gap / 2, startAngle, endAngle
        );
        var centroid = tpl.segmentCentroid(
          cx, cy, innerR + gap, outerR - gap / 2, startAngle, endAngle
        );
        var pathEl = el('path', {
          d: d,
          fill: fill,
          stroke: '#fff',
          'stroke-width': '1.5',
          'data-ring': String(ring),
          'data-ring-key': ringKey,
          'data-ring-kind': 'rank',
          'data-cell': String(pos),
          'data-centroid-x': centroid.x.toFixed(2),
          'data-centroid-y': centroid.y.toFixed(2),
          'data-occupancy': 'empty',
          'data-state': 'idle',
          class: 'arena-cell arena-cell--sponsors-tpl'
        });
        cells.appendChild(pathEl);

        var clip = el('clipPath', { id: 'arena-clip-' + ring + '-' + pos });
        clip.appendChild(el('path', { d: d }));
        defs.appendChild(clip);
      }
    }

    var faceClip = el('clipPath', { id: 'arena-face-clip', clipPathUnits: 'objectBoundingBox' });
    faceClip.appendChild(el('circle', { cx: '0.5', cy: '0.5', r: '0.5' }));
    defs.appendChild(faceClip);

    var centreR = tpl.RING_RADII.centre[1] - gap;
    var centrePts = tpl.octagonPoints(cx, cy, centreR);
    var centreClip = el('clipPath', { id: 'arena-clip-0-0' });
    centreClip.appendChild(el('polygon', { points: centrePts }));
    defs.appendChild(centreClip);

    // Hard clip: avatars / cell strokes / any filter bleed cannot paint past
    // the outer octagon. Grey walkway is drawn OUTSIDE this group.
    var floorClip = el('clipPath', { id: 'arena-shell-clip' });
    floorClip.appendChild(el('polygon', {
      points: tpl.octagonPoints(cx, cy, tpl.TEMPLATE_OUTER)
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
      fill: colours[0],
      stroke: '#fff',
      'stroke-width': '2',
      'data-ring': String(stageRing.index),
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
    var tpl = global.OctagonFloorTemplate;
    // Sponsors template: 6 rings. Arena payload still has 8 rank keys —
    // geometry rings 1–5 map 1:1; rings 6–8 (commis/prep/porter) share outer ring 6.
    var occupiedByRing = { 1: {}, 2: {}, 3: {}, 4: {}, 5: {}, 6: {} };
    var capacity = {};
    for (var r = 1; r <= 6; r++) {
      capacity[r] = tpl ? tpl.RING_COUNTS[r] : 60;
    }

    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'rank') { return; }
      var templateRing = Math.min(6, ring.index);
      var chefs = ((payload.rings && payload.rings[ring.key]) || []).filter(function (chef) {
        return chef && !isDisplaced(chef, center);
      });
      // Stable order so hash collisions resolve the same way every poll.
      chefs.sort(function (a, b) {
        return String(a.slug || '').localeCompare(String(b.slug || ''));
      });
      chefs.forEach(function (chef) {
        var occupied = occupiedByRing[templateRing];
        var cell = pickScatteredCell(
          templateRing, chef.slug, capacity[templateRing], occupied
        );
        if (cell < 0) { return; }
        occupied[cell] = true;
        assignments.push({
          ring: templateRing, cell: cell, entity: chef,
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

  function floorRadius(svg, geometry) {
    return g1Radii(geometry).floorOuter;
  }

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
    var tpl = global.OctagonFloorTemplate;
    if (assignment.occupancy !== 'chef') { return; }
    if (entity.is_online === false) { return; }
    if (!seat || !tpl) { return; }

    var ring = assignment.ring;
    var cell = assignment.cell;
    var count = tpl.RING_COUNTS[ring];
    var radii = tpl.RING_RADII[ring];
    if (!count || !radii) { return; }

    var outerR = radii[1] - tpl.GAP / 2;
    var innerR = radii[0] + tpl.GAP;
    var sweep = (2 * Math.PI) / count;
    var offset = -Math.PI / 2 - sweep / 2;
    var startAngle = offset + cell * sweep + tpl.GAP / outerR;
    var endAngle = offset + (cell + 1) * sweep - tpl.GAP / outerR;
    var pts = tpl.ringSegmentPoints(TPL_CX, TPL_CY, innerR, outerR, startAngle, endAngle);

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
      if (!seat) { return; }
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

  function drawFloorCrown(layer, cx, cy, radius, center) {
    var assets = global.ARENA_CROWN_ASSETS || {};
    // Same clip as .arena-stage (#arena-clip-0-0) — marble/glyph are inscribed
    // in the centre octagon like chef avatars in ring cells, not a free rectangle.
    var group = el('g', {
      class: 'arena-floor-crown',
      'pointer-events': 'none',
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
      var gSize = radius * 1.05;
      group.appendChild(el('image', {
        href: assets.glyph,
        x: (cx - gSize / 2).toFixed(2),
        y: (cy - radius * 0.78).toFixed(2),
        width: gSize.toFixed(2),
        height: gSize.toFixed(2),
        preserveAspectRatio: 'xMidYMid meet',
        class: 'arena-floor-crown__glyph'
      }));
    }

    var label = el('text', {
      x: cx.toFixed(2),
      y: (cy + radius * 0.22).toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      class: 'arena-floor-crown__label'
    });
    label.textContent = 'CROWN HOLDER';
    group.appendChild(label);

    var name = el('text', {
      x: cx.toFixed(2),
      y: (cy + radius * 0.48).toFixed(2),
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      class: 'arena-floor-crown__name'
    });
    name.textContent = (center && center.name) || '';
    group.appendChild(name);
    layer.appendChild(group);
  }

  function drawFloorVs(layer, cx, cy, radius, center) {
    var tpl = global.OctagonFloorTemplate;
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
    if (fighter.name) {
      var label = el('text', {
        x: centre.x.toFixed(2),
        y: (centre.y + radius + 16).toFixed(2),
        'text-anchor': 'middle',
        'dominant-baseline': 'hanging',
        class: 'arena-floor-fighter__name'
      });
      label.textContent = fighter.name;
      group.appendChild(label);
    }
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
    var scrollX = global.scrollX || global.pageXOffset;
    var scrollY = global.scrollY || global.pageYOffset;
    var margin = 8;
    var left = rect.left + scrollX + (rect.width / 2) - (tip.offsetWidth / 2);
    var maxLeft = scrollX + global.innerWidth - tip.offsetWidth - margin;
    tip.style.left = Math.max(scrollX + margin, Math.min(left, maxLeft)) + 'px';
    tip.style.top = (rect.bottom + scrollY + margin) + 'px';
  }

  function setHidden(node, hidden) { if (node) { node.hidden = hidden; } }
  function setText(node, value) { if (node) { node.textContent = value; } }

  function hideTooltip() {
    var tip = tooltipEl();
    if (tip) { tip.hidden = true; }
  }

  /** One-shot ripple at the click point, in SVG user space. */
  function fireRipple(svg, event) {
    if (!svg.createSVGPoint || !svg.getScreenCTM) { return; }
    var point = svg.createSVGPoint();
    point.x = event.clientX;
    point.y = event.clientY;
    var ctm = svg.getScreenCTM();
    if (!ctm) { return; }
    var at = point.matrixTransform(ctm.inverse());
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
    svg.addEventListener('mouseover', function (event) {
      var seat = event.target.closest && event.target.closest('.arena-cell[data-seatable]');
      if (seat) { showSeatLabel(svg, seat); } else { hideSeatLabel(svg); }
    });
    svg.addEventListener('mouseleave', function () { hideSeatLabel(svg); });

    svg.addEventListener('click', function (event) {
      // The centre stage opens the live battle room, exactly as the legacy
      // centre cells did.
      var stage = event.target.closest && event.target.closest('[data-arena-stage]');
      if (stage && stageCentre && stageCentre.popup_url) {
        event.stopPropagation();
        fireRipple(svg, event);
        global.ArenaBattleRoom.open(stageCentre.popup_url, stageCentre.battle_url);
        return;
      }
      var seat = event.target.closest && event.target.closest('.arena-cell[data-ring]');
      if (!seat || !seat.chefRecord) { hideTooltip(); return; }
      event.stopPropagation();
      fireRipple(svg, event);
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
