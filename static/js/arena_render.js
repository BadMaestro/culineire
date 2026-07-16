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

  function radiusStepFor(geometry) {
    var usable = (SVG_SIZE / 2) - OUTER_MARGIN - STAGE_RADIUS;
    return usable / Math.max(1, geometry.rings.length - 1);
  }

  /* ---------------------------------------------------------------- */
  /* Grid — drawn once from geometry, then only re-stamped by bind()   */
  /* ---------------------------------------------------------------- */

  function drawGrid(svg, geometry) {
    var step = radiusStepFor(geometry);
    var defs = el('defs', {});
    var cells = el('g', { 'data-arena-layer': 'cells' });
    var hints = el('g', { 'data-arena-layer': 'hints' });
    var stageRing = geometry.rings[0];

    geometry.rings.forEach(function (ring) {
      if (ring.index === 0) { return; }
      for (var segment = 0; segment < ring.segments; segment++) {
        var vertices = global.ArenaGeometry.cellVertices(
          SVG_SIZE / 2, SVG_SIZE / 2, ring.index, segment,
          geometry.rings.length, ring.segments, step, geometry.sides, STAGE_RADIUS
        );
        var centroid = global.ArenaGeometry.cellCentroid(vertices);
        var shape = inset(vertices, centroid);
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

        // A free seat carries a "+", as the legacy floor did: an empty arena
        // should read as an invitation, not as a dead grid. bind() hides it
        // the moment the seat is taken.
        var span = Math.max(
          Math.abs(shape[1].x - shape[0].x), Math.abs(shape[1].y - shape[0].y),
          Math.abs(shape[2].x - shape[1].x), Math.abs(shape[2].y - shape[1].y)
        );
        var hint = el('text', {
          x: centroid.x.toFixed(2), y: centroid.y.toFixed(2),
          'text-anchor': 'middle', 'dominant-baseline': 'central',
          'font-size': Math.min(7, Math.max(3.5, span * 0.4)).toFixed(1),
          'pointer-events': 'none',
          'data-ring': String(ring.index),
          'data-cell': String(segment),
          'data-ring-kind': ring.kind || 'unknown',
          'data-occupancy': 'empty',
          class: 'arena-cell-hint'
        });
        hint.textContent = '+';
        hints.appendChild(hint);

        // One clip path per cell, reused by whoever occupies it. Avatars are
        // clipped to the cell outline so an occupant fills its tile instead of
        // floating as a square inside it.
        var clip = el('clipPath', { id: 'arena-clip-' + ring.index + '-' + segment });
        clip.appendChild(el('polygon', { points: shape.map(pointString).join(' ') }));
        defs.appendChild(clip);
      }
    });

    svg.appendChild(defs);
    svg.appendChild(cells);
    svg.appendChild(hints);
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
    svg.appendChild(el('g', { 'data-arena-layer': 'occupants' }));
    svg.appendChild(el('g', { 'data-arena-layer': 'centre' }));
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
    var index = 0;
    geometry.rings.forEach(function (ring) {
      if (ring.kind !== 'spectator') { return; }
      for (var cell = 0; cell < ring.segments && index < spectators.length; cell++) {
        assignments.push({
          ring: ring.index, cell: cell, entity: spectators[index++],
          occupancy: 'spectator', state: 'watching'
        });
      }
    });

    return assignments;
  }

  function initialOf(entity) {
    var source = (entity.name || entity.slug || '').trim();
    return source ? source.charAt(0).toUpperCase() : '?';
  }

  function appendOccupant(svg, layer, assignment) {
    var entity = assignment.entity || {};
    var selector = '[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]';
    var polygon = svg.querySelector('polygon' + selector);
    if (!polygon) { return; }

    var box = polygon.getBBox();
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
    Array.prototype.forEach.call(svg.querySelectorAll('polygon[data-ring]'), function (polygon) {
      polygon.setAttribute('data-occupancy', 'empty');
      polygon.setAttribute('data-state', 'idle');
      polygon.removeAttribute('data-entity-slug');
      polygon.chefRecord = null;
    });
    // A seat freed by this poll gets its "+" back.
    Array.prototype.forEach.call(svg.querySelectorAll('.arena-cell-hint'), function (hint) {
      hint.setAttribute('data-occupancy', 'empty');
    });

    buildAssignments(payload, geometry).forEach(function (assignment) {
      var polygon = svg.querySelector('polygon[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]');
      if (!polygon) { return; }
      var entity = assignment.entity;
      polygon.setAttribute('data-occupancy', assignment.occupancy);
      polygon.setAttribute('data-state', assignment.state);
      polygon.setAttribute('data-entity-slug', entity.slug || '');
      polygon.chefRecord = assignment.occupancy === 'spectator' ? asSpectator(entity) : entity;

      var hint = svg.querySelector('.arena-cell-hint[data-ring="' + assignment.ring + '"][data-cell="' + assignment.cell + '"]');
      if (hint) { hint.setAttribute('data-occupancy', assignment.occupancy); }

      appendOccupant(svg, occupants, assignment);
    });

    stampStage(svg, payload.center || { type: 'empty' });
  }

  function asSpectator(spectator) {
    return {
      name: spectator.name, slug: spectator.slug, avatar_url: spectator.avatar_url,
      rank_label: 'Spectator', rating: spectator.tokens + ' tokens',
      in_battle: false, is_online: false, is_spectator: true
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
    stage.setAttribute('data-centre-key', global.ArenaDeck ? global.ArenaDeck.centreKey(center) : 'empty');
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

  function attachEvents(svg) {
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
      var polygon = event.target.closest && event.target.closest('polygon[data-ring]');
      if (!polygon || !polygon.chefRecord) { hideTooltip(); return; }
      event.stopPropagation();
      fireRipple(svg, event);
      showTooltip(polygon.chefRecord, polygon);
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
        if (payload.geometry) { bind(svg, payload, payload.geometry); }
        if (global.ArenaDeck) { global.ArenaDeck.refresh(payload); }
        if (global.ArenaBattleRoom) { global.ArenaBattleRoom.maybeCelebrate(payload.latest_result); }
      })
      .catch(function () { /* a dropped poll is retried on the next tick */ });
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
