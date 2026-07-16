/*
 * Dark-launch entry point for /chef-battle/arena/?proto=1.
 * Uses the frozen arena_data and arena/state/ contracts only.  The default
 * arena continues to load arena_puzzle.js and never executes this file.
 */
(function () {
  'use strict';

  var POLL_INTERVAL = 10000;
  var SVG_SIZE = 1000;
  var STAGE_RADIUS = 76;
  var OUTER_MARGIN = 36;

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function readInitialPayload() {
    var node = document.getElementById('arena-data-json');
    if (!node) { return null; }
    try { return JSON.parse(node.textContent); } catch (error) { return null; }
  }

  function clearGrid(svg) {
    while (svg.firstChild) { svg.removeChild(svg.firstChild); }
  }

  function drawGrid(svg, payload) {
    var geometry = payload && payload.geometry;
    if (!geometry || !Array.isArray(geometry.rings) || !geometry.rings.length) { return false; }
    var usableRadius = (SVG_SIZE / 2) - OUTER_MARGIN - STAGE_RADIUS;
    var ringWidth = usableRadius / Math.max(1, geometry.rings.length - 1);
    clearGrid(svg);
    window.ArenaOctantPrototype.drawFullArenaGrid(svg, geometry, {
      cx: SVG_SIZE / 2,
      cy: SVG_SIZE / 2,
      stageRadius: STAGE_RADIUS,
      ringWidth: ringWidth,
      stroke: '#8b7355',
      strokeWidth: 1.1
    });
    return true;
  }

  function render(svg, payload) {
    if (!payload || !payload.geometry) { return; }
    if (!svg.querySelector('[data-arena-prototype="stage"]')) {
      if (!drawGrid(svg, payload)) { return; }
    }
    window.ArenaDataSandbox.bind(svg, payload, payload.geometry);
  }

  function poll(svg) {
    fetch('/chef-battle/arena/state/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrfToken() }
    })
      .then(function (response) { return response.ok ? response.json() : null; })
      .then(function (payload) { if (payload) { render(svg, payload); } })
      .catch(function () {});
  }

  document.addEventListener('DOMContentLoaded', function () {
    var svg = document.getElementById('arena-prototype');
    var payload = readInitialPayload();
    if (!svg || !payload || !window.ArenaGeometry || !window.ArenaOctantPrototype || !window.ArenaDataSandbox) { return; }
    render(svg, payload);
    window.setInterval(function () { poll(svg); }, POLL_INTERVAL);
  });
})();
