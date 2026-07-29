/**
 * Shared octagon floor template — same grid as the Sponsors puzzle.
 *
 * Layout (outer → inner):
 *   Ring 6 – 60 cells
 *   Ring 5 – 50 cells
 *   Ring 4 – 40 cells
 *   Ring 3 – 30 cells
 *   Ring 2 – 20 cells
 *   Ring 1 – 10 cells
 *   Centre – 1 octagon
 *
 * Arena and Sponsors both draw from these constants so cell counts, gaps,
 * colours and path maths stay identical. Data (sponsors vs chefs) is bound
 * by the caller.
 */
(function (global) {
  'use strict';

  var GAP = 3;

  // Radii of each ring boundary (inner edge, then outer edge per ring).
  // Canonical size is centred at (550, 550) with outer circumradius 515 —
  // callers scale into their own SVG centre/size.
  var RING_RADII = {
    centre: [0, 85],
    1: [85, 145],
    2: [145, 235],
    3: [235, 325],
    4: [325, 400],
    5: [400, 460],
    6: [460, 515]
  };

  var RING_COUNTS = { 1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60 };

  var RING_COLOURS = {
    available: {
      6: '#f4f1ec', 5: '#ede8df', 4: '#e4ddd1', 3: '#d8d0c0',
      2: '#ccc1aa', 1: '#bfb49a', 0: '#6c6054'
    },
    reserved: {
      6: '#faf0d8', 5: '#f5e6c8', 4: '#f2ddb2', 3: '#efd49c',
      2: '#ebca86', 1: '#e6c070', 0: '#c8942a'
    },
    // The Arena floor, measured off the Owner-approved mockup
    // (docs mockups/arena.png, horizontal scanline through the octagon centre,
    // median of a 5x5 window per sample). Sponsors keep `available` unchanged:
    // that table paints /sponsors/ and is not ours to repaint.
    arena: {
      6: '#e6d2ba', 5: '#e6d1b9', 4: '#dbc0a3', 3: '#b49d80',
      2: '#b59d81', 1: '#9d886c', 0: '#9e886c'
    },
    sold: {
      6: '#ddd8ce', 5: '#cdc7ba', 4: '#b8b0a0', 3: '#a49888',
      2: '#907e6c', 1: '#786454', 0: '#3a2e28'
    }
  };

  var TEMPLATE_OUTER = RING_RADII[6][1];
  var TEMPLATE_CENTRE = 550;

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
    var i, angle, pt;
    for (i = 0; i <= STEPS; i++) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pt = octPoint(cx, cy, angle, outerR);
      pts.push(pt);
    }
    for (i = STEPS; i >= 0; i--) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pt = octPoint(cx, cy, angle, innerR);
      pts.push(pt);
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

  /**
   * Full octagon polygon points. Vertices at 0°, 45°, … — matches octRadius()
   * where R is the circumradius (same as sponsors_puzzle.js).
   */
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
   * Scale factor so template outer radius (515) lands on targetOuterR.
   */
  function scaleFor(targetOuterR) {
    return targetOuterR / TEMPLATE_OUTER;
  }

  function scaledRadii(scale) {
    var out = { centre: [0, RING_RADII.centre[1] * scale] };
    for (var ring = 1; ring <= 6; ring++) {
      out[ring] = [RING_RADII[ring][0] * scale, RING_RADII[ring][1] * scale];
    }
    return out;
  }

  global.OctagonFloorTemplate = {
    GAP: GAP,
    RING_RADII: RING_RADII,
    RING_COUNTS: RING_COUNTS,
    RING_COLOURS: RING_COLOURS,
    TEMPLATE_OUTER: TEMPLATE_OUTER,
    TEMPLATE_CENTRE: TEMPLATE_CENTRE,
    octRadius: octRadius,
    octPoint: octPoint,
    ringSegmentPoints: ringSegmentPoints,
    ringSegmentPath: ringSegmentPath,
    pathFromPoints: pathFromPoints,
    octagonPoints: octagonPoints,
    segmentCentroid: segmentCentroid,
    scaleFor: scaleFor,
    scaledRadii: scaledRadii
  };
}(typeof window !== 'undefined' ? window : this));
