/*
 * Arena lamp layout — applies the Owner's stored lamp positions. No interface.
 *
 * Split out of arena_lamp_console.js on 2026-08-29, when he moved the control
 * itself into the Master Console and ruled: "на арене пусть применяется то, что
 * я настроил в консоли".
 *
 * Before the split, the panel that DREW the control was also the only thing
 * that read the stored layout - so taking the control off the public arena
 * would have taken his positions with it and quietly returned the floor to the
 * defaults. Reading the layout and offering a way to change it are two jobs;
 * this file is the first one and it is the one both pages need.
 *
 * The store is localStorage, in his own browser. Persisting to the server would
 * be a schema change, and a schema change needs his explicit word every time
 * (AGENTS.md section 8). It has not been given, so this stays where it was.
 */
(function (global) {
  'use strict';

  var KEY = 'culineire.arena.lamps.v1';
  var KEYS = ['outer', 'inner', 'moat'];

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
      for (var i = 0; i < KEYS.length; i++) {
        var k = KEYS[i];
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

  function save(state) {
    try {
      if (global.localStorage) { global.localStorage.setItem(KEY, JSON.stringify(state)); }
    } catch (error) { /* private mode, quota - it still works this session */ }
  }

  function push(state) {
    global.ArenaLampLayout = state;
    if (global.ArenaRender && global.ArenaRender.applyLampLayout) {
      global.ArenaRender.applyLampLayout();
    }
  }

  function apply() {
    if (!document.getElementById('arena-render')) { return null; }
    var state = load();
    // Published BEFORE the first paint where possible, so a stored layout is
    // what the floor is built with rather than something it flickers away from.
    global.ArenaLampLayout = state;
    push(state);
    return state;
  }

  global.ArenaLampLayout = global.ArenaLampLayout || null;
  global.ArenaLampStore = {
    key: KEY,
    keys: KEYS,
    defaults: defaults,
    load: load,
    save: save,
    push: push,
    apply: apply
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', apply);
  } else {
    apply();
  }
})(window);
