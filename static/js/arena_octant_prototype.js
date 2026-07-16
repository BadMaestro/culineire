/*
 * Isolated Arena geometry prototype — intentionally not loaded by production.
 * One octant is generated from polar coordinates and can later be repeated
 * eight times around the same centre. Cells have no fill: live data owns them.
 */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  function polar(cx, cy, radius, angle) {
    return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
  }

  function pointString(point) {
    return point.x.toFixed(2) + ',' + point.y.toFixed(2);
  }

  function sectorCell(cx, cy, innerRadius, outerRadius, startAngle, endAngle) {
    return [
      polar(cx, cy, innerRadius, startAngle),
      polar(cx, cy, outerRadius, startAngle),
      polar(cx, cy, outerRadius, endAngle),
      polar(cx, cy, innerRadius, endAngle)
    ].map(pointString).join(' ');
  }

  function drawOctantSector(svg, options) {
    var config = Object.assign({
      cx: 240, cy: 240,
      innerRadius: 64, ringWidth: 28, ringCount: 5,
      cellsPerRing: 3, octantIndex: 0,
      stroke: '#8b7355', strokeWidth: 1.15
    }, options || {});
    var octant = Math.PI / 4;
    var start = -Math.PI / 2 + config.octantIndex * octant;
    var group = document.createElementNS(NS, 'g');
    group.setAttribute('data-arena-prototype', 'octant');
    group.setAttribute('fill', 'none');
    group.setAttribute('stroke', config.stroke);
    group.setAttribute('stroke-width', config.strokeWidth);
    group.setAttribute('vector-effect', 'non-scaling-stroke');

    for (var ring = 0; ring < config.ringCount; ring++) {
      var inner = config.innerRadius + ring * config.ringWidth;
      var outer = inner + config.ringWidth;
      for (var cell = 0; cell < config.cellsPerRing; cell++) {
        var a0 = start + octant * cell / config.cellsPerRing;
        var a1 = start + octant * (cell + 1) / config.cellsPerRing;
        var polygon = document.createElementNS(NS, 'polygon');
        polygon.setAttribute('points', sectorCell(config.cx, config.cy, inner, outer, a0, a1));
        polygon.setAttribute('data-ring', String(ring));
        polygon.setAttribute('data-cell', String(cell));
        group.appendChild(polygon);
      }
    }
    svg.appendChild(group);
    return group;
  }

  global.ArenaOctantPrototype = { polar: polar, sectorCell: sectorCell, drawOctantSector: drawOctantSector };
})(window);
