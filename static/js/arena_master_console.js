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
    paintSwitches();
    paintRehearsal();

    /* DG-04: real viewer presence */
    if (state.viewers && state.viewers.available) {
      setText('amc-lobby-viewers', state.viewers.arena_lobby_viewers);
      if (state.viewers.battles && state.viewers.battles.length) {
        setText('amc-viewers', state.viewers.battles[0].viewers);
      } else {
        setEmpty('amc-viewers', 'No active battle');
      }
    }
    if (state.voting && state.voting.length) {
      setText('amc-votes', state.voting[0].total_votes);
    } else {
      setEmpty('amc-votes', 'No active battle');
    }

    /* P06: voting integrity list */
    var votingList = document.getElementById('amc-voting-list');
    if (votingList) {
      votingList.textContent = '';
      (state.voting || []).forEach(function (v) {
        var li = document.createElement('li');
        var head = '#' + v.battle_id + ': ' + v.challenger_votes + ':' + v.opponent_votes;
        if (v.total_votes) head += ' (' + v.challenger_pct + '% / ' + v.opponent_pct + '%)';
        else head += ' (no votes yet)';
        if (v.is_tie) head += ' [TIE]';
        if (v.completion && v.completion.ready) {
          head += v.completion.blocked_by_tie ? ' [DEADLINE PASSED - TIE]' : ' [READY TO COMPLETE]';
        }
        li.textContent = head;
        var hint = document.createElement('span');
        hint.className = 'amc-panel__hint';
        hint.textContent = 'rejected attempts: ' + v.enforcement.rejected_attempts_total +
          ' total, ' + v.enforcement.rejected_attempts_24h + ' in 24h' +
          (v.suspicious_votes ? ', ' + v.suspicious_votes + ' flagged for review' : '') +
          ' | pulse: ' + v.pulse.chat_messages_last_hour + ' chat msg/h';
        li.appendChild(document.createElement('br'));
        li.appendChild(hint);
        votingList.appendChild(li);
      });
      if (!(state.voting || []).length) {
        votingList.innerHTML = '<li><span class="amc-empty">No battles in progress</span></li>';
      }
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
          li.textContent = a.chef + ': ' + a.artifact + ' (' + a.effect_type +
            ' +' + a.effect_value + ') · ' + a.status + (a.is_gift ? ' · gift' : '');
          artifacts.appendChild(li);
        });
        if (!(mon.artifacts_in_use || []).length) {
          artifacts.innerHTML = '<li><span class="amc-empty">None in play</span></li>';
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

  // Monotonic sequence: a slow response that arrives after a newer one
  // must never overwrite fresher state (P09 hardening).
  var pollSeq = 0;

  function poll() {
    var seq = ++pollSeq;
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
        if (seq !== pollSeq) return; // stale response, a newer poll finished
        state = fresh;
        apply();
        setText('amc-sys-status', 'Read models live · polling every 20s');
      })
      .catch(function () {
        if (seq !== pollSeq) return;
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

    if (kind === 'start_emulation') {
      if (!window.confirm('Start a battle EMULATION between the EMU bot chefs? ' +
          'It runs through the real services; advance it stage by stage with Emulation Step.')) return;
      fields = { action: 'start_emulation' };
    } else if (kind === 'emulation_step') {
      if (!primary) { showActionError('No battle to step.'); return; }
      fields = { action: 'emulation_step', battle_id: primary.id };
    } else if (kind === 'broadcast') {
      var msg = window.prompt('Broadcast notice (public, appears in the battle feed):');
      if (!msg) return;
      fields.action = 'broadcast';
      fields.message = msg;
      fields.correlation_id = Date.now().toString(36) + Math.random().toString(36).slice(2);
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
    } else if (kind === 'delete_test_battle') {
      if (!window.confirm(
        'DELETE TEST BATTLE #' + primary.id + '? This permanently removes the unscored '
        + 'test battle, its events, reactions and linked challenge. It is only available '
        + 'while Chef Battles is in test mode.'
      )) return;
      fields.action = 'delete_test_battle';
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

  /* DELEGATED ON THE DOCUMENT, not on the phase-button div. Bound to
     #amc-controls, this handler only ever saw the phase buttons - so "Start
     Only" and "Step", which carry data-amc-action but sit in their own card,
     did nothing at all when clicked. Every other handler in this file is
     already delegated this way. */
  if (window.AMC_OPERATOR && window.AMC_OPERATOR.isOwner) {
    document.addEventListener('click', function (e) {
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

  /* ── P05: chef safety actions (owner) — suspend/unsuspend/fraud flag ── */

  function handleSafetyAction(btn) {
    var action = btn.getAttribute('data-amc-safety');
    var slug = btn.getAttribute('data-chef');
    var fields = { action: action, chef_slug: slug };
    var reasonRequired = btn.getAttribute('data-reason-required') === '1';
    if (reasonRequired) {
      var prompt_text = action === 'suspend_chef'
        ? 'Suspend chef "' + slug + '". They will be notified. Enter reason (required):'
        : 'Set fraud flag on chef "' + slug + '". Enter note (required):';
      var reason = window.prompt(prompt_text);
      if (!reason) return;
      fields.reason = reason;
    } else {
      var confirm_text = action === 'unsuspend_chef'
        ? 'Lift suspension for chef "' + slug + '"?'
        : 'Clear fraud flag for chef "' + slug + '"?';
      if (!window.confirm(confirm_text)) return;
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
      var pbtn = e.target.closest('[data-amc-payout]');
      if (pbtn && !pbtn.disabled) handlePayout(pbtn);
      var sbtn = e.target.closest('[data-amc-safety]');
      if (sbtn && !sbtn.disabled) handleSafetyAction(sbtn);
    });
  }

  /* ── P08: payout decisions (owner) + battle reports (any operator) ── */

  function handlePayout(btn) {
    var id = btn.getAttribute('data-amc-payout');
    var decision = btn.getAttribute('data-decision');
    var fields = { payout_id: id, action: decision + '_payout' };
    if (decision === 'approve') {
      if (!window.confirm('APPROVE payout request #' + id +
          '? This triggers the real Stripe Connect transfer and cannot be undone from the console.')) return;
    } else {
      var reason = window.prompt('REJECT payout request #' + id +
        '. Issued reward records return to approved state. Enter the reason (required):');
      if (!reason) return;
      fields.reason = reason;
    }
    btn.disabled = true;
    showActionError('');
    postAction(fields)
      .then(function () { window.location.reload(); })
      .catch(function (err) { showActionError(err.message); btn.disabled = false; });
  }

  /* ── One-click full emulation: start (or pick up the running EMU
     battle) and step through every stage with a viewing pause. ──────── */

  /* ── The operator deck: three switches, a count and a purge ────────
     Each switch renders from state.operator on every poll rather than from
     what it last did, so a second console - or a setting pinned in a
     deployment - cannot leave this one showing a lie. */

  var SWITCHES = [
    { id: 'amc-switch-bots', action: 'set_emulation_bots', field: 'shown',
      on: function (op) { return op.emulation_bots_shown; },
      words: ['off floor', 'on floor'],
      locked: function (op) { return op.emulation_bots_pinned; },
      confirm: function (next) {
        return next
          ? 'Put the two EMU test chefs ON the public arena floor?'
          : 'Take the two EMU test chefs off the arena floor?';
      } },
    { id: 'amc-switch-runway', action: 'set_runway', field: 'armed',
      on: function (op) { return !!op.runway; },
      words: ['idle', 'armed'],
      confirm: function (next) {
        return next
          ? 'Arm the runway? The public arena polls every 2s instead of 20s ' +
            'for the next few minutes, so an emulation can be watched live.'
          : 'Stand the runway down?';
      } },
    { id: 'amc-switch-chat', action: 'set_chat_open', field: 'is_open',
      on: function (op) { return op.chat_is_open !== false; },
      words: ['closed', 'open'],
      confirm: function (next) {
        return next
          ? 'Open the arena chat to new lines again?'
          : 'Close the arena chat to NEW lines? Nothing is hidden and nothing ' +
            'is deleted - the panel and the history stay exactly as they are.';
      } }
  ];

  function paintSwitches() {
    var op = state.operator || {};
    SWITCHES.forEach(function (sw) {
      var btn = document.getElementById(sw.id);
      if (!btn) return;
      var on = !!sw.on(op);
      btn.setAttribute('aria-pressed', on ? 'true' : 'false');
      setText(sw.id + '-state', sw.words[on ? 1 : 0]);
      var locked = sw.locked ? !!sw.locked(op) : false;
      btn.disabled = locked;
      if (locked) btn.title = 'Pinned by a deployment setting; the console cannot override it.';
    });
    var note = document.getElementById('amc-switch-note');
    if (note) {
      note.textContent = op.emulation_bots_pinned
        ? 'ARENA_SHOW_EMULATION_BOTS is pinned in settings.'
        : '';
    }
  }

  function handleSwitch(btn) {
    var sw = SWITCHES.filter(function (s) { return s.id === btn.id; })[0];
    if (!sw) return;
    var next = btn.getAttribute('aria-pressed') !== 'true';
    if (!window.confirm(sw.confirm(next))) return;
    var fields = { action: sw.action };
    fields[sw.field] = next ? '1' : '0';
    btn.disabled = true;
    showActionError('');
    postAction(fields)
      .then(function () { return poll(); })
      .catch(function (err) { showActionError(err.message); })
      .finally(function () { btn.disabled = false; paintSwitches(); });
  }

  /* THE PURGE IS TWO PRESSES, ALWAYS. Count first - the server measures and
     removes nothing - and only then does the second button appear, carrying
     the number it is about to act on. A confirmation that does not say how
     much it is deleting is not a confirmation. */

  var purgeTotal = null;

  function renderPurge(report) {
    var list = document.getElementById('amc-purge-rows');
    var apply = document.getElementById('amc-purge-apply');
    if (!list) return;
    list.textContent = '';
    if (!report) {
      list.innerHTML = '<li><span class="amc-empty">Press Count to measure</span></li>';
      if (apply) apply.classList.add('amc-hidden');
      return;
    }
    [['Battles', 'battles'], ['Chat', 'chat'], ['Seats', 'seats'],
     ['Votes', 'votes'], ['Entries', 'entries'], ['Gifts', 'gifts'],
     ['Voters', 'voters'], ['Recipes', 'recipes']].forEach(function (pair) {
      var row = report[pair[1]];
      if (!row || !row.count) return;
      var li = document.createElement('li');
      li.textContent = pair[0] + ' ';
      var b = document.createElement('b');
      b.textContent = row.count;
      li.appendChild(b);
      if (row.examples && row.examples.length) {
        var hint = document.createElement('span');
        hint.textContent = ' — ' + row.examples.map(function (e) {
          return typeof e === 'string' ? e : (e.theme || ('#' + e.id));
        }).join(', ');
        li.appendChild(hint);
      }
      list.appendChild(li);
    });
    purgeTotal = report.total;
    if (!report.total) {
      list.innerHTML = '<li><span class="amc-empty">No test data on the arena</span></li>';
    }
    if (apply) {
      apply.classList.toggle('amc-hidden', !report.total);
      apply.textContent = 'Purge ' + report.total + ' rows';
    }
  }

  function handlePurge(btn) {
    var kind = btn.getAttribute('data-amc-purge');
    var fields = { action: 'purge_emulation_data' };
    if (kind === 'count') {
      fields.dry_run = '1';
    } else {
      if (!window.confirm('Permanently remove ' + purgeTotal + ' rows belonging to ' +
          'the EMU test bots? The bot accounts themselves are kept. Nothing a ' +
          'person made is in this set.')) return;
    }
    btn.disabled = true;
    showActionError('');
    postAction(fields)
      .then(function (res) {
        renderPurge(kind === 'count' ? res.report : res.remaining);
        return poll();
      })
      .catch(function (err) { showActionError(err.message); })
      .finally(function () { btn.disabled = false; });
  }

  /* THE REHEARSAL DIAL. It renders from state.rehearsal on every poll, the
     way the switches do, so the trace survives a reload and two consoles
     never disagree about which step the run is on. The buttons only ask the
     server to do something; what happened is read back, never assumed. */

  var REH_WORDS = {
    pass: 'PASS', fail: 'FAIL', missing_mechanism: 'MISSING',
    ui_mismatch: 'UI', forced: 'FORCED'
  };

  function paintRehearsal() {
    var reh = state.rehearsal || {};
    var run = reh.run;
    var trace = document.getElementById('amc-reh-trace');
    if (!trace) return;

    if (!run) {
      setEmpty('amc-reh-run', 'None yet');
      setEmpty('amc-reh-seed', '—');
      setEmpty('amc-reh-step', '—');
      setText('amc-reh-next', reh.next_step || '—');
      setEmpty('amc-reh-counts', '—');
      trace.innerHTML = '<li><span class="amc-empty">No run yet</span></li>';
      return;
    }

    setText('amc-reh-run', run.run_id + ' · ' + run.status_display);
    setText('amc-reh-seed', String(run.seed));
    setText('amc-reh-step', reh.done_steps + ' / ' + reh.total_steps);
    setText('amc-reh-next', reh.next_step || 'finished');
    var c = reh.counts || {};
    setText('amc-reh-counts',
      (c.pass || 0) + ' pass · ' + (c.missing || 0) + ' missing · ' +
      (c.fail || 0) + ' fail');

    trace.textContent = '';
    (reh.steps || []).forEach(function (s) {
      var li = document.createElement('li');
      li.className = 'amc-reh__step amc-reh__step--' + s.outcome;
      var tag = document.createElement('b');
      tag.className = 'amc-reh__tag';
      tag.textContent = REH_WORDS[s.outcome] || s.outcome;
      li.appendChild(tag);
      li.appendChild(document.createTextNode(' ' + s.title));
      if (s.detail) {
        var d = document.createElement('span');
        d.className = 'amc-reh__detail';
        d.textContent = s.detail;
        li.appendChild(d);
      }
      trace.appendChild(li);
    });
    if (!trace.children.length) {
      trace.innerHTML = '<li><span class="amc-empty">Started; no step run yet</span></li>';
    }
  }

  function rehPost(action) {
    return postAction({ action: action }).then(function (res) {
      if (res.rehearsal) { state.rehearsal = res.rehearsal; paintRehearsal(); }
      return res;
    });
  }

  function handleRehearsal(btn) {
    var kind = btn.getAttribute('data-amc-reh');
    if (kind === 'rehearsal_start' &&
        !window.confirm("Start scenario A? Jam O'Liver and CrestedTen live a whole " +
          'battle on the MAIN arena, through the real forms and services. It leaves ' +
          'a real battle row behind.')) return;
    if (kind === 'rehearsal_abort' &&
        !window.confirm('End the run in flight? The battle it created is left exactly ' +
          'where it stands - nothing is deleted.')) return;

    btn.disabled = true;
    showActionError('');

    /* RUN ALL IS THE SAME STEP, PRESSED UNTIL IT STOPS. There is no second
       server path for it: one endpoint, one step at a time, so a run he
       stepped through by hand and a run he let go are the same run. */
    var chain = kind === 'run_all'
      ? (function step() {
          return rehPost('rehearsal_step').then(function (res) {
            var reh = res.rehearsal || {};
            if (reh.running && reh.done_steps < reh.total_steps) return step();
            return res;
          });
        })()
      : rehPost(kind);

    chain
      .then(function () { return poll(); })
      .catch(function (err) { showActionError(err.message); })
      .finally(function () { btn.disabled = false; });
  }

  if (window.AMC_OPERATOR && window.AMC_OPERATOR.isOwner) {
    document.addEventListener('click', function (e) {
      var sbtn = e.target.closest('[data-amc-switch]');
      if (sbtn && !sbtn.disabled) handleSwitch(sbtn);
      var pbtn = e.target.closest('[data-amc-purge]');
      if (pbtn && !pbtn.disabled) handlePurge(pbtn);
      var rbtn = e.target.closest('[data-amc-reh]');
      if (rbtn && !rbtn.disabled) handleRehearsal(rbtn);
    });
  }

  var runBtn = document.getElementById('amc-run-emulation');
  if (runBtn && window.AMC_OPERATOR && window.AMC_OPERATOR.isOwner) {
    var STAGE_PAUSE_MS = 5000;
    var STAGE_LABELS = {
      scheduled: 'battle created — bots in the antechamber',
      menu_locked: 'both bots ready, menus being declared',
      active: 'combat!',
      ingredient_penalty: 'biathlon: locks and shots',
      cooking: 'bots are cooking',
      presentation: 'dishes presented',
      voting: 'audience voting',
      completed: 'DONE — crown decided',
    };

    function emuProgress(text) {
      var el = document.getElementById('amc-emu-progress');
      if (el) { el.textContent = text; el.classList.toggle('amc-hidden', !text); }
    }

    function findEmuBattle() {
      return (state.battles || []).find(function (b) {
        return b.theme && b.theme.indexOf('EMULATION') === 0;
      });
    }

    runBtn.addEventListener('click', function () {
      if (!window.confirm('Run a FULL battle emulation? A bot battle is created and ' +
          'walks through every stage to the crown automatically (~40 seconds, ' +
          'about 5 seconds per stage). Watch the panels, the ring and the battle room.')) return;
      runBtn.disabled = true;
      showActionError('');
      /* THE ARENA HAS TO BE LOOKING. Without this the emulation walks a stage
         every five seconds while the public page polls every twenty, so more
         than half of what it does happens between two polls and is never
         drawn. Armed here, stood down when the run ends. */
      postAction({ action: 'set_runway', armed: '1',
                   label: 'Emulation run' }).catch(function () {});

      var standDown = function () {
        postAction({ action: 'set_runway', armed: '0' }).catch(function () {});
      };

      var run = function (battleId) {
        postAction({ action: 'emulation_step', battle_id: battleId })
          .then(function (res) {
            emuProgress('Stage: ' + (STAGE_LABELS[res.after] || res.after) +
              (res.hits ? ' (hits ' + res.hits + ')' : '') +
              (res.winner ? ' — winner: ' + res.winner : ''));
            return poll().then(function () { return res; });
          })
          .then(function (res) {
            if (res.after === 'completed') {
              emuProgress('Emulation complete — ' + (STAGE_LABELS.completed) +
                (res.winner ? ' Winner: ' + res.winner : ''));
              standDown();
              runBtn.disabled = false;
              return;
            }
            window.setTimeout(function () { run(battleId); }, STAGE_PAUSE_MS);
          })
          .catch(function (err) {
            showActionError(err.message);
            emuProgress('Stopped: ' + err.message);
            standDown();
            runBtn.disabled = false;
          });
      };

      var existing = findEmuBattle();
      if (existing) {
        emuProgress('Continuing emulation battle #' + existing.id + '…');
        run(existing.id);
        return;
      }
      postAction({ action: 'start_emulation' })
        .then(function (res) {
          emuProgress('Battle #' + res.battle.id + ' created — ' + STAGE_LABELS.scheduled);
          return poll().then(function () {
            window.setTimeout(function () { run(res.battle.id); }, STAGE_PAUSE_MS);
          });
        })
        .catch(function (err) {
          showActionError(err.message);
          emuProgress('Stopped: ' + err.message);
          runBtn.disabled = false;
        });
    });
  }

  var reportBtn = document.getElementById('amc-submit-report');
  if (reportBtn) {
    reportBtn.addEventListener('click', function () {
      var battleId = reportBtn.getAttribute('data-battle');
      var summary = window.prompt('Battle report for battle #' + battleId +
        ' (goes to the owner). Summary (required):');
      if (!summary) return;
      var rec = window.prompt(
        'Recommendation - one of: approve_payout / withhold / needs_review / no_action');
      if (!rec) return;
      reportBtn.disabled = true;
      showActionError('');
      postAction({ action: 'submit_battle_report', battle_id: battleId,
                   summary: summary, recommendation: rec })
        .then(function () { window.location.reload(); })
        .catch(function (err) { showActionError(err.message); reportBtn.disabled = false; });
    });
  }

  apply();
  setInterval(tick, 1000);
  setInterval(poll, POLL_INTERVAL);
})();
