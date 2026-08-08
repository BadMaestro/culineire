/*
 * The Arena's OWN octagon geometry.
 *
 * Owner's instruction, 2026-07-30: "у нас никаких связей между арены и шаблоном
 * спонсоров не должно быть" — the arena must share no code with the Sponsors
 * puzzle. When the octagon was first brought over, the instruction was to make a
 * faithful COPY of the sponsors floor template and move it to the arena; instead
 * the renderer kept reading `OctagonFloorTemplate` live, and every consumer that
 * still trusted that foreign table drifted the moment the arena grew its own
 * rings: occupant capacity, the online beacon and the cell radii all disagreed
 * with what was actually drawn, and chefs silently vanished from the floor.
 *
 * So this file is that copy. The maths below is identical to the sponsors
 * template's (same circumradius convention, same 12-step segment tessellation,
 * same gap handling), which is what keeps the arena floor pixel-faithful to the
 * approved shell — but it is the arena's own, and changing it cannot touch the
 * Sponsors page.
 *
 * The ONLY relationship left between the two is a product one, not a code one:
 * sponsors sit in the arena's VIP ring (ring 11).
 *
 * Ring structure — eleven rings, centre outward (ARENA_BATTLE_PLAN §2 v2):
 *   1  Crown Holder      the centre plate, crown + holder's name
 *   2  Moat              no visible cells; lanterns light the gold ring (AR3)
 *   3..10  the eight culinary ranks, Culinary Master → Kitchen Porter
 *   11 VIP Guests        reserved for sponsors (AR5)
 */
(function (global) {
  'use strict';

  // Plan-space centre and outer edge. The viewBox is 0 0 1100 1100, so the
  // octagon is centred and 515 is its circumradius, exactly as the shell was.
  var CX = 550;
  var CY = 550;
  var OUTER = 515;
  var CROWN_OUTER = 85;
  var GAP = 3;

  // Bands for the two rings that are not ranks, and their cell counts. Both are
  // Owner-facing numbers, so they are named here rather than buried in a loop.
  var MOAT_BAND = 25;
  var VIP_BAND = 45;
  var MOAT_SEGMENTS = 8;
  // Four VIP boxes per octagon face (Owner, 2026-07-30): one box per face read as
  // a slab of floor, not as seating. 32 keeps them square-ish on a 45-unit band.
  var VIP_SEGMENTS = 32;

  var VISUAL_CROWN = 1;
  var VISUAL_MOAT = 2;
  var VISUAL_RANK_FIRST = 3;
  var VISUAL_VIP = 11;

  // ---- geometry (pure) ----

  function octRadius(angle, R) {
    var sector = Math.PI / 4;
    var half = sector / 2;
    var norm = ((angle % sector) + sector) % sector;
    return R * Math.cos(half) / Math.cos(norm - half);
  }

  function octPoint(cx, cy, angle, R) {
    var r = octRadius(angle, R);
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  }

  function ringSegmentPoints(cx, cy, innerR, outerR, startAngle, endAngle) {
    var STEPS = 12;
    var pts = [];
    var i, angle;
    for (i = 0; i <= STEPS; i++) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pts.push(octPoint(cx, cy, angle, outerR));
    }
    for (i = STEPS; i >= 0; i--) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pts.push(octPoint(cx, cy, angle, innerR));
    }
    return pts;
  }

  function pathFromPoints(pts) {
    if (!pts.length) { return ''; }
    var first = pts[0][0].toFixed(2) + ',' + pts[0][1].toFixed(2);
    var rest = [];
    for (var i = 1; i < pts.length; i++) {
      rest.push(pts[i][0].toFixed(2) + ',' + pts[i][1].toFixed(2));
    }
    return 'M ' + first + ' L ' + rest.join(' L ') + ' Z';
  }

  function ringSegmentPath(cx, cy, innerR, outerR, startAngle, endAngle) {
    return pathFromPoints(ringSegmentPoints(cx, cy, innerR, outerR, startAngle, endAngle));
  }

  function octagonPoints(cx, cy, R) {
    var pts = [];
    for (var i = 0; i < 8; i++) {
      var angle = i * Math.PI / 4;
      pts.push((cx + R * Math.cos(angle)).toFixed(2) + ',' + (cy + R * Math.sin(angle)).toFixed(2));
    }
    return pts.join(' ');
  }

  function segmentCentroid(cx, cy, innerR, outerR, startAngle, endAngle) {
    var midAngle = (startAngle + endAngle) / 2;
    var midR = (innerR + outerR) / 2;
    var r = octRadius(midAngle, midR);
    return { x: cx + r * Math.cos(midAngle), y: cy + r * Math.sin(midAngle) };
  }

  /**
   * The angular span of one cell, gap included, as the drawing loop computes it.
   * Kept here so anything that needs to re-find a cell's wedge (the online
   * beacon, a portrait clip) derives it from the same source as the floor
   * instead of guessing — that guessing is what broke the beacon.
   */
  function cellAngles(count, cell, outerR) {
    var sweep = (2 * Math.PI) / count;
    var offset = -Math.PI / 2 - sweep / 2;
    return {
      start: offset + cell * sweep + GAP / outerR,
      end: offset + (cell + 1) * sweep - GAP / outerR
    };
  }

  /**
   * Build the eleven-ring table. Rank counts and keys come from the backend's
   * geometry payload (`get_arena_geometry()`), which is the authority for
   * seating — so the floor and the seat map cannot disagree.
   */
  function ringTable(geometryRings) {
    var moatOuter = CROWN_OUTER + MOAT_BAND;
    var vipInner = OUTER - VIP_BAND;
    var ranks = (geometryRings || []).filter(function (r) {
      return r.kind === 'rank';
    }).sort(function (a, b) { return a.index - b.index; });
    var band = ranks.length ? (vipInner - moatOuter) / ranks.length : 0;

    var table = [{
      visual: VISUAL_CROWN, kind: 'crown', ring: 0, key: 'stage',
      inner: 0, outer: CROWN_OUTER, segments: 1
    }, {
      visual: VISUAL_MOAT, kind: 'moat', ring: null, key: 'moat',
      inner: CROWN_OUTER, outer: moatOuter, segments: MOAT_SEGMENTS
    }];
    ranks.forEach(function (ring, i) {
      table.push({
        visual: VISUAL_RANK_FIRST + i,
        kind: 'rank',
        ring: ring.index,
        key: ring.key,
        inner: moatOuter + i * band,
        outer: moatOuter + (i + 1) * band,
        segments: ring.segments
      });
    });
    table.push({
      visual: VISUAL_VIP, kind: 'vip', ring: null, key: 'vip_guests',
      inner: vipInner, outer: OUTER, segments: VIP_SEGMENTS
    });
    return table;
  }

  // ============================================================
  // THE RENDERED OCTAGON'S PUBLIC CONTRACT
  //
  // AN16, master task section 10: the page hands the octagon a region and
  // reads nothing of its internal SVG geometry.
  //
  // Everything above this line is plan-space arithmetic and never touches the
  // DOM. Everything below is the live side of the same component: the three
  // questions the PAGE is allowed to ask about where the octagon actually
  // landed, answered in viewport coordinates.
  //
  // Before this existed, the page-level placement code - the floor caption,
  // the band reserved above it, the rank ladder beside it - reached inside the
  // SVG and queried `.arena-cell[data-ring-kind="rank"]` for itself. Three
  // separate functions therefore knew that the octagon is made of cells, that
  // cells carry a ring kind, and what the kinds are called. Renaming an
  // attribute inside the octagon would have moved a caption in another file.
  //
  // A question NOT on this list is one the page has no business asking.
  // ============================================================

  /** The box every drawn cell of the octagon falls inside, or null. */
  function region(svg) {
    return boxOf(svg, '.arena-cell');
  }

  /** The box of the eight RANK rings alone - the floor the ladder names. */
  function rankRegion(svg) {
    return boxOf(svg, '.arena-cell[data-ring-kind="rank"]');
  }

  /**
   * The Sponsors corner: the vertical middle of the rightmost VIP cell.
   *
   * The Owner named this point on 2026-08-07 - the corner of the Sponsors cell
   * is to sit exactly between Chef de Partie and Sous Chef - and it is NOT the
   * middle of the octagon's bounding box. The camera is rotateX(42deg), so the
   * far half is compressed and the box's centre sits BELOW the right-hand
   * vertex: measured 439 against 423 at his own window, sixteen pixels of it.
   */
  function sponsorsCorner(svg) {
    var cells = svg ? svg.querySelectorAll('.arena-cell[data-ring-kind="vip"]') : [];
    var best = null, right = -Infinity;
    for (var i = 0; i < cells.length; i++) {
      var box = cells[i].getBoundingClientRect();
      if (!box.width || !box.height) { continue; }
      if (box.right > right) {
        right = box.right;
        best = { x: box.right, y: (box.top + box.bottom) / 2 };
      }
    }
    return best;
  }

  function boxOf(svg, selector) {
    var cells = svg ? svg.querySelectorAll(selector) : [];
    var top = Infinity, bottom = -Infinity, left = Infinity, right = -Infinity;
    for (var i = 0; i < cells.length; i++) {
      var box = cells[i].getBoundingClientRect();
      if (!box.width || !box.height) { continue; }
      if (box.top < top) { top = box.top; }
      if (box.bottom > bottom) { bottom = box.bottom; }
      if (box.left < left) { left = box.left; }
      if (box.right > right) { right = box.right; }
    }
    if (!isFinite(top) || !(right > left) || !(bottom > top)) { return null; }
    return { top: top, bottom: bottom, left: left, right: right,
             width: right - left, height: bottom - top };
  }

  global.ArenaOctagon = {
    CX: CX,
    CY: CY,
    OUTER: OUTER,
    CROWN_OUTER: CROWN_OUTER,
    GAP: GAP,
    VISUAL_CROWN: VISUAL_CROWN,
    VISUAL_MOAT: VISUAL_MOAT,
    VISUAL_RANK_FIRST: VISUAL_RANK_FIRST,
    VISUAL_VIP: VISUAL_VIP,
    octRadius: octRadius,
    octPoint: octPoint,
    ringSegmentPoints: ringSegmentPoints,
    ringSegmentPath: ringSegmentPath,
    octagonPoints: octagonPoints,
    segmentCentroid: segmentCentroid,
    cellAngles: cellAngles,
    ringTable: ringTable,
    // the live component's contract with the page (AN16)
    region: region,
    rankRegion: rankRegion,
    sponsorsCorner: sponsorsCorner
  };
})(window);
