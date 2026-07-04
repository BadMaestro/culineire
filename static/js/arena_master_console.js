/**
 * Arena Master Console — P02 read-only live updates.
 * Bootstraps from #amc-state-json, polls /chef-battle/master/state/ every
 * 20 s (same cadence as the public arena), and ticks the countdown every
 * second. No writes: this file only reads state and updates text.
 */
(function () {
  'use strict';

  var POLL_INTERVAL = 20000;
  var STATE_URL = '/chef-battle/master/state/';

  var stateEl = document.getElementById('amc-state-json');
  if (!stateEl) return;

  var state;
  try { state = JSON.parse(stateEl.textContent); } catch (e) { return; }

  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function setText(id, value) {
    var el = document.getElementById(id);
    if (el) el.textContent = value;
  }

  function setEmpty(id, label) {
    var el = document.getElementById(id);
    if (el) el.innerHTML = '<span class="amc-empty">' + label + '</span>';
  }

  /* ── Countdown ──────────────────────────────────────────────────── */

  var deadlineMs = null;

  function syncDeadline() {
    var primary = state.battles && state.battles[0];
    deadlineMs = primary && primary.deadline ? Date.parse(primary.deadline) : null;
  }

  function tick() {
    var el = document.getElementById('amc-status-timer');
    if (!el) return;
    if (deadlineMs === null) { el.textContent = '--:--'; return; }
    var s = Math.max(0, Math.floor((deadlineMs - Date.now()) / 1000));
    var h = Math.floor(s / 3600);
    var m = Math.floor((s % 3600) / 60);
    var sec = s % 60;
    el.textContent = h > 0
      ? h + ':' + String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0')
      : String(m).padStart(2, '0') + ':' + String(sec).padStart(2, '0');
  }

  /* ── Apply state to the DOM ─────────────────────────────────────── */

  function apply() {
    var primary = state.battles && state.battles[0];
    var sys = state.system || {};

    setText('amc-battle-count', sys.active_battle_count);
    setText('amc-paused-count', sys.paused_battle_count);

    if (primary) {
      setText('amc-battle-id', '#' + primary.id);
      setText('amc-status-state', primary.status_display);
      setText('amc-status-theme', primary.theme);
      if (primary.next_status_display) setText('amc-status-next', primary.next_status_display);
    } else {
      setEmpty('amc-battle-id', 'No active battle');
      setEmpty('amc-status-state', 'No active battle');
      setEmpty('amc-status-theme', '—');
      setEmpty('amc-status-next', '—');
    }

    setText('amc-online', state.arena.online_count);
    if (state.voting && state.voting.length) {
      setText('amc-votes', state.voting[0].total_votes);
    } else {
      setEmpty('amc-votes', 'No active battle');
    }
    if (state.economy && state.economy.battle_gifts && state.economy.battle_gifts.length) {
      setText('amc-gifts', state.economy.battle_gifts[0].gift_count);
    } else {
      setEmpty('amc-gifts', 'No active battle');
    }
    if (state.arena.crown_holder) {
      setText('amc-crown', state.arena.crown_holder.name);
    } else {
      setEmpty('amc-crown', 'None');
    }

    setText('amc-mod-cooking', state.moderation.cooking_queue);
    setText('amc-mod-reports', state.moderation.content_reports_pending);
    setText('amc-mod-flagged', state.moderation.entries_flagged);

    setText('amc-eco-in', state.economy.tokens_in_24h);
    setText('amc-eco-out', state.economy.tokens_out_24h);
    setText('amc-eco-payouts', state.economy.pending_payouts);

    setText('amc-rank-enrolled', state.arena.enrolled_count);
    setText('amc-rank-online', state.arena.online_count);
    setText('amc-rank-suspended', state.arena.suspended_count);

    if (sys.server_time) {
      var d = new Date(sys.server_time);
      setText('amc-server-time',
        String(d.getHours()).padStart(2, '0') + ':' + String(d.getMinutes()).padStart(2, '0'));
    }

    /* Phase rail active step */
    var rail = document.querySelector('.amc-phase-rail');
    if (rail) {
      var active = primary ? primary.phase_rail_step : null;
      rail.querySelectorAll('.amc-phase-rail__step').forEach(function (step) {
        step.classList.toggle('amc-phase-rail__step--active',
          active !== null && Number(step.getAttribute('data-step')) === active);
      });
      var note = document.getElementById('amc-rail-note');
      if (note) note.classList.toggle('amc-hidden', !!primary);
    }

    syncDeadline();
    tick();
  }

  /* ── Poll loop ──────────────────────────────────────────────────── */

  function poll() {
    fetch(STATE_URL, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      credentials: 'same-origin',
    })
      .then(function (resp) {
        if (!resp.ok) throw new Error('poll ' + resp.status);
        return resp.json();
      })
      .then(function (fresh) {
        state = fresh;
        apply();
        setText('amc-sys-status', 'Read models live · polling every 20s');
      })
      .catch(function () {
        setText('amc-sys-status', 'Poll failed — showing last known state');
      });
  }

  apply();
  setInterval(tick, 1000);
  setInterval(poll, POLL_INTERVAL);
})();
