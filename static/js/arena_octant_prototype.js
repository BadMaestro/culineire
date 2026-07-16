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

  function drawOctantSector(svg, geometry, options) {
    if (!geometry || !Number.isInteger(geometry.sides) || !Array.isArray(geometry.rings)) {
      throw new TypeError('geometry must provide integer sides and an ordered rings array.');
    }
    var config = Object.assign({
      cx: 240, cy: 240,
      ringWidth: 28, stageRadius: 64, cellsPerOctant: 1, octantIndex: 0, startRingIndex: 1,
      stroke: '#8b7355', strokeWidth: 1.15
    }, options || {});
    if (!global.ArenaGeometry) {
      throw new Error('ArenaGeometry must load before the octant prototype.');
    }
    var totalSegments = config.cellsPerOctant * geometry.sides;
    var group = document.createElementNS(NS, 'g');
    group.setAttribute('data-arena-prototype', 'octant');
    group.setAttribute('fill', 'none');
    group.setAttribute('stroke', config.stroke);
    group.setAttribute('stroke-width', config.strokeWidth);
    group.setAttribute('vector-effect', 'non-scaling-stroke');

    // `stage` is one central medallion, not eight degenerate wedges.
    // The final render layer owns that dedicated element.
    for (var ring = config.startRingIndex; ring < geometry.rings.length; ring++) {
      for (var cell = 0; cell < config.cellsPerOctant; cell++) {
        var segmentIndex = config.octantIndex * config.cellsPerOctant + cell;
        var polygon = document.createElementNS(NS, 'polygon');
        polygon.setAttribute('points', global.ArenaGeometry.cellVertices(
          config.cx, config.cy, ring, segmentIndex, geometry.rings.length, totalSegments, config.ringWidth, geometry.sides, config.stageRadius
        ).map(pointString).join(' '));
        polygon.setAttribute('data-ring', String(geometry.rings[ring].index));
        polygon.setAttribute('data-ring-key', geometry.rings[ring].key || '');
        polygon.setAttribute('data-cell', String(cell));
        polygon.setAttribute('vector-effect', 'non-scaling-stroke');
        group.appendChild(polygon);
      }
    }
    svg.appendChild(group);
    return group;
  }

  function drawStage(svg, geometry, config) {
    var stage = document.createElementNS(NS, 'circle');
    stage.setAttribute('cx', config.cx);
    stage.setAttribute('cy', config.cy);
    stage.setAttribute('r', config.stageRadius);
    stage.setAttribute('fill', 'none');
    stage.setAttribute('stroke', config.stroke);
    stage.setAttribute('stroke-width', config.strokeWidth);
    stage.setAttribute('vector-effect', 'non-scaling-stroke');
    stage.setAttribute('data-ring', String(geometry.rings[0].index));
    stage.setAttribute('data-ring-key', geometry.rings[0].key);
    stage.setAttribute('data-arena-prototype', 'stage');
    svg.appendChild(stage);
    return stage;
  }

  function drawFullArenaGrid(svg, geometry, options) {
    var config = Object.assign({
      cx: 240, cy: 240, ringWidth: 13, stageRadius: 66,
      cellsPerOctant: 3, stroke: '#8b7355', strokeWidth: 1.15
    }, options || {});
    drawStage(svg, geometry, config);
    for (var octantIndex = 0; octantIndex < geometry.sides; octantIndex++) {
      drawOctantSector(svg, geometry, Object.assign({}, config, { octantIndex: octantIndex }));
    }
  }

  global.ArenaOctantPrototype = {
    drawOctantSector: drawOctantSector,
    drawFullArenaGrid: drawFullArenaGrid
  };
})(window);
