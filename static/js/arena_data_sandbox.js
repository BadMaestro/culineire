/* Sandbox-only Layer 2 binder. It accepts the public arena_state shape. */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';
  var previousSlots = Object.create(null);

  function centreSlugs(center) {
    var out = Object.create(null);
    ['challenger', 'opponent'].forEach(function (key) {
      if (center && center[key] && center[key].slug) { out[center[key].slug] = true; }
    });
    return out;
  }

  function buildAssignments(payload, geometry) {
    var assignments = [];
    var inCentre = centreSlugs(payload.center);
    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'rank') { return; }
      var chefs = (payload.rings && payload.rings[ring.key]) || [];
      var cell = 0;
      chefs.forEach(function (chef) {
        if (cell < ring.segments && chef && !inCentre[chef.slug]) {
          assignments.push({ ring: ring.index, cell: cell++, entity: chef, occupancy: 'chef', state: chef.in_battle ? 'in-battle' : 'online' });
        }
      });
    });
    var spectatorIndex = 0;
    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'spectator') { return; }
      for (var cell = 0; cell < ring.segments && spectatorIndex < ((payload.spectators || []).length); cell++) {
        assignments.push({ ring: ring.index, cell: cell, entity: payload.spectators[spectatorIndex++], occupancy: 'spectator', state: 'watching' });
      }
    });
    return assignments;
  }

  function stampStage(svg, payload) {
    var stage = svg.querySelector('[data-arena-prototype="stage"]');
    if (!stage) { return; }
    var center = payload.center || { type: 'open' };
    stage.setAttribute('data-stage-type', center.type || 'open');
    stage.setAttribute('data-state', center.type || 'open');
    var label = document.createElementNS(NS, 'text');
    label.setAttribute('class', 'arena-prototype-stage-label');
    label.setAttribute('x', stage.getAttribute('cx'));
    label.setAttribute('y', stage.getAttribute('cy'));
    label.setAttribute('text-anchor', 'middle');
    label.setAttribute('font-size', '7');
    label.textContent = center.name || (center.type || 'open').replace(/_/g, ' ');
    svg.appendChild(label);
  }

  function appendOccupant(svg, polygon, assignment) {
    var x = Number(polygon.getAttribute('data-centroid-x'));
    var y = Number(polygon.getAttribute('data-centroid-y'));
    var entity = assignment.entity || {};
    var group = document.createElementNS(NS, 'g');
    group.setAttribute('class', 'arena-prototype-occupant');
    group.setAttribute('transform', 'translate(' + x + ' ' + y + ')');
    group.setAttribute('data-entity-slug', entity.slug || 'spectator-' + assignment.ring + '-' + assignment.cell);
    var avatar = document.createElementNS(NS, 'image');
    avatar.setAttribute('x', '-6'); avatar.setAttribute('y', '-6');
    avatar.setAttribute('width', '12'); avatar.setAttribute('height', '12');
    avatar.setAttribute('href', entity.avatar_url || '');
    avatar.setAttribute('preserveAspectRatio', 'xMidYMid slice');
    group.appendChild(avatar);
    var label = document.createElementNS(NS, 'text');
    label.setAttribute('x', '0'); label.setAttribute('y', '12');
    label.setAttribute('text-anchor', 'middle'); label.setAttribute('font-size', '5');
    label.textContent = entity.name || entity.slug || 'Viewer';
    group.appendChild(label);
    svg.appendChild(group);
  }

  function bind(svg, payload, geometry) {
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-prototype-occupant, .arena-prototype-stage-label'), function (node) { node.remove(); });
    // A poll may move or remove an entity. Clear every transient cell attribute
    // before applying the next snapshot so a freed polygon cannot retain a
    // stale occupant, state, or highlight from the previous payload.
    Array.prototype.forEach.call(svg.querySelectorAll('[data-ring][data-cell]'), function (polygon) {
      polygon.removeAttribute('data-occupancy');
      polygon.removeAttribute('data-state');
      polygon.removeAttribute('data-entity-slug');
      polygon.removeAttribute('data-changed');
    });
    var nextSlots = Object.create(null);
    buildAssignments(payload, geometry).forEach(function (assignment) {
      var key = assignment.ring + ':' + assignment.cell;
      var polygon = svg.querySelector('[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]');
      if (!polygon) { return; }
      var identity = assignment.entity.slug || assignment.entity.name || key;
      var stateKey = identity + ':' + assignment.state;
      polygon.setAttribute('data-occupancy', assignment.occupancy);
      polygon.setAttribute('data-state', assignment.state);
      polygon.setAttribute('data-entity-slug', identity);
      polygon.setAttribute('data-changed', previousSlots[key] !== stateKey ? 'true' : 'false');
      nextSlots[key] = stateKey;
      appendOccupant(svg, polygon, assignment);
    });
    previousSlots = nextSlots;
    stampStage(svg, payload);
  }

  global.ArenaDataSandbox = { buildAssignments: buildAssignments, bind: bind };
})(window);
