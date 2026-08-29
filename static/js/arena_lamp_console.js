/*
 * Arena lamp console — the Owner's control over where the lamps stand.
 *
 * Built 2026-07-31 on his order, after the throwaway plan he called the ideal
 * way to control them: he drags a lamp on a small schematic and the real floor
 * answers immediately.
 *
 * MOVED INTO THE MASTER CONSOLE on 2026-08-29, on his instruction: "Перенеси
 * виджет управления лампочками в мастер консоль и встрой в панель управления
 * боем", and then "чтоб он стал статичным блоком управления внутри мастер
 * консоли". So it is no longer a floating panel with a toggle bolted to the
 * corner of the public arena. It mounts into the operator panel it was given
 * and stays open: a control inside a control deck does not need to ask
 * permission to be visible.
 *
 * IT NO LONGER READS OR WRITES THE LAYOUT ITSELF. arena_lamp_layout.js does
 * that, and both pages load it - otherwise moving this panel off the arena
 * would have taken his stored positions with it and quietly returned the floor
 * to the defaults, which is the one thing he said he did not want.
 *
 * Three things it still deliberately does NOT do:
 *
 *  - It does not touch the server. Positions live in localStorage, in his own
 *    browser. Persisting them would mean a schema change, and a schema change
 *    needs his explicit word every time (AGENTS.md section 8).
 *  - It does not widen access. It renders only where the template gives it a
 *    mount point, and that mount point sits inside the owner-only branch of the
 *    Master Console's first panel. It adds no route and no gate of its own.
 *  - It does not draw the floor. It writes a layout and asks the renderer to
 *    repaint, so exactly one piece of code knows how a lamp is drawn, and it is
 *    arena_render.js.
 */
(function (global) {
  'use strict';

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
  var store = null;
  var state = null;
  var panel = null;
  var plan = null;
  var dragging = null;

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

    for (var i = 0; i < GROUPS.length; i++) {
      var grp = GROUPS[i];
      var here = state[grp.key];
      for (var n = 0; n < 8; n++) {
        var a = (n * 45 + here.deg) * Math.PI / 180;
        var dot = svgEl('circle', {
          cx: (C + here.r * K * UNIT * Math.cos(a)).toFixed(1),
          cy: (C + here.r * K * UNIT * Math.sin(a)).toFixed(1),
          r: n === 0 ? 7 : 4.5,
          fill: grp.colour,
          'class': 'arena-lampc__dot',
          'data-lamp-group': grp.key
        });
        plan.appendChild(dot);
      }
    }
    readout();
  }

  function readout() {
    for (var i = 0; i < GROUPS.length; i++) {
      var key = GROUPS[i].key;
      var node = panel.querySelector('[data-lamp-readout="' + key + '"]');
      if (node) {
        node.textContent = 'r ' + state[key].r.toFixed(4) + '  ·  ' + state[key].deg.toFixed(1) + '°';
      }
    }
    var box = panel.querySelector('[data-lamp-copy]');
    if (box) { box.value = JSON.stringify(state, null, 2); }
  }

  function pointerToLayout(event) {
    var box = plan.getBoundingClientRect();
    var scale = 300 / box.width;
    var x = (event.clientX - box.left) * scale - C;
    var y = (event.clientY - box.top) * scale - C;
    var deg = Math.atan2(y, x) * 180 / Math.PI;
    return {
      // Clamped so a slip of the hand cannot throw a lamp off the floor.
      r: Math.max(0.3, Math.min(2.2, Math.sqrt(x * x + y * y) / K / UNIT)),
      // Eight-fold symmetry: only the offset inside one face is free.
      deg: ((deg % 45) + 45) % 45
    };
  }

  function build(mount) {
    panel = document.createElement('div');
    panel.className = 'arena-lampc';
    panel.setAttribute('aria-label', 'Управление лампами арены');
    panel.innerHTML =
      '<div class="arena-lampc__body">' +
      '<p class="arena-lampc__hint">Тяните лампу — вся восьмёрка едет вместе. Арена меняется сразу.</p>' +
      '<svg class="arena-lampc__plan" viewBox="0 0 300 300" data-lamp-plan></svg>' +
      GROUPS.map(function (grp) {
        return '<p class="arena-lampc__row"><span class="arena-lampc__sw" style="background:' + grp.colour + '"></span>' +
          grp.label + '<br><span class="arena-lampc__val" data-lamp-readout="' + grp.key + '"></span></p>';
      }).join('') +
      '<p class="arena-lampc__actions">' +
      '<button type="button" data-lamp-reset>Сбросить</button></p>' +
      // id and aria-label: a field with neither is one a screen reader
      // announces as nothing and the browser cannot autofill. It is read-only
      // and holds the numbers to copy out of the console, so the label says so.
      '<textarea id="arena-lamp-copy" class="arena-lampc__copy" data-lamp-copy ' +
      'aria-label="Lamp layout values, ready to copy" readonly rows="4"></textarea>' +
      '</div>';

    mount.appendChild(panel);
    plan = panel.querySelector('[data-lamp-plan]');

    panel.querySelector('[data-lamp-reset]').addEventListener('click', function () {
      state = store.defaults();
      store.save(state);
      store.push(state);
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
      store.push(state);
      drawPlan();
    });

    function release() {
      if (!dragging) { return; }
      dragging = null;
      store.save(state);
    }
    plan.addEventListener('pointerup', release);
    plan.addEventListener('pointercancel', release);
  }

  function start() {
    // NO MOUNT POINT, NO PANEL, and that is the whole of the access story: the
    // template decides where this control may appear, and it writes the mount
    // only inside the owner-only branch of the console's first panel.
    var mount = document.querySelector('[data-lamp-mount]');
    if (!mount) { return; }
    store = global.ArenaLampStore;
    if (!store) { return; }
    state = global.ArenaLampLayout || store.load();
    build(mount);
    store.push(state);
    drawPlan();
  }

  global.ArenaLampConsole = { start: start };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start);
  } else {
    start();
  }
})(window);
