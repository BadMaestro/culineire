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

    /* P04: monitor panels (battle list, counts, event log, combat, artifacts) */
    var mon = state.monitor;
    if (mon) {
      Object.keys(mon.counts || {}).forEach(function (key) {
        var el = document.querySelector('[data-amc-count="' + key + '"]');
        if (el) el.textContent = mon.counts[key];
      });

      var battleList = document.getElementById('amc-battle-list');
      if (battleList) {
        battleList.textContent = '';
        (state.battles || []).forEach(function (b) {
          var li = document.createElement('li');
          var a = document.createElement('a');
          a.className = 'amc-link';
          a.href = b.url;
          a.textContent = '#' + b.id;
          li.appendChild(a);
          li.appendChild(document.createTextNode(
            ' ' + b.status_display + ' — ' + b.challenger.name + ' vs ' + b.opponent.name +
            (b.is_paused ? ' [PAUSED]' : '')));
          battleList.appendChild(li);
        });
        if (!(state.battles || []).length) {
          battleList.innerHTML = '<li><span class="amc-empty">No battles in progress</span></li>';
        }
      }

      var log = document.getElementById('amc-event-log');
      if (log) {
        log.textContent = '';
        (mon.events || []).forEach(function (e) {
          var li = document.createElement('li');
          li.textContent = '#' + e.battle_id + ' · ' + e.message.slice(0, 90);
          log.appendChild(li);
        });
        if (!(mon.events || []).length) {
          log.innerHTML = '<li><span class="amc-empty">No events yet</span></li>';
        }
      }

      var combat = document.getElementById('amc-combat-list');
      if (combat) {
        combat.textContent = '';
        (mon.detail || []).forEach(function (c) {
          var li = document.createElement('li');
          if (c.kind === 'combat') {
            li.textContent = '#' + c.battle_id + ' — round ' + c.current_round +
              ', hits ' + c.challenger_hits + ':' + c.opponent_hits;
            (c.declared_actions || []).forEach(function (a) {
              var span = document.createElement('span');
              span.className = 'amc-panel__hint';
              span.textContent = a.chef + ': ' + a.action_type + ' (' + a.moves_invested +
                ' moves)' + (a.is_locked ? ' · locked' : '');
              li.appendChild(document.createElement('br'));
              li.appendChild(span);
            });
          } else {
            li.textContent = '#' + c.battle_id + ' — biathlon: locks ' + c.locks_placed +
              '/' + c.max_locks + ', shots ' + c.shots_fired + '/' + c.max_shots +
              ' (' + c.winner + ' shooting at ' + c.loser + ')';
          }
          combat.appendChild(li);
        });
        if (!(mon.detail || []).length) {
          combat.innerHTML = '<li><span class="amc-empty">No combat in progress</span></li>';
        }
      }

      var artifacts = document.getElementById('amc-artifact-list');
      if (artifacts) {
        artifacts.textContent = '';
        (mon.artifacts_in_use || []).forEach(function (a) {
          var li = document.createElement('li');
          li.textContent = a.chef + ': ' + a.artifact + ' (' + a.effect_type + ' +' + a.effect_value + ')';
          artifacts.appendChild(li);
        });
        if (!(mon.artifacts_in_use || []).length) {
          artifacts.innerHTML = '<li><span class="amc-empty">None reserved</span></li>';
        }
      }
    }

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

  /* ── P05: moderation actions (owner only) ───────────────────────── */

  function handleModAction(btn) {
    var kind = btn.getAttribute('data-amc-mod');
    var fields = {};

    if (kind === 'entry') {
      var status = btn.getAttribute('data-status');
      var adverse = status !== 'approved';
      var reason = '';
      if (adverse) {
        reason = window.prompt('Flag entry #' + btn.getAttribute('data-entry') +
          '. The chef will be notified. Enter the reason (required):');
        if (!reason) return;
      } else if (!window.confirm('Approve entry #' + btn.getAttribute('data-entry') + '?')) {
        return;
      }
      fields = { action: 'moderate_entry', entry_id: btn.getAttribute('data-entry'),
                 new_status: status, reason: reason };
    } else if (kind === 'report') {
      var note = window.prompt(
        (btn.getAttribute('data-status') === 'dismissed' ? 'Dismiss' : 'Mark reviewed') +
        ' report #' + btn.getAttribute('data-report') + '. Enter a review note (required):');
      if (!note) return;
      fields = { action: 'review_report', report_id: btn.getAttribute('data-report'),
                 new_status: btn.getAttribute('data-status'), reason: note };
    } else if (kind === 'stream') {
      var streamReason = window.prompt(
        'END STREAM session #' + btn.getAttribute('data-session') +
        '. The platform record is terminated and the chef is notified. ' +
        'No provider-side kill is performed (no provider integration is configured). ' +
        'Enter the reason (required):');
      if (!streamReason) return;
      fields = { action: 'end_stream', session_id: btn.getAttribute('data-session'),
                 reason: streamReason };
    } else {
      return;
    }

    btn.disabled = true;
    showActionError('');
    postAction(fields)
      .then(function () { window.location.reload(); })
      .catch(function (err) { showActionError(err.message); btn.disabled = false; });
  }

  if (window.AMC_OPERATOR && window.AMC_OPERATOR.isOwner) {
    document.addEventListener('click', function (e) {
      var btn = e.target.closest('[data-amc-mod]');
      if (btn && !btn.disabled) handleModAction(btn);
    });
  }

  apply();
  setInterval(tick, 1000);
  setInterval(poll, POLL_INTERVAL);
})();
