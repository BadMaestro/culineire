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

  /**
   * Return one no-fill arena cell as four vertices.
   * `segmentIndex` may address any sector around the arena; callers decide
   * how many segments form a ring through `segmentsPerRing`.
   */
  function cellVertices(centerX, centerY, ringIndex, segmentIndex, ringCount, segmentsPerRing, radiusStep) {
    if (!Number.isInteger(ringIndex) || ringIndex < 0 || ringIndex >= ringCount) {
      throw new RangeError('ringIndex must be inside ringCount');
    }
    if (!Number.isInteger(segmentIndex) || segmentIndex < 0 || segmentIndex >= segmentsPerRing) {
      throw new RangeError('segmentIndex must be inside segmentsPerRing');
    }
    if (!(radiusStep > 0)) {
      throw new RangeError('radiusStep must be positive');
    }

    var startAngle = -Math.PI / 2 + (Math.PI * 2 * segmentIndex / segmentsPerRing);
    var endAngle = -Math.PI / 2 + (Math.PI * 2 * (segmentIndex + 1) / segmentsPerRing);
    var innerRadius = ringIndex * radiusStep;
    var outerRadius = (ringIndex + 1) * radiusStep;

    return [
      polar(centerX, centerY, innerRadius, startAngle),
      polar(centerX, centerY, outerRadius, startAngle),
      polar(centerX, centerY, outerRadius, endAngle),
      polar(centerX, centerY, innerRadius, endAngle)
    ];
  }

  global.ArenaGeometry = { polar: polar, cellVertices: cellVertices };
})(window);
