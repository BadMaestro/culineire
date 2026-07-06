/**
 * Sitewide Chef Battles widget — vertical drag.
 * The header row is the handle: a short press toggles the card as before,
 * a vertical move slides the whole widget up/down and the position is
 * remembered per device (localStorage). Uses pointer events, so it works
 * with both a finger (touch) and the mouse (desktop) identically.
 */
(function () {
  'use strict';

  var widget = document.getElementById('site-battle-widget');
  if (!widget) return;
  var handle = widget.querySelector('.site-battle-widget__toggle');
  if (!handle) return;

  var STORE_KEY = 'battleWidgetTop';
  var DRAG_THRESHOLD = 12; // px of travel before a press becomes a drag
  var EDGE = 8;            // min gap from viewport top/bottom

  function clampTop(top) {
    var max = window.innerHeight - handle.offsetHeight - EDGE;
    return Math.min(Math.max(top, EDGE), Math.max(max, EDGE));
  }

  function applyTop(top) {
    widget.style.top = clampTop(top) + 'px';
    widget.style.bottom = 'auto';
  }

  var saved = parseFloat(window.localStorage.getItem(STORE_KEY));
  if (!isNaN(saved)) applyTop(saved);

  var pointerId = null;
  var startY = 0;
  var startTop = 0;
  var dragged = false;

  handle.addEventListener('pointerdown', function (e) {
    pointerId = e.pointerId;
    startY = e.clientY;
    startTop = widget.getBoundingClientRect().top;
    dragged = false;
  });

  handle.addEventListener('pointermove', function (e) {
    if (pointerId === null || e.pointerId !== pointerId) return;
    var delta = e.clientY - startY;
    if (!dragged && Math.abs(delta) > DRAG_THRESHOLD) {
      dragged = true;
      widget.dataset.dragging = 'true';
      try { handle.setPointerCapture(pointerId); } catch (err) {}
    }
    if (dragged) {
      e.preventDefault();
      applyTop(startTop + delta);
    }
  });

  function endDrag(e) {
    if (pointerId === null || e.pointerId !== pointerId) return;
    pointerId = null;
    if (dragged) {
      widget.dataset.dragging = 'false';
      try {
        window.localStorage.setItem(
          STORE_KEY, String(Math.round(widget.getBoundingClientRect().top)));
      } catch (err) {}
    }
  }

  handle.addEventListener('pointerup', endDrag);
  handle.addEventListener('pointercancel', endDrag);

  // A finished drag must not also toggle the <details> — swallow the click
  // that the same gesture produces.
  handle.addEventListener('click', function (e) {
    if (dragged) {
      e.preventDefault();
      dragged = false;
    }
  });

  // Keep the widget on screen when the viewport rotates/resizes.
  window.addEventListener('resize', function () {
    if (widget.style.top) applyTop(parseFloat(widget.style.top));
  });
})();
