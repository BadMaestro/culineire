/*
 * Arena lamp console — the Owner's own control over where the lamps stand.
 *
 * Built 2026-07-31 on his order, after the throwaway plan he called the ideal
 * way to control them. This is that plan, on the arena page: he drags a lamp on
 * a small schematic and the real floor answers immediately.
 *
 * Three things it deliberately does NOT do:
 *
 *  - It does not touch the server. Positions live in localStorage, in his own
 *    browser. Persisting them would mean a schema change, and a schema change
 *    needs his explicit word every time (AGENTS.md section 8).
 *  - It does not widen access. The arena page is staff/superuser only, so
 *    anything on it already is; nothing here loosens that, and the panel adds no
 *    route of its own.
 *  - It does not draw the floor. It writes a layout and asks the renderer to
 *    repaint, so there is exactly one piece of code that knows how a lamp is
 *    drawn, and it is arena_render.js.
 *
 * localStorage is what makes it usable at all: the arena reloads its payload
 * every 30 seconds, and without a stored layout every adjustment would be wiped
 * by the next poll.
 */
(function (global) {
  'use strict';

  var KEY = 'culineire.arena.lamps.v1';
  var GROUPS = [
    { key: 'outer', label: '1 — внешние на плите', colour: '#ffb347' },
    { key: 'inner', label: '2 — внутренние на плите', colour: '#ff5f5f' },
    { key: 'moat', label: '3 — во рву (бегущее пятно)', colour: '#57c8ff' }
  ];

  // The schematic's own space: the crown plate's circumradius is 1, drawn at
  // this many pixels, around the centre of a 300x300 box.
  var UNIT = 82;
  var K = 1.28;
  var C = 150;

  var NS = 'http://www.w3.org/2000/svg';
  var state = null;
  var panel = null;
  var plan = null;

  function defaults() {
    var d = (global.ArenaRender && global.ArenaRender.lampDefaults) || {};
    return JSON.parse(JSON.stringify({
      outer: d.outer || { r: 1.128, deg: 0 },
      inner: d.inner || { r: 0.9475, deg: 22.7 },
      moat: d.moat || { r: 1.3161, deg: 0.2 }
    }));
  }

  function load() {
    var base = defaults();
    try {
      var raw = global.localStorage && global.localStorage.getItem(KEY);
      if (!raw) { return base; }
      var saved = JSON.parse(raw);
      for (var i = 0; i < GROUPS.length; i++) {
        var k = GROUPS[i].key;
        if (saved[k] && isFinite(saved[k].r) && isFinite(saved[k].deg)) {
          base[k] = { r: saved[k].r, deg: saved[k].deg };
        }
      }
    } catch (error) {
      // A corrupt or blocked store is not a reason to lose the arena: fall back
      // to the defaults rather than throwing on the way in.
    }
    return base;
  }

  function save() {
    try {
      if (global.localStorage) { global.localStorage.setItem(KEY, JSON.stringify(state)); }
    } catch (error) { /* private mode, quota — the layout still works this session */ }
  }

  function push() {
    global.ArenaLampLayout = state;
    if (global.ArenaRender && global.ArenaRender.applyLampLayout) {
      global.ArenaRender.applyLampLayout();
    }
  }

  function svgEl(name, attrs) {
    var node = document.createElementNS(NS, name);
    for (var k in attrs) { if (attrs.hasOwnProperty(k)) { node.setAttribute(k, attrs[k]); } }
    return node;
  }

  function octagon(r) {
    var pts = [];
    for (var i = 0; i < 8; i++) {
      var a = i * Math.PI / 4;
      pts.push((C + r * K * Math.cos(a)).toFixed(1) + ',' + (C + r * K * Math.sin(a)).toFixed(1));
    }
    return pts.join(' ');
  }

  function drawPlan() {
    while (plan.firstChild) { plan.removeChild(plan.firstChild); }
    plan.appendChild(svgEl('polygon', { points: octagon(125), fill: '#2a2216', stroke: '#5a4a34', 'stroke-width': 1 }));
    plan.appendChild(svgEl('polygon', { points: octagon(108.5), fill: '#2c2318', stroke: '#6a5a44', 'stroke-width': 1 }));
    plan.appendChild(svgEl('polygon', { points: octagon(88), fill: '#1d180f', stroke: '#6a5a44', 'stroke-width': 1 }));
    plan.appendChild(svgEl('polygon', { points: octagon(UNIT * 1.006), fill: '#20342a', stroke: '#e0b34a', 'stroke-width': 2 }));

    for (var g = 0; g < GROUPS.length; g++) {
      var group = GROUPS[g];
      var set = state[group.key];
      for (var i = 0; i < 8; i++) {
        var a = (i * 45 + set.deg) * Math.PI / 180;
        var dot = svgEl('circle', {
          cx: (C + set.r * UNIT * K * Math.cos(a)).toFixed(1),
          cy: (C + set.r * UNIT * K * Math.sin(a)).toFixed(1),
          r: 4.6, fill: group.colour, class: 'arena-lampc__dot'
        });
        dot.setAttribute('data-lamp-group', group.key);
        plan.appendChild(dot);
      }
    }
    readout();
  }

  function readout() {
    for (var g = 0; g < GROUPS.length; g++) {
      var key = GROUPS[g].key;
      var node = panel.querySelector('[data-lamp-readout="' + key + '"]');
      if (node) {
        node.textContent = 'r = ' + (state[key].r * UNIT).toFixed(2) +
          '  (' + state[key].r.toFixed(4) + ' x 82)   угол = ' + state[key].deg.toFixed(1) + '°';
      }
    }
    var box = panel.querySelector('[data-lamp-copy]');
    if (box) {
      box.value = 'ЛАМПЫ\n' + GROUPS.map(function (grp) {
        return grp.label + ': r = ' + (state[grp.key].r).toFixed(4) + ' x 82, угол = ' + state[grp.key].deg.toFixed(1);
      }).join('\n');
    }
  }

  var dragging = null;

  function pointerToLayout(event) {
    var box = plan.getBoundingClientRect();
    var x = (event.clientX - box.left) * (300 / box.width) - C;
    var y = (event.clientY - box.top) * (300 / box.height) - C;
    var deg = Math.atan2(y, x) * 180 / Math.PI;
    return {
      // Clamped so a slip of the hand cannot throw a lamp off the floor.
      r: Math.max(0.3, Math.min(2.2, Math.sqrt(x * x + y * y) / K / UNIT)),
      // Eight-fold symmetry: only the offset inside one face is free.
      deg: ((deg % 45) + 45) % 45
    };
  }

  function build() {
    panel = document.createElement('aside');
    panel.className = 'arena-lampc';
    panel.setAttribute('aria-label', 'Управление лампами арены');
    panel.innerHTML =
      '<button type="button" class="arena-lampc__toggle" data-lamp-toggle>Лампы</button>' +
      '<div class="arena-lampc__body" data-lamp-body hidden>' +
      '<p class="arena-lampc__hint">Тяните лампу — вся восьмёрка едет вместе. Арена меняется сразу.</p>' +
      '<svg class="arena-lampc__plan" viewBox="0 0 300 300" data-lamp-plan></svg>' +
      GROUPS.map(function (grp) {
        return '<p class="arena-lampc__row"><span class="arena-lampc__sw" style="background:' + grp.colour + '"></span>' +
          grp.label + '<br><span class="arena-lampc__val" data-lamp-readout="' + grp.key + '"></span></p>';
      }).join('') +
      '<p class="arena-lampc__actions">' +
      '<button type="button" data-lamp-reset>Сбросить</button></p>' +
      '<textarea class="arena-lampc__copy" data-lamp-copy readonly rows="4"></textarea>' +
      '</div>';

    document.body.appendChild(panel);
    plan = panel.querySelector('[data-lamp-plan]');

    var body = panel.querySelector('[data-lamp-body]');
    panel.querySelector('[data-lamp-toggle]').addEventListener('click', function () {
      body.hidden = !body.hidden;
      if (!body.hidden) { drawPlan(); }
    });

    panel.querySelector('[data-lamp-reset]').addEventListener('click', function () {
      state = defaults();
      save();
      push();
      drawPlan();
    });

    plan.addEventListener('pointerdown', function (event) {
      var key = event.target && event.target.getAttribute && event.target.getAttribute('data-lamp-group');
      if (!key) { return; }
      dragging = key;
      if (plan.setPointerCapture) { plan.setPointerCapture(event.pointerId); }
      event.preventDefault();
    });

    plan.addEventListener('pointermove', function (event) {
      if (!dragging) { return; }
      state[dragging] = pointerToLayout(event);
      push();
      drawPlan();
    });

    function release() {
      if (!dragging) { return; }
      dragging = null;
      save();
    }
    plan.addEventListener('pointerup', release);
    plan.addEventListener('pointercancel', release);
  }

  function start() {
    if (!document.getElementById('arena-render')) { return; }
    state = load();
    // Publish before the first paint where possible, so a stored layout is what
    // the floor is built with rather than something it flickers away from.
    global.ArenaLampLayout = state;
    build();
    push();
  }

  global.ArenaLampConsole = { start: start };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})(window);
