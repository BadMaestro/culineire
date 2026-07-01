/* global window, document */
/* ==========================================================================
   CulinEire — Chef Battle cutlery hover cursor
   --------------------------------------------------------------------------
   Shows a custom crossed knife-&-fork cursor that follows the mouse while
   hovering any Chef Battle target (.battle-cursor-target / .js-battle-cursor-target).

   Event-delegated on `document` (pointerover/pointerout/pointermove, which
   bubble — unlike pointerenter/pointerleave) so targets created after this
   script runs (e.g. arena cells redrawn every 20s by arena_puzzle.js) are
   picked up automatically with zero extra wiring on their side.

   - Desktop / fine-pointer only  -> bails on touch & coarse pointers.
   - Overlay element is pointer-events:none, so it never blocks clicks,
     hover, focus or dropdown behaviour.
   - Degrades silently: if the overlay element is missing, nothing happens
     and targets behave normally with the native cursor.
   - Respects prefers-reduced-motion (no follow-smoothing).

   See static/css/battle_cursor.css. Isolated feature; safe to remove.
   ========================================================================== */
(function () {
  'use strict';

  // Desktop-like pointers only.
  var fine = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)');
  if (!fine || !fine.matches) { return; }

  var cursor = document.querySelector('.battle-cutlery-cursor');
  if (!cursor) { return; }   // graceful no-op

  var SELECTOR = '.battle-cursor-target, .js-battle-cursor-target';
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');

  // Offset so the SVG centre sits just off the actual click point.
  var OFFSET = 30;

  var targetX = -999, targetY = -999;
  var curX = -999, curY = -999;
  var visible = false;
  var rafId = null;
  var activeEl = null;

  function render() {
    rafId = null;
    if (reduce.matches) {
      curX = targetX;
      curY = targetY;
    } else {
      curX += (targetX - curX) * 0.22;
      curY += (targetY - curY) * 0.22;
    }
    cursor.style.transform =
      'translate3d(' + (curX - OFFSET) + 'px,' + (curY - OFFSET) + 'px,0)';

    // keep animating until we've caught up with the pointer
    if (visible && (Math.abs(targetX - curX) > 0.4 || Math.abs(targetY - curY) > 0.4)) {
      schedule();
    }
  }

  function schedule() {
    if (rafId === null) {
      rafId = window.requestAnimationFrame(render);
    }
  }

  function show(el, e) {
    // snap to the pointer on entry so it doesn't streak in from off-screen
    targetX = curX = e.clientX;
    targetY = curY = e.clientY;
    visible = true;
    activeEl = el;
    cursor.classList.add('is-visible');
    el.classList.add('is-battle-cursor-active');
    schedule();
  }

  function move(e) {
    targetX = e.clientX;
    targetY = e.clientY;
    schedule();
  }

  function hide() {
    visible = false;
    cursor.classList.remove('is-visible');
    if (activeEl) {
      activeEl.classList.remove('is-battle-cursor-active');
      activeEl = null;
    }
  }

  document.addEventListener('pointerover', function (e) {
    var el = e.target.closest ? e.target.closest(SELECTOR) : null;
    if (!el) { return; }
    if (el.contains(e.relatedTarget)) { return; } // moved within the same target
    show(el, e);
  });

  document.addEventListener('pointerout', function (e) {
    var el = e.target.closest ? e.target.closest(SELECTOR) : null;
    if (!el) { return; }
    if (el.contains(e.relatedTarget)) { return; } // moved to a child, not a real leave
    hide();
  });

  document.addEventListener('pointermove', function (e) {
    if (!activeEl) { return; }
    move(e);
  });

  document.addEventListener('pointercancel', hide);
  // safety: drop the overlay if the window loses focus mid-hover
  window.addEventListener('blur', hide);
}());
