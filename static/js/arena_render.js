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

  var SVG_SIZE = 1000;
  var OUTER_MARGIN = 26;
  var STAGE_RADIUS = 88;
  var POLL_INTERVAL = 10000;
  var PING_INTERVAL = 20000;
  // Cells are inset toward their own centroid to open the seams. Proportional
  // rather than a fixed pixel gap so inner rings (small cells) keep the same
  // visual rhythm as the outer ones.
  var CELL_INSET = 0.94;

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
  // Share of the frame taken by the FULL illustrated octagon (rank + spectator
  // rings + walkway). Historically this was 0.66 of WIDTH measured on RANK
  // cells only — that left the outer rings larger than the frame, and with
  // overflow:visible they clipped under the ribbon and lower broadcast
  // (Owner screenshot 2026-07-24). Fit the whole visible scene instead.
  var SCENE_SHARE = 0.90;

  var CONVERGENCE = 0;
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
    var usable = (SVG_SIZE / 2) - OUTER_MARGIN - STAGE_RADIUS;
    var floorRings = (geometry.rings || []).filter(function (ring) {
      return ring.kind === 'stage' || ring.kind === 'rank';
    });
    // Chef floor depth only — oval stands sit outside and must not shrink the octagon.
    return usable / Math.max(1, Math.max(floorRings.length, 9) - 1);
  }

  function floorOuterRadius(geometry, step) {
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
  function ringOutline(radius, sides) {
    var project = projector();
    var points = [];
    for (var i = 0; i < sides; i++) {
      var angle = (Math.PI * 2 * i) / sides - Math.PI / 2;
      points.push(project(global.ArenaGeometry.polar(SVG_SIZE / 2, SVG_SIZE / 2, radius, angle)));
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
    var floorR = floorOuterRadius(geometry, step);
    var oval = geometry.spectator_oval || {};
    var rowsBySide = oval.rows_by_side || { top: 2, right: 3, bottom: 2, left: 3 };
    var beFloor = oval.floor_outer_radius || 220;
    var scale = floorR / beFloor;
    var seats = oval.seats && oval.seats.length
      ? oval.seats
      : (global.ArenaGeometry.ovalSeats
        ? global.ArenaGeometry.ovalSeats(0, 0, beFloor, rowsBySide).map(function (s) {
            return s;
          })
        : []);

    seats.forEach(function (seat) {
      var planX = SVG_SIZE / 2 + seat.x * scale;
      var planY = SVG_SIZE / 2 + seat.y * scale;
      var pt = project({ x: planX, y: planY });
      var pitch = Math.max(14, floorR * 0.055);
      var r = Math.max(5, pitch * 0.42 * Math.min(1.15, scale));
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
      layer.appendChild(circle);
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
    var lastRank = 0;
    geometry.rings.forEach(function (ring) {
      if (ring.kind === 'rank' && ring.index > lastRank) { lastRank = ring.index; }
    });
    if (!lastRank) { return; }

    var radius = STAGE_RADIUS + lastRank * step;
    var sides = geometry.sides || 8;
    var band = el('g', { 'data-arena-layer': 'walkway', 'pointer-events': 'none' });

    band.appendChild(el('polygon', {
      points: ringOutline(radius + step * 0.34, sides),
      class: 'arena-walkway'
    }));
    band.appendChild(el('polygon', {
      points: ringOutline(radius, sides),
      class: 'arena-rim arena-rim--inner'
    }));
    band.appendChild(el('polygon', {
      points: ringOutline(radius + step * 0.68, sides),
      class: 'arena-rim arena-rim--outer'
    }));
    svg.appendChild(band);
  }

  function drawGrid(svg, geometry) {
    var step = radiusStepFor(geometry);
    var project = projector();
    var defs = el('defs', {});
    var cells = el('g', { 'data-arena-layer': 'cells' });
    var stageRing = geometry.rings[0];
    // Chef floor only (stage + rank). Spectator oval is drawn separately —
    // Owner 2026-07-24: viewers do not sit in octagon cells.
    var floorRings = geometry.rings.filter(function (ring) {
      return ring.kind === 'stage' || ring.kind === 'rank';
    });
    var floorRingCount = floorRings.length;

    floorRings.forEach(function (ring) {
      if (ring.index === 0) { return; }
      for (var segment = 0; segment < ring.segments; segment++) {
        var vertices = global.ArenaGeometry.cellVertices(
          SVG_SIZE / 2, SVG_SIZE / 2, ring.index, segment,
          floorRingCount, ring.segments, step, geometry.sides, STAGE_RADIUS
        );
        var centroid = global.ArenaGeometry.cellCentroid(vertices);
        // Project after the plan-space maths, never before: the geometry
        // contract owns the rings, the projection only draws them.
        var shape = inset(vertices, centroid).map(project);
        centroid = project(centroid);
        var polygon = el('polygon', {
          points: shape.map(pointString).join(' '),
          'data-ring': String(ring.index),
          'data-ring-key': ring.key || '',
          'data-ring-kind': ring.kind || 'unknown',
          'data-cell': String(segment),
          'data-centroid-x': centroid.x.toFixed(2),
          'data-centroid-y': centroid.y.toFixed(2),
          'data-occupancy': 'empty',
          'data-state': 'idle',
          'vector-effect': 'non-scaling-stroke',
          class: 'arena-cell'
        });
        cells.appendChild(polygon);

        // One clip path per cell, reused by whoever occupies it. Avatars are
        // clipped to the cell outline so an occupant fills its tile instead of
        // floating as a square inside it.
        var clip = el('clipPath', { id: 'arena-clip-' + ring.index + '-' + segment });
        clip.appendChild(el('polygon', { points: shape.map(pointString).join(' ') }));
        defs.appendChild(clip);
      }
    });

    // One clip for every crowd portrait. objectBoundingBox units mean the same
    // path fits a face of any size, so the front row and the back row share it.
    var faceClip = el('clipPath', { id: 'arena-face-clip', clipPathUnits: 'objectBoundingBox' });
    faceClip.appendChild(el('circle', { cx: '0.5', cy: '0.5', r: '0.5' }));
    defs.appendChild(faceClip);

    svg.appendChild(defs);
    svg.appendChild(cells);
    drawWalkway(svg, geometry, step);
    drawSpectatorOval(svg, geometry, step, defs);
    svg.appendChild(el('circle', {
      cx: SVG_SIZE / 2, cy: SVG_SIZE / 2, r: STAGE_RADIUS,
      'data-ring': String(stageRing.index),
      'data-ring-key': stageRing.key,
      'data-ring-kind': stageRing.kind,
      'data-occupancy': 'stage',
      'data-state': 'open',
      'data-arena-stage': 'true',
      'vector-effect': 'non-scaling-stroke',
      class: 'arena-stage'
    }));
    svg.appendChild(el('g', { 'data-arena-layer': 'crowd' }));
    svg.appendChild(el('g', { 'data-arena-layer': 'occupants' }));
    svg.appendChild(el('g', { 'data-arena-layer': 'centre' }));

    // One label, moved to whichever free seat is hovered — 368 hidden labels
    // would cost the same DOM every poll for a thing only ever seen once.
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

  function buildAssignments(payload, geometry) {
    var assignments = [];
    var center = payload.center || {};

    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'rank') { return; }
      var chefs = ((payload.rings && payload.rings[ring.key]) || []).filter(function (chef) {
        return chef && !isDisplaced(chef, center);
      });
      chefs.slice(0, ring.segments).forEach(function (chef, cell) {
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

  function crowdFaceFor(ring, cell) {
    var faces = global.ARENA_CROWD_FACES || [];
    if (!faces.length) { return null; }
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
    var step = radiusStepFor(geometry);
    var last = 0;
    geometry.rings.forEach(function (ring) {
      if (ring.kind === 'rank' && ring.index > last) { last = ring.index; }
    });
    return STAGE_RADIUS + last * step;
  }

  // How far back a seat sits, 0 at the front row and 1 at the back. The server
  // puts row / rows_total in the geometry contract for exactly this, so depth
  // never has to be inferred from an absolute ring index that shifts whenever
  // the stands get deeper.
  function rowDepth(geometry, ring) {
    var record = null;
    geometry.rings.forEach(function (r) { if (r.index === ring) { record = r; } });
    if (!record || !record.row || !record.rows_total || record.rows_total < 2) { return 0; }
    return Math.min(1, Math.max(0, (record.row - 1) / (record.rows_total - 1)));
  }

  function faceDiameter(geometry, ring, radius) {
    return radius * (FACE_NEAR + (FACE_FAR - FACE_NEAR) * rowDepth(geometry, ring));
  }

  // Depth of light. Size alone does not read as distance: with every face at
  // full brightness the back row shines as hard as the front and the
  // perspective flattens out. The mockup (§4) drops roughly 35% of brightness
  // from the near row to the far one, and lets the far rows fall toward the
  // hall's own colour, so the crowd recedes instead of standing in a wall.
  var FACE_DIM = 0.35;
  var FACE_DESATURATE = 0.28;

  // The seats fall into the dark on the same curve as the faces sitting in
  // them. arena_render.css reads --row-light; it used to hold a hand-written
  // ladder of ring numbers, which stopped covering the stands the moment they
  // grew from four rows to eight. One source of depth, written from here.
  function lightRows(svg, geometry) {
    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'spectator') { return; }
      var light = (1 - FACE_DIM * rowDepth(geometry, ring.index)).toFixed(3);
      var seats = svg.querySelectorAll('.arena-cell[data-ring="' + ring.index + '"]');
      Array.prototype.forEach.call(seats, function (seat) {
        seat.style.setProperty('--row-light', light);
      });
    });
  }

  function faceLighting(geometry, ring) {
    var depth = rowDepth(geometry, ring);
    var brightness = 1 - FACE_DIM * depth;
    var saturation = 1 - FACE_DESATURATE * depth;
    return 'brightness(' + brightness.toFixed(3) + ') saturate(' + saturation.toFixed(3) + ')';
  }

  function appendCrowdFigure(svg, layer, ring, cell, geometry, radius) {
    var href = crowdFaceFor(ring, cell);
    if (!href) { return; }
    var polygon = svg.querySelector('.arena-cell[data-ring="' + ring + '"][data-cell="' + cell + '"]');
    if (!polygon) { return; }
    var box = polygon.getBBox();
    var jitter = seatJitter(ring, cell);
    // A portrait sits IN its seat, so it never grows past the seat either.
    var size = Math.min(faceDiameter(geometry, ring, radius) * jitter.scale,
                        Math.max(box.width, box.height));
    // Off-centre by up to a fifth of the seat in each direction.
    var offsetX = jitter.x * box.width * 0.4;
    var offsetY = jitter.y * box.height * 0.4;

    var figure = el('g', {
      'pointer-events': 'none',
      class: 'arena-crowd-figure'
    });
    // Round portrait, not a slice of the seat's polygon. One shared clip path
    // in objectBoundingBox units serves every face whatever its size.
    var image = el('image', {
      href: href,
      x: (box.x + box.width / 2 - size / 2 + offsetX).toFixed(2),
      y: (box.y + box.height / 2 - size / 2 + offsetY).toFixed(2),
      width: size.toFixed(2), height: size.toFixed(2),
      // The portraits are cut out now, so the seat behind them shows through.
      // No circular clip: a round mask over a head-and-shoulders cut-out chops
      // the shoulders off and puts the carton back.
      preserveAspectRatio: 'xMidYMid meet'
    });
    image.style.filter = faceLighting(geometry, ring);
    figure.appendChild(image);
    layer.appendChild(figure);
  }

  // Build Plan 3C: interactive spectator seats are REAL viewers only.
  // Atmospheric packed-hall presentation lives outside these polygons (hall
  // image / arena_atmosphere haze) and must not impersonate registered or
  // online users. Default-avatar stand-ins therefore must never be drawn into
  // empty interactive seats — leave them empty so front-row-first self-seating
  // and live payload.spectators remain honest.
  //
  // crowdFaceFor / seatHash / appendCrowdFigure stay in-tree as unused helpers
  // (constitution: do not delete suspected legacy during first 2D work). They
  // are no longer called from bind().
  function fillCrowd(svg, geometry, assignments) {
    var layer = svg.querySelector('[data-arena-layer="crowd"]');
    if (!layer) { return; }
    while (layer.firstChild) { layer.removeChild(layer.firstChild); }
    // Intentionally empty: no synthetic occupants in interactive seats.
  }

  function initialOf(entity) {
    var source = (entity.name || entity.slug || '').trim();
    return source ? source.charAt(0).toUpperCase() : '?';
  }

  function appendOccupant(svg, layer, assignment) {
    var entity = assignment.entity || {};
    var selector = '.arena-cell[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]';
    var seat = svg.querySelector(selector);
    if (!seat) { return; }

    var box = seat.getBBox();
    var size = Math.max(box.width, box.height);
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

    var project = projector();
    var cx = SVG_SIZE / 2;
    var cy = SVG_SIZE / 2;
    var type = center.type;

    if (type === 'active_battle' || type === 'facing_pair') {
      var offset = STAGE_RADIUS * 2.35;
      var size = STAGE_RADIUS * 1.55;
      drawFloorFighter(svg, layer, center.challenger, project({ x: cx - offset, y: cy }), size, 'challenger');
      drawFloorFighter(svg, layer, center.opponent, project({ x: cx + offset, y: cy }), size, 'opponent');
    }
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
      var size = radius * 1.72;
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
        y: (centre.y + radius + 18).toFixed(2),
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
      cx: SVG_SIZE / 2, cy: SVG_SIZE / 2, r: STAGE_RADIUS,
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

  // Fit the tilted scene inside its frame.
  //
  // This cannot be done in CSS. A square SVG tilted by rotateX draws cos(angle)
  // of its height, but the container also carries perspective:1500px, and
  // perspective is not a constant scale — the nearer half of a tall element is
  // magnified more than a short one, so the octagon's final on-screen size is
  // not a fixed fraction of the SVG's own box. Sizing off a measured constant
  // was tried in v2.5.336 and overshot by 251px a side: the constant taken at
  // one size is wrong at the next.
  //
  // So measure the thing itself. Read the octagon's real on-screen box, scale
  // by whichever axis runs out first, and repeat once — the second pass lands
  // on the residue the changed perspective leaves behind. Two passes measure
  // under 1px of drift, so there is no third.
  function fitScene(svg) {
    var container = svg.parentElement;
    if (!container) { return; }

    for (var pass = 0; pass < 2; pass++) {
      // Fit the FULL visible octagon (rank + spectator + walkway + stage).
      // Measuring RANK alone under-scaled relative to the outer rings, so the
      // stands clipped under the ribbon/footer (Owner 2026-07-24). Skip zero
      // rects — hidden cells report 0 at the origin and collapse the fit.
      var parts = svg.querySelectorAll(
        '.arena-cell, .arena-walkway, .arena-rim, .arena-stage'
      );
      if (!parts.length) { return; }

      var left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity;
      for (var i = 0; i < parts.length; i++) {
        var box = parts[i].getBoundingClientRect();
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

      // Uniform scale: keep the whole scene inside the frame on BOTH axes with
      // a small margin (panels/ribbon still readable around it).
      var byWidth = frame.width * SCENE_SHARE / width;
      var byHeight = frame.height * SCENE_SHARE / height;
      var factor = Math.min(byWidth, byHeight);
      var current = parseFloat(svg.style.getPropertyValue('--arena-fit')) || 1;
      svg.style.setProperty('--arena-fit', (current * factor).toFixed(4));

      // Centre in screen space on BOTH axes (Owner: octagon sat left/high and
      // clipped). Previously only Y was corrected.
      var driftY = (frame.top + frame.bottom) / 2 - (top + bottom) / 2;
      var driftX = (frame.left + frame.right) / 2 - (left + right) / 2;
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
