(function () {
  'use strict';

  var popover = document.querySelector('[data-login-popover]');
  if (!popover) return;

  var trigger = popover.querySelector('[data-login-popover-trigger]');
  var panel = popover.querySelector('[data-login-popover-panel]');
  var username = popover.querySelector('[name="username"]');
  var desktop = window.matchMedia('(min-width: 1280px)');
  if (!trigger || !panel) return;

  function close() {
    panel.hidden = true;
    trigger.setAttribute('aria-expanded', 'false');
  }

  function open() {
    panel.hidden = false;
    trigger.setAttribute('aria-expanded', 'true');
    if (username) username.focus();
  }

  trigger.addEventListener('click', function (event) {
    if (!desktop.matches) return;
    event.preventDefault();
    if (panel.hidden) open(); else close();
  });
  document.addEventListener('click', function (event) {
    if (!panel.hidden && !popover.contains(event.target)) close();
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape' && !panel.hidden) {
      close();
      trigger.focus();
    }
  });
  desktop.addEventListener('change', function () {
    if (!desktop.matches) close();
  });
})();
