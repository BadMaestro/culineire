/**
 * Sitewide Chef Battles widget — vertical drag.
 * The header row is the handle: a short press toggles the card, a vertical
 * move slides the whole widget up/down and the position is remembered per
 * device (localStorage). Uses pointer events, so it works with both a finger
 * (touch) and the mouse (desktop) identically.
 */
(function () {
  'use strict';

  var widget = document.getElementById('site-battle-widget');
  if (!widget) return;
  var handle = widget.querySelector('.site-battle-widget__toggle');
  var details = widget.querySelector('.site-battle-widget__details');
  if (!handle) return;

  var STORE_KEY = 'battleWidgetTop';
  var COLLAPSE_STORE_KEY = 'battleWidgetCollapsed';
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

  if (details) {
    try {
      if (window.localStorage.getItem(COLLAPSE_STORE_KEY) === 'true') {
        details.open = false;
      }
    } catch (err) {}
    details.addEventListener('toggle', function () {
      try {
        window.localStorage.setItem(COLLAPSE_STORE_KEY, details.open ? 'false' : 'true');
      } catch (err) {}
    });
  }

  var pointerId = null;
  var startY = 0;
  var startTop = 0;
  var dragged = false;

  // Fully clear the gesture and release any pointer capture. Idempotent —
  // safe to call from any of the end-of-gesture events. Resetting ALL state
  // here (not just in a click that may never fire) is what stops the widget
  // from getting stuck in a "grabbing" drag that follows the cursor.
  function reset() {
    if (pointerId !== null) {
      try { handle.releasePointerCapture(pointerId); } catch (err) {}
    }
    pointerId = null;
    widget.dataset.dragging = 'false';
  }

  function endDrag(e) {
    if (pointerId === null || (e && e.pointerId !== pointerId)) return;
    if (dragged) {
      try {
        window.localStorage.setItem(
          STORE_KEY, String(Math.round(widget.getBoundingClientRect().top)));
      } catch (err) {}
    }
    reset();
  }

  handle.addEventListener('pointerdown', function (e) {
    // Only a primary (left) mouse button starts a drag; ignore right/middle.
    if (e.pointerType === 'mouse' && e.button !== 0) return;
    // If a previous gesture somehow never cleaned up, clear it first.
    if (pointerId !== null) reset();
    pointerId = e.pointerId;
    startY = e.clientY;
    startTop = widget.getBoundingClientRect().top;
    dragged = false;
    // Capture immediately (not after the threshold): this guarantees every
    // pointermove / pointerup / pointercancel for this pointer is delivered to
    // the handle even once the widget slides out from under the cursor. The
    // old code captured late, so an "up" that landed off the handle was missed
    // and the drag got stuck.
    try { handle.setPointerCapture(e.pointerId); } catch (err) {}
  });

  handle.addEventListener('pointermove', function (e) {
    if (pointerId === null || e.pointerId !== pointerId) return;
    // Safety net: if no button is held any more, a pointerup was missed —
    // end the gesture instead of letting the widget track a button-up cursor.
    if (e.buttons === 0) { endDrag(e); return; }
    var delta = e.clientY - startY;
    if (!dragged && Math.abs(delta) > DRAG_THRESHOLD) {
      dragged = true;
      widget.dataset.dragging = 'true';
    }
    if (dragged) {
      e.preventDefault();
      applyTop(startTop + delta);
    }
  });

  handle.addEventListener('pointerup', endDrag);
  handle.addEventListener('pointercancel', endDrag);
  // Belt-and-braces: if the browser drops the capture for any reason, stop.
  handle.addEventListener('lostpointercapture', endDrag);

  // A finished drag must not also toggle the <details> — swallow the click
  // that the same gesture produces.
  handle.addEventListener('click', function (e) {
    if (dragged) {
      e.preventDefault();
      e.stopPropagation();
      dragged = false;
    }
  });

  // Keep the widget on screen when the viewport rotates/resizes.
  window.addEventListener('resize', function () {
    if (widget.style.top) applyTop(parseFloat(widget.style.top));
  });
})();
