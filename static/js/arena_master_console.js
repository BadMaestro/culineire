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
    var primary = state.battles && state.battles[0];
    if (primary && primary.is_paused) { el.textContent = 'PAUSED'; return; }
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
    return fetch(STATE_URL, {
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

  /* ── Operator actions (P03, owner only) ─────────────────────────── */

  var ACTION_URL = '/chef-battle/master/action/';

  function showActionError(text) {
    var el = document.getElementById('amc-action-error');
    if (!el) return;
    el.textContent = text;
    el.classList.toggle('amc-hidden', !text);
  }

  function postAction(fields) {
    var body = new FormData();
    Object.keys(fields).forEach(function (k) {
      if (fields[k] !== null && fields[k] !== undefined) body.append(k, fields[k]);
    });
    return fetch(ACTION_URL, {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrfToken() },
      credentials: 'same-origin',
      body: body,
    }).then(function (resp) {
      return resp.json().then(function (data) {
        if (!resp.ok || !data.ok) throw new Error(data.error || ('HTTP ' + resp.status));
        return data;
      });
    });
  }

  function handleAction(btn) {
    var primary = state.battles && state.battles[0];
    var kind = btn.getAttribute('data-amc-action');
    var fields = { battle_id: primary ? primary.id : '' };

    if (kind === 'broadcast') {
      var msg = window.prompt('Broadcast notice (public, appears in the battle feed):');
      if (!msg) return;
      fields.action = 'broadcast';
      fields.message = msg;
    } else if (!primary) {
      showActionError('No battle to act on.');
      return;
    } else if (kind === 'advance') {
      if (!primary.next_status) { showActionError('No expected next phase for this state.'); return; }
      if (!window.confirm('Force battle #' + primary.id + ' from "' + primary.status_display +
          '" to "' + primary.next_status_display + '"? This is audited and cannot be undone from the console.')) return;
      fields.action = 'force_status';
      fields.target_status = primary.next_status;
      fields.expected_status = primary.status;
      fields.reason = 'Console: advance to expected next phase';
    } else if (kind === 'force') {
      var target = btn.getAttribute('data-amc-target');
      if (!window.confirm('Force battle #' + primary.id + ' from "' + primary.status_display +
          '" to "' + target + '"? This is audited and cannot be undone from the console.')) return;
      fields.action = 'force_status';
      fields.target_status = target;
      fields.expected_status = primary.status;
      fields.reason = 'Console: force ' + target;
    } else if (kind === 'emergency_stop') {
      var reason = window.prompt(
        'EMERGENCY STOP battle #' + primary.id + '.\n' +
        'Consequences: status becomes PAUSED, all timers freeze, live streams are ' +
        'terminated, both chefs are notified. Only you can resume or cancel.\n\n' +
        'Enter the reason (required):');
      if (!reason) return;
      fields.action = 'emergency_stop';
      fields.reason = reason;
    } else if (kind === 'resume') {
      if (!window.confirm('Resume battle #' + primary.id + ' to its pre-pause phase?')) return;
      fields.action = 'resume';
    } else if (kind === 'cancel') {
      var cancelReason = window.prompt(
        'END BATTLE #' + primary.id + ' — this cancels it PERMANENTLY. ' +
        'Both chefs are notified. Enter the reason (required):');
      if (!cancelReason) return;
      fields.action = 'cancel';
      fields.reason = cancelReason;
    } else {
      return;
    }

    btn.disabled = true;
    showActionError('');
    postAction(fields)
      .then(function () { return poll(); })
      .catch(function (err) { showActionError(err.message); })
      .finally(function () { btn.disabled = false; });
  }

  var controls = document.getElementById('amc-controls');
  if (controls && window.AMC_OPERATOR && window.AMC_OPERATOR.isOwner) {
    controls.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-amc-action]');
      if (btn && !btn.disabled) handleAction(btn);
    });
  }

  apply();
  setInterval(tick, 1000);
  setInterval(poll, POLL_INTERVAL);
})();
