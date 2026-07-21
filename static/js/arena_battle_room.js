/*
 * Battle room popup + battle blast.
 *
 * Ported from arena_puzzle.js so both survive the legacy renderer's removal.
 * The popup embeds a server-rendered preview and links to the full-screen
 * Battle Room; the blast celebrates a finished battle for everyone watching the
 * arena, not only the two participants.
 */
(function (global) {
  'use strict';

  var previousFocus = null;
  var popupRequestId = 0;
  // null = not yet initialised from the page's own data. Only a *change* after
  // that first snapshot is a fresh result worth celebrating, so a reload never
  // replays the last battle's blast.
  var lastSeenResultId = null;

  function byId(id) { return document.getElementById(id); }

  function popupPanel() {
    var popup = byId('arena-battle-popup');
    return popup ? popup.querySelector('[role="dialog"]') : null;
  }

  function focusableElements() {
    var panel = popupPanel();
    if (!panel) { return []; }
    return Array.prototype.filter.call(panel.querySelectorAll(
      'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), ' +
      'textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'
    ), function (element) {
      return !element.hidden && element.getAttribute('aria-hidden') !== 'true';
    });
  }

  function focusPopup() {
    var closeBtn = byId('arena-popup-close');
    var panel = popupPanel();
    if (closeBtn) {
      closeBtn.focus();
    } else if (panel) {
      panel.setAttribute('tabindex', '-1');
      panel.focus();
    }
  }

  /* ---- popup ---- */

  function setLoading(inner, text) {
    inner.textContent = '';
    var note = document.createElement('p');
    note.className = 'arena-popup__loading';
    note.textContent = text;
    inner.appendChild(note);
  }

  function open(popupUrl, battleUrl) {
    var popup = byId('arena-battle-popup');
    var inner = byId('arena-popup-inner');
    if (!popup || !inner) {
      if (battleUrl) { global.location.href = battleUrl; }
      return;
    }
    var requestId = ++popupRequestId;
    setLoading(inner, 'Loading battle...');
    previousFocus = document.activeElement;
    popup.hidden = false;
    document.body.style.overflow = 'hidden';
    focusPopup();

    fetch(popupUrl, { credentials: 'same-origin' })
      .then(function (response) { return response.ok ? response.text() : null; })
      .then(function (html) {
        if (requestId !== popupRequestId || popup.hidden) { return; }
        if (!html) {
          setLoading(inner, 'No active battle right now.');
          return;
        }
        // Server-rendered fragment from our own view.
        inner.innerHTML = html;
        focusPopup();
      })
      .catch(function () {
        if (requestId !== popupRequestId || popup.hidden) { return; }
        setLoading(inner, 'Could not load battle.');
        if (battleUrl) {
          var link = document.createElement('a');
          link.href = battleUrl;
          link.textContent = 'Open full room';
          inner.querySelector('.arena-popup__loading').appendChild(link);
        }
      });
  }

  function close() {
    var popup = byId('arena-battle-popup');
    if (!popup || popup.hidden) { return; }
    popupRequestId += 1;
    popup.hidden = true;
    document.body.style.overflow = '';
    if (previousFocus && typeof previousFocus.focus === 'function' && document.contains(previousFocus)) {
      previousFocus.focus();
    }
    previousFocus = null;
  }

  /* ---- battle blast ---- */

  function fireBlast(result) {
    var blast = byId('battle-blast');
    if (!blast || !result) { return; }
    var badge = byId('blast-badge');
    var winner = byId('blast-winner');
    var score = byId('blast-score');
    if (badge) { badge.textContent = 'Battle Complete'; }
    if (winner) { winner.textContent = result.winner_name + ' Wins!'; }
    if (score) { score.textContent = result.result_reason || result.theme || ''; }

    blast.hidden = false;
    // Force layout so the entrance transition actually plays.
    void blast.offsetWidth;
    blast.classList.add('is-active');
  }

  function dismissBlast() {
    var blast = byId('battle-blast');
    if (!blast) { return; }
    blast.classList.remove('is-active');
    global.setTimeout(function () { blast.hidden = true; }, 350);
  }

  function maybeCelebrate(latestResult) {
    if (!latestResult) { return; }
    if (lastSeenResultId !== null && latestResult.battle_id !== lastSeenResultId) {
      fireBlast(latestResult);
    }
    lastSeenResultId = latestResult.battle_id;
  }

  /* ---- wiring ---- */

  function init(initialResult) {
    lastSeenResultId = initialResult ? initialResult.battle_id : null;

    var dismiss = byId('blast-dismiss');
    if (dismiss) { dismiss.addEventListener('click', dismissBlast); }

    var closeBtn = byId('arena-popup-close');
    var backdrop = byId('arena-popup-backdrop');
    if (closeBtn) { closeBtn.addEventListener('click', close); }
    if (backdrop) { backdrop.addEventListener('click', close); }
    document.addEventListener('keydown', function (event) {
      var popup = byId('arena-battle-popup');
      if (!popup || popup.hidden) { return; }
      if (event.key === 'Escape') {
        event.preventDefault();
        close();
        return;
      }
      if (event.key !== 'Tab') { return; }
      var focusable = focusableElements();
      if (!focusable.length) {
        event.preventDefault();
        focusPopup();
        return;
      }
      var first = focusable[0];
      var last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    });
  }

  global.ArenaBattleRoom = {
    init: init,
    open: open,
    close: close,
    maybeCelebrate: maybeCelebrate
  };
})(window);
