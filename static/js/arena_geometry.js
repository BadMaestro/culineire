/*
 * Procedural Chef Battles Arena geometry.
 * Pure math only: no DOM access, rendering, sprites or live-data wiring.
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

  /**
   * Return one no-fill arena cell as four vertices.
   * `segmentIndex` may address any cell around the arena. The optional
   * `sides` argument is supplied by the live geometry contract. Cells divide
   * each straight octagonal edge through linear interpolation, never a curve.
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
    if (!Number.isInteger(sides) || sides < 3 || segmentsPerRing % sides !== 0) {
      throw new RangeError('segmentsPerRing must divide evenly across sides');
    }

    var cellsPerSide = segmentsPerRing / sides;
    var sideIndex = Math.floor(segmentIndex / cellsPerSide);
    var cellIndex = segmentIndex % cellsPerSide;
    // Half-side offset creates a flat top/bottom. Every cell on a side uses
    // lerp along one chord, preserving the actual polygon instead of a circle.
    var orientationOffset = -Math.PI / 2 - (Math.PI / sides);
    var angle0 = orientationOffset + (Math.PI * 2 * sideIndex / sides);
    var angle1 = orientationOffset + (Math.PI * 2 * (sideIndex + 1) / sides);
    // Ring 0 is the centre stage. Ring 1 starts beyond its reserved radius,
    // leaving a real hole for the crown/VS medallion in the renderer.
    var innerRadius = ringIndex === 0 ? 0 : innerRadiusOffset + (ringIndex - 1) * radiusStep;
    var outerRadius = ringIndex === 0 ? innerRadiusOffset : innerRadius + radiusStep;
    var cellStart = cellIndex / cellsPerSide;
    var cellEnd = (cellIndex + 1) / cellsPerSide;
    var innerStart = lerp(polar(centerX, centerY, innerRadius, angle0), polar(centerX, centerY, innerRadius, angle1), cellStart);
    var innerEnd = lerp(polar(centerX, centerY, innerRadius, angle0), polar(centerX, centerY, innerRadius, angle1), cellEnd);
    var outerStart = lerp(polar(centerX, centerY, outerRadius, angle0), polar(centerX, centerY, outerRadius, angle1), cellStart);
    var outerEnd = lerp(polar(centerX, centerY, outerRadius, angle0), polar(centerX, centerY, outerRadius, angle1), cellEnd);

    return [innerStart, outerStart, outerEnd, innerEnd];
  }

  global.ArenaGeometry = { polar: polar, lerp: lerp, cellCentroid: cellCentroid, cellVertices: cellVertices };
})(window);
