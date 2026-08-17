/**
 * The "More" portrait gallery on the registration form.
 *
 * The Owner, 2026-08-17: the site has 96 generated portraits and may NOT hand
 * one to a person automatically -- they are realistic and carry racial
 * features, skin colour and age nobody has the right to attribute to someone.
 * So the gallery is a door the person opens himself, and this file does nothing
 * until he clicks More.
 *
 * The form works without it: gallery_avatar simply stays empty and the
 * illustrated stand-in he picked from the three radios stands, which is exactly
 * the behaviour the page had before the gallery existed.
 */
(function () {
  'use strict';

  var open = document.getElementById('avatar-gallery-open');
  var modal = document.getElementById('avatar-gallery-modal');
  var field = document.getElementById('id_gallery_avatar');
  if (!open || !modal || !field) { return; }

  var close = document.getElementById('avatar-gallery-close');
  var chosen = document.getElementById('avatar-gallery-chosen');
  var chosenImg = document.getElementById('avatar-gallery-chosen-img');
  var clear = document.getElementById('avatar-gallery-clear');
  var lastFocus = null;

  function showModal() {
    lastFocus = document.activeElement;
    modal.removeAttribute('hidden');
    // Focus moves into the dialog so a keyboard user is not left behind on the
    // page underneath it. preventScroll because focusing a tile lets the browser
    // scroll it into view, and its idea of "into view" can push the first row of
    // portraits out of sight - which is the bug this guards against, not a
    // theoretical one.
    var first = modal.querySelector('.auth-avatar-grid__item');
    var target = first || close;
    try {
        target.focus({ preventScroll: true });
    } catch (err) {
        target.focus();
    }
    modal.scrollTop = 0;
    var panel = modal.querySelector('.auth-avatar-modal__panel');
    if (panel) { panel.scrollTop = 0; }
    document.addEventListener('keydown', onKey);
  }

  function hideModal() {
    modal.setAttribute('hidden', 'hidden');
    document.removeEventListener('keydown', onKey);
    if (lastFocus) { lastFocus.focus(); }
  }

  function onKey(event) {
    if (event.key === 'Escape') { hideModal(); }
  }

  function pick(key, url) {
    field.value = key;
    chosenImg.setAttribute('src', url);
    chosen.removeAttribute('hidden');
    hideModal();
  }

  open.addEventListener('click', showModal);
  if (close) { close.addEventListener('click', hideModal); }

  // The backdrop closes; a click inside the panel must not.
  modal.addEventListener('click', function (event) {
    if (event.target === modal) { hideModal(); }
  });

  modal.addEventListener('click', function (event) {
    var item = event.target.closest ? event.target.closest('.auth-avatar-grid__item') : null;
    if (!item) { return; }
    pick(item.getAttribute('data-avatar-key'), item.getAttribute('data-avatar-url'));
  });

  if (clear) {
    clear.addEventListener('click', function () {
      field.value = '';
      chosen.setAttribute('hidden', 'hidden');
      chosenImg.setAttribute('src', '');
      open.focus();
    });
  }
})();
