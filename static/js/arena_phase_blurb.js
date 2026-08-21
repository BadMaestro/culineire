/**
 * EVERY STAGE OF THE BATTLE EXPLAINS ITSELF.
 *
 * Owner, 2026-08-21: "seven stages of the battle, reveal the description of
 * each stage." The strip has always said WHICH stage is running and never
 * what any of them means - a spectator who has just walked into the arena had
 * no way to find out. Tapping a marker now prints that stage's sentence under
 * the strip.
 *
 * THE TEXT IS THE SERVER'S. Each marker carries it as data-phase-blurb,
 * written from _ARENA_PHASE_RAIL_STEPS (chef_battle/selectors.py) both by the
 * template and by arena_deck.js when a poll rebuilds the rail, so the two can
 * never end up describing the stages differently. Nothing here invents a word
 * of it; a marker with no blurb simply does not open.
 *
 * WHY THIS IS ITS OWN FILE. arena_deck.js owns what the rail SAYS - which
 * rung is active, which are complete, what the next one is called - and is
 * driven by the poll. This owns what the reader ASKED for, and is driven by a
 * finger. Keeping the two apart means a repaint cannot close a panel the
 * reader just opened, and this file never has to know how the rail is built.
 *
 * Delegated from the rail rather than bound per marker, because the rail is
 * rebuilt from scratch whenever the rung set changes: a listener on each
 * marker would be lost with it, and re-binding after every poll is a second
 * thing to remember. One listener on the container survives every rebuild.
 */
(function (global) {
  'use strict';

  function init() {
    var rail = document.getElementById('arena-phase-rail');
    var panel = document.getElementById('arena-phase-blurb');
    if (!rail || !panel) { return; }

    var openKey = null;

    function close() {
      openKey = null;
      panel.hidden = true;
      panel.textContent = '';
      Array.prototype.forEach.call(
        rail.querySelectorAll('[data-phase-step]'),
        function (step) { step.removeAttribute('aria-expanded'); }
      );
    }

    function open(step) {
      var text = step.getAttribute('data-phase-blurb');
      if (!text) { return; }
      var key = step.getAttribute('data-phase-step');

      /* A second tap on the same marker closes it. The gesture that opened
         it is the one everyone tries to undo it with. */
      if (openKey === key) { close(); return; }

      Array.prototype.forEach.call(
        rail.querySelectorAll('[data-phase-step]'),
        function (other) { other.removeAttribute('aria-expanded'); }
      );
      step.setAttribute('aria-expanded', 'true');
      openKey = key;
      panel.textContent = text;
      panel.hidden = false;
    }

    rail.addEventListener('click', function (event) {
      var step = event.target.closest && event.target.closest('[data-phase-step]');
      if (step && rail.contains(step)) { open(step); }
    });

    rail.addEventListener('keydown', function (event) {
      if (event.key !== 'Enter' && event.key !== ' ' && event.key !== 'Spacebar') {
        return;
      }
      var step = event.target.closest && event.target.closest('[data-phase-step]');
      if (!step || !rail.contains(step)) { return; }
      /* Space scrolls a page by default, and a marker that scrolled the arena
         away while opening its own description would be a strange control. */
      event.preventDefault();
      open(step);
    });

    /* Escape closes it from the keyboard, the same way it closes every other
       transient panel on this site. */
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape' && openKey !== null) { close(); }
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})(window);
