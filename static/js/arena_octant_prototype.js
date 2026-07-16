/*
 * Isolated Arena geometry prototype — intentionally not loaded by production.
 * One octant is generated from polar coordinates and can later be repeated
 * eight times around the same centre. Cells have no fill: live data owns them.
 */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  function pointString(point) {
    return point.x.toFixed(2) + ',' + point.y.toFixed(2);
  }

  function drawOctantSector(svg, options) {
    var config = Object.assign({
      cx: 240, cy: 240,
      ringWidth: 28, ringCount: 5,
      cellsPerRing: 3, octantIndex: 0,
      stroke: '#8b7355', strokeWidth: 1.15
    }, options || {});
    if (!global.ArenaGeometry) {
      throw new Error('ArenaGeometry must load before the octant prototype.');
    }
    var octant = Math.PI / 4;
    var totalSegments = config.cellsPerRing * 8;
    var group = document.createElementNS(NS, 'g');
    group.setAttribute('data-arena-prototype', 'octant');
    group.setAttribute('fill', 'none');
    group.setAttribute('stroke', config.stroke);
    group.setAttribute('stroke-width', config.strokeWidth);
    group.setAttribute('vector-effect', 'non-scaling-stroke');

    for (var ring = 0; ring < config.ringCount; ring++) {
      for (var cell = 0; cell < config.cellsPerRing; cell++) {
        var segmentIndex = config.octantIndex * config.cellsPerRing + cell;
        var polygon = document.createElementNS(NS, 'polygon');
        polygon.setAttribute('points', global.ArenaGeometry.cellVertices(
          config.cx, config.cy, ring, segmentIndex, config.ringCount, totalSegments, config.ringWidth
        ).map(pointString).join(' '));
        polygon.setAttribute('data-ring', String(ring));
        polygon.setAttribute('data-cell', String(cell));
        group.appendChild(polygon);
      }
    }
    svg.appendChild(group);
    return group;
  }

  global.ArenaOctantPrototype = { drawOctantSector: drawOctantSector };
})(window);
