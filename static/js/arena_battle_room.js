/*
 * Battle blast — the arena-wide celebration when a battle finishes.
 *
 * Ported from arena_puzzle.js so it survived the legacy renderer's removal.
 * The blast celebrates a finished battle for everyone watching the arena, not
 * only the two participants.
 *
 * AA6, 2026-08-15: this file also carried a battle-room POPUP - a
 * server-rendered preview opened by clicking the centre of the floor. AA4
 * pointed that click at the battle's own broadcast page, which is what
 * ARENA_BATTLE_PLAN section 2c (Owner, 2026-08-06) always said the target
 * should be: "a click on the centre takes every spectator off the arena and
 * onto the battle's own page... the popup is a placeholder, and the target is
 * a page." That left open(), close(), the focus trap, the popup DOM, the
 * arena_battle_popup view, its template, its route and its payload key with
 * no caller at all. They are gone. The module keeps the name it is loaded
 * under; only the dead half was removed.
 */
(function (global) {
  'use strict';

  // null = not yet initialised from the page's own data. Only a *change* after
  // that first snapshot is a fresh result worth celebrating, so a reload never
  // replays the last battle's blast.
  var lastSeenResultId = null;

  function byId(id) { return document.getElementById(id); }

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
  }

  global.ArenaBattleRoom = {
    init: init,
    maybeCelebrate: maybeCelebrate
  };
})(window);
