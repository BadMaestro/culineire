/* global window, document */
/* ==========================================================================
   CulinEire — Chef Battle cutlery hover cursor
   --------------------------------------------------------------------------
   Shows a custom crossed knife-&-fork cursor that follows the mouse while
   hovering the Chef Battle nav CTA (.battle-cursor-target).

   - Desktop / fine-pointer only  -> bails on touch & coarse pointers.
   - Overlay element is pointer-events:none, so it never blocks clicks,
     hover, focus or dropdown behaviour.
   - Degrades silently: if the overlay element or targets are missing,
     nothing happens and the button behaves normally with the native cursor.
   - Respects prefers-reduced-motion (no follow-smoothing).

   See static/css/battle_cursor.css. Isolated feature; safe to remove.
   ========================================================================== */
(function () {
  'use strict';

  // Desktop-like pointers only.
  var fine = window.matchMedia && window.matchMedia('(hover: hover) and (pointer: fine)');
  if (!fine || !fine.matches) { return; }

  var cursor = document.querySelector('.battle-cutlery-cursor');
  var targets = document.querySelectorAll('.battle-cursor-target, .js-battle-cursor-target');
  if (!cursor || !targets.length) { return; }   // graceful no-op

  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)');

  // Offset so the SVG centre sits just off the actual click point.
  var OFFSET = 30;

  var targetX = -999, targetY = -999;
  var curX = -999, curY = -999;
  var visible = false;
  var rafId = null;

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

  function show(e) {
    // snap to the pointer on entry so it doesn't streak in from off-screen
    targetX = curX = e.clientX;
    targetY = curY = e.clientY;
    visible = true;
    cursor.classList.add('is-visible');
    if (e.currentTarget && e.currentTarget.classList) {
      e.currentTarget.classList.add('is-battle-cursor-active');
    }
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
    for (var i = 0; i < targets.length; i++) {
      targets[i].classList.remove('is-battle-cursor-active');
    }
  }

  for (var i = 0; i < targets.length; i++) {
    var t = targets[i];
    t.addEventListener('pointerenter', show);
    t.addEventListener('pointermove', move);
    t.addEventListener('pointerleave', hide);
    t.addEventListener('pointercancel', hide);
    t.addEventListener('blur', hide, true);
  }
  // safety: drop the overlay if the window loses focus mid-hover
  window.addEventListener('blur', hide);
}());
