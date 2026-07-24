/*
 * Procedural Chef Battles Arena geometry.
 * Pure math only: no DOM access, rendering, sprites or live-data wiring.
 *
 * Owner 2026-07-24: rank rings may use uneven cells-per-side (mockup counts
 * 9/10/15… are not multiples of 8). Spectators use ovalSeats(), not polar
 * cellVertices on the floor grid.
 */
(function (global) {
  'use strict';

  function polar(centerX, centerY, radius, angle) {
    return {
      x: centerX + radius * Math.cos(angle),
      y: centerY + radius * Math.sin(angle)
    };
  }

  function lerp(start, end, amount) {
    return {
      x: start.x + (end.x - start.x) * amount,
      y: start.y + (end.y - start.y) * amount
    };
  }

  function cellCentroid(vertices) {
    if (!Array.isArray(vertices) || vertices.length === 0) {
      throw new TypeError('cellCentroid requires one or more vertices');
    }
    var total = vertices.reduce(function (total, point) {
      total.x += point.x;
      total.y += point.y;
      return total;
    }, { x: 0, y: 0 });
    return { x: total.x / vertices.length, y: total.y / vertices.length };
  }

  /** Distribute `total` cells across `sides` (first remainder sides get +1). */
  function cellsPerSideList(total, sides) {
    var base = Math.floor(total / sides);
    var rem = total % sides;
    var list = [];
    for (var i = 0; i < sides; i++) {
      list.push(base + (i < rem ? 1 : 0));
    }
    return list;
  }

  /**
   * Map a flat segmentIndex onto {sideIndex, cellIndex, cellsOnSide}.
   */
  function locateSegment(segmentIndex, segmentsPerRing, sides) {
    var perSide = cellsPerSideList(segmentsPerRing, sides);
    var remaining = segmentIndex;
    for (var side = 0; side < sides; side++) {
      if (remaining < perSide[side]) {
        return { sideIndex: side, cellIndex: remaining, cellsOnSide: perSide[side] };
      }
      remaining -= perSide[side];
    }
    throw new RangeError('segmentIndex must be inside segmentsPerRing');
  }

  /**
   * Return one no-fill arena cell as four vertices.
   * Cells divide each straight octagonal edge through linear interpolation.
   * Uneven segments-per-ring are allowed (Owner mockup chef counts).
   */
  function cellVertices(centerX, centerY, ringIndex, segmentIndex, ringCount, segmentsPerRing, radiusStep, sides, innerRadiusOffset) {
    sides = sides || 8;
    innerRadiusOffset = innerRadiusOffset || 0;
    if (!Number.isInteger(ringIndex) || ringIndex < 0 || ringIndex >= ringCount) {
      throw new RangeError('ringIndex must be inside ringCount');
    }
    if (!Number.isInteger(segmentIndex) || segmentIndex < 0 || segmentIndex >= segmentsPerRing) {
      throw new RangeError('segmentIndex must be inside segmentsPerRing');
    }
    if (!(radiusStep > 0)) {
      throw new RangeError('radiusStep must be positive');
    }
    if (innerRadiusOffset < 0) {
      throw new RangeError('innerRadiusOffset must not be negative');
    }
    if (!Number.isInteger(sides) || sides < 3) {
      throw new RangeError('sides must be an integer >= 3');
    }

    var loc = locateSegment(segmentIndex, segmentsPerRing, sides);
    var sideIndex = loc.sideIndex;
    var cellIndex = loc.cellIndex;
    var cellsOnSide = Math.max(1, loc.cellsOnSide);
    // Half-side offset creates a flat top/bottom.
    var orientationOffset = -Math.PI / 2 - (Math.PI / sides);
    var angle0 = orientationOffset + (Math.PI * 2 * sideIndex / sides);
    var angle1 = orientationOffset + (Math.PI * 2 * (sideIndex + 1) / sides);
    var innerRadius = ringIndex === 0 ? 0 : innerRadiusOffset + (ringIndex - 1) * radiusStep;
    var outerRadius = ringIndex === 0 ? innerRadiusOffset : innerRadius + radiusStep;
    var cellStart = cellIndex / cellsOnSide;
    var cellEnd = (cellIndex + 1) / cellsOnSide;
    var innerStart = lerp(polar(centerX, centerY, innerRadius, angle0), polar(centerX, centerY, innerRadius, angle1), cellStart);
    var innerEnd = lerp(polar(centerX, centerY, innerRadius, angle0), polar(centerX, centerY, innerRadius, angle1), cellEnd);
    var outerStart = lerp(polar(centerX, centerY, outerRadius, angle0), polar(centerX, centerY, outerRadius, angle1), cellStart);
    var outerEnd = lerp(polar(centerX, centerY, outerRadius, angle0), polar(centerX, centerY, outerRadius, angle1), cellEnd);

    return [innerStart, outerStart, outerEnd, innerEnd];
  }

  /**
   * Spectator seats on an oval around the chef octagon (Owner mockup).
   * rowsBySide: {top, right, bottom, left} — 2/3/2/3 on the mockup.
   * Returns [{side, row, cell, ring, x, y, r}] in plan space.
   *
   * `ring` is a synthetic index: 100 + side*10 + row (stable for ArenaSeat).
   */
  function ovalSeats(centerX, centerY, floorOuterRadius, rowsBySide, seatPitch) {
    rowsBySide = rowsBySide || { top: 2, right: 3, bottom: 2, left: 3 };
    seatPitch = seatPitch || Math.max(14, floorOuterRadius * 0.055);
    var gap = floorOuterRadius * 0.08;
    var sides = [
      { key: 'top', rows: rowsBySide.top || 0, a0: -Math.PI * 0.75, a1: -Math.PI * 0.25 },
      { key: 'right', rows: rowsBySide.right || 0, a0: -Math.PI * 0.25, a1: Math.PI * 0.25 },
      { key: 'bottom', rows: rowsBySide.bottom || 0, a0: Math.PI * 0.25, a1: Math.PI * 0.75 },
      { key: 'left', rows: rowsBySide.left || 0, a0: Math.PI * 0.75, a1: Math.PI * 1.25 }
    ];
    var sideIndex = { top: 0, right: 1, bottom: 2, left: 3 };
    var out = [];
    sides.forEach(function (side) {
      for (var row = 0; row < side.rows; row++) {
        var radius = floorOuterRadius + gap + (row + 0.5) * seatPitch * 1.15;
        // Ellipse: stretch X slightly so the stand reads as an oval, not a circle.
        var rx = radius * 1.08;
        var ry = radius * 0.92;
        var arc = side.a1 - side.a0;
        var arcLen = Math.abs(arc) * ((rx + ry) / 2);
        var count = Math.max(4, Math.round(arcLen / seatPitch));
        var ringId = 100 + sideIndex[side.key] * 10 + row;
        for (var cell = 0; cell < count; cell++) {
          var t = (cell + 0.5) / count;
          var angle = side.a0 + arc * t;
          out.push({
            side: side.key,
            row: row,
            cell: cell,
            ring: ringId,
            x: centerX + rx * Math.cos(angle),
            y: centerY + ry * Math.sin(angle),
            r: seatPitch * 0.42
          });
        }
      }
    });
    return out;
  }

  global.ArenaGeometry = {
    polar: polar,
    lerp: lerp,
    cellCentroid: cellCentroid,
    cellVertices: cellVertices,
    cellsPerSideList: cellsPerSideList,
    ovalSeats: ovalSeats
  };
})(window);
