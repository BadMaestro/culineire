/*
 * The sticker shelf's viewer, and the right-click refusal that goes with it.
 *
 * Owner, 2026-08-31, in three instructions on the same shelf:
 *   "стикеры в галерее серые, цветные при наведении - и водяной знак на них"
 *   "ссылка на каждом стикере - при нажатии на которую открывается цветной стикер"
 *   "такой же способ как при нажатии на ячейку в спонсорах - только там
 *    открывается форма для заполнения, а у нас стикер в полный рост и цвет,
 *    но с ватермаркой"
 *   "и без возможности правого клика"
 *
 * The grey-to-colour is CSS. This file is the panel and the refusal.
 *
 * WHY contextmenu AND NOT A BUTTON NUMBER. The context menu is opened by the
 * OS GESTURE, not by a particular physical button - MDN puts it plainly: the
 * event "fires when the user attempts to open a context menu". So a reader who
 * has swapped his mouse buttons in the operating system is covered by the same
 * two lines, and nothing here has to detect a swap the browser cannot see
 * anyway. The Owner asked about exactly that case.
 *
 * WHAT IT DOES NOT DO, and it is on the record rather than implied: in Firefox,
 * Shift plus the menu gesture opens the menu WITHOUT firing this event at all,
 * by design. Nothing on any page can prevent that. The picture is also still in
 * the browser cache and still one devtools panel away - this is a sign on the
 * door, and the lock is that the file it hands over is watermarked and that the
 * chat refuses a re-upload of it (v2.5.1519).
 */
(function () {
  'use strict';

  var viewer = document.querySelector('[data-sticker-viewer]');
  if (!viewer) { return; }

  var art = viewer.querySelector('[data-sticker-art]');
  var label = viewer.querySelector('[data-sticker-label]');
  var closer = viewer.querySelector('[data-sticker-close]');
  var opener = null;

  function open(button) {
    var full = button.getAttribute('data-full');
    if (!full) { return; }
    opener = button;
    art.setAttribute('src', full);
    art.setAttribute('alt', button.getAttribute('data-label') || '');
    if (label) { label.textContent = button.getAttribute('data-label') || ''; }
    viewer.hidden = false;
    // The page behind must not scroll under an open panel - the same thing the
    // sponsors modal does, for the same reason.
    document.body.style.overflow = 'hidden';
    if (closer) { closer.focus(); }
  }

  function close() {
    viewer.hidden = true;
    document.body.style.overflow = '';
    // Focus goes back where it came from, or the reader is dropped at the top
    // of the document having pressed one key.
    if (opener) { opener.focus(); opener = null; }
  }

  document.addEventListener('click', function (event) {
    var button = event.target.closest && event.target.closest('[data-sticker-open]');
    if (button) {
      event.preventDefault();
      open(button);
      return;
    }
    if (event.target.closest && event.target.closest('[data-sticker-close]')) {
      close();
      return;
    }
    // The dim behind the card closes it, as it does on the sponsors puzzle.
    if (event.target === viewer) { close(); }
  });

  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !viewer.hidden) { close(); }
  });

  // NO CONTEXT MENU, NO DRAG, ON THE SHELF'S PICTURES AND ON THE VIEWER.
  // Delegated rather than bound per image, so stickers rendered later are
  // covered by the same two handlers.
  function isProtected(target) {
    if (!target || !target.closest) { return false; }
    return !!(target.closest('.sticker-card__art')
              || target.closest('[data-sticker-art]')
              || target.closest('.sticker-pack__window'));
  }

  document.addEventListener('contextmenu', function (event) {
    if (isProtected(event.target)) { event.preventDefault(); }
  });

  document.addEventListener('dragstart', function (event) {
    if (isProtected(event.target)) { event.preventDefault(); }
  });
})();
