/*
 * Arena command deck — the live read model around the floor: metrics, phase
 * rail, deadline countdown, centre live stage, crown ladder and recent gifts.
 *
 * Ported verbatim in behaviour from arena_puzzle.js so the deck keeps working
 * when the legacy renderer is removed. It is deliberately separate from the
 * renderer: the deck only touches the surrounding panels and never the SVG
 * floor, so either can change without the other.
 *
 * Every refresher no-ops when its element is absent, which is what lets the
 * same file serve the arena page and the Arena Master Console.
 */
(function (global) {
  'use strict';

  var NS = 'http://www.w3.org/2000/svg';

  var deadlineTicker = null;
  var deadlineAnchor = null;
  /* Visual Contract §5: empty widgets must show the mockup fixture until real
     battle data is wired. Stable countdown so polls do not reset the clock. */
  var fixtureDeadlineUntil = null;

  var LIVE_FIXTURE = {
    metrics: { active_viewers: '2.4K', public_votes: '3.7K', battle_gifts: '620' },
    crown_streak: 3,
    crown_ladder: [
      { name: 'GreenBear', slug: 'greenbear', crowns: 3 },
      { name: 'Aidan Byrne', slug: 'aidan-byrne', crowns: 2 },
      { name: 'ChefOrla', slug: 'cheforla', crowns: 1 },
      { name: 'Fire&Steel', slug: 'fire-steel', crowns: 1 }
    ],
    recent_gifts: [
      { recipient: 'Aidan Byrne', recipient_slug: 'aidan-byrne', item: 'Artifact Set', tokens: 120 },
      { recipient: 'Luca Moretti', recipient_slug: 'luca-moretti', item: 'Champagne', tokens: 100 },
      { recipient: 'Both Chefs', recipient_slug: '', item: 'Good Luck', tokens: 50 }
    ],
    top_supporter: { name: 'Sláinte Club', tokens: 420 },
    phase: { step: 4, key: 'cooking', label: 'Cooking' },
    center: {
      type: 'active_battle',
      battle_id: 'fixture',
      status_display: 'Cooking',
      theme: 'Irish stew showdown',
      battle_url: '/chef-battle/',
      challenger: {
        name: 'Aidan Byrne',
        side: 'challenger',
        avatar_url: '/static/images/male-avatar.webp',
        profile_url: '/chef-battle/'
      },
      opponent: {
        name: 'Luca Moretti',
        side: 'opponent',
        avatar_url: '/static/images/neutral-avatar.webp',
        profile_url: '/chef-battle/'
      }
    },
    deadline_seconds: 8 * 60 + 37
  };

  function byId(id) { return document.getElementById(id); }

  function metricsAreEmpty(metrics) {
    if (!metrics) { return true; }
    function n(value) {
      if (value === null || typeof value === 'undefined' || value === '') { return 0; }
      if (typeof value === 'string' && /[kKmM]/.test(value)) { return 1; }
      var num = Number(value);
      return Number.isFinite(num) ? num : 0;
    }
    return n(metrics.active_viewers) === 0
      && n(metrics.public_votes) === 0
      && n(metrics.battle_gifts) === 0;
  }

  function hasLiveBattleCentre(center) {
    if (!center) { return false; }
    if (center.type !== 'active_battle' && center.type !== 'facing_pair') { return false; }
    var id = center.battle_id;
    return id !== null && typeof id !== 'undefined' && String(id) !== '' && String(id) !== 'fixture';
  }

  function hydrateFixtures(data) {
    if (!data) { return data; }
    var out = Object.assign({}, data);
    var metrics = out.arena_metrics || out.metrics;
    if (metricsAreEmpty(metrics)) {
      out.metrics = Object.assign({}, LIVE_FIXTURE.metrics);
      out.arena_metrics = out.metrics;
    }
    if (!Number(out.crown_streak)) {
      out.crown_streak = LIVE_FIXTURE.crown_streak;
    }
    if (!Array.isArray(out.crown_ladder) || !out.crown_ladder.length) {
      out.crown_ladder = LIVE_FIXTURE.crown_ladder.slice();
    }
    if (!Array.isArray(out.recent_gifts) || !out.recent_gifts.length) {
      out.recent_gifts = LIVE_FIXTURE.recent_gifts.slice();
    }
    if (!out.top_supporter || !out.top_supporter.name) {
      out.top_supporter = Object.assign({}, LIVE_FIXTURE.top_supporter);
    }

    if (!hasLiveBattleCentre(out.center)) {
      out.center = Object.assign({}, LIVE_FIXTURE.center, {
        challenger: Object.assign({}, LIVE_FIXTURE.center.challenger),
        opponent: Object.assign({}, LIVE_FIXTURE.center.opponent)
      });
      out.phase = Object.assign({}, LIVE_FIXTURE.phase);
      out.arena_phase = out.phase;
      if (!fixtureDeadlineUntil) {
        fixtureDeadlineUntil = Date.now() + LIVE_FIXTURE.deadline_seconds * 1000;
      }
      var remain = Math.max(0, Math.floor((fixtureDeadlineUntil - Date.now()) / 1000));
      out.deadline = {
        seconds_remaining: remain,
        kind: 'cooking',
        label: 'Cooking ends',
        deadline_iso: new Date(fixtureDeadlineUntil).toISOString()
      };
      out.server_time = new Date().toISOString();
      out._fixture_surface = true;
    } else {
      fixtureDeadlineUntil = null;
      out._fixture_surface = false;
    }
    return out;
  }

  function refreshBroadcastCopy(data) {
    var liveNote = byId('arena-live-note');
    var floorStrong = byId('arena-floor-caption-strong');
    var floorEm = byId('arena-floor-caption-em');
    var tickerPhase = byId('arena-ticker-phase');
    var tickerWatch = byId('arena-ticker-watching');
    var metrics = (data && (data.arena_metrics || data.metrics)) || {};
    var viewers = metricText(metrics.active_viewers);
    if (data && data._fixture_surface) {
      if (liveNote) {
        liveNote.textContent = 'LIVE COOKING IN PROGRESS · CHEFS EARNING THE CROWD';
        liveNote.classList.add('is-live');
      }
      if (floorStrong) { floorStrong.textContent = 'Live cooking in progress'; }
      if (floorEm) { floorEm.textContent = 'One scene · live hierarchy · fixture until wired'; }
      if (tickerPhase) { tickerPhase.textContent = 'Cooking'; }
    }
    if (tickerWatch) { tickerWatch.textContent = viewers + ' watching'; }
  }

  function svgEl(tag, attrs) {
    var node = document.createElementNS(NS, tag);
    Object.keys(attrs || {}).forEach(function (key) { node.setAttribute(key, attrs[key]); });
    return node;
  }

  function profileHref(container, slug) {
    var template = container && container.getAttribute('data-profile-template');
    if (!template || !slug) { return '#'; }
    return template.replace('arena-chef-slug', encodeURIComponent(slug));
  }

  function clearPanel(container) {
    while (container && container.firstChild) { container.removeChild(container.firstChild); }
  }

  function appendPanelEmpty(container, message) {
    var item = document.createElement('li');
    item.className = 'arena-panel__empty';
    item.textContent = message;
    container.appendChild(item);
  }

  function metricText(value) {
    return value === null || typeof value === 'undefined' ? '—' : String(value);
  }

  /* ---- panels ---- */

  function refreshCrownLadder(ladder) {
    var container = byId('arena-crown-ladder');
    if (!container || !Array.isArray(ladder)) { return; }
    clearPanel(container);
    if (!ladder.length) {
      appendPanelEmpty(container, 'No crowns have been awarded today.');
      return;
    }
    ladder.forEach(function (entry, index) {
      var chef = entry || {};
      var item = document.createElement('li');
      var position = document.createElement('span');
      var link = document.createElement('a');
      var crowns = document.createElement('em');
      position.textContent = String(index + 1);
      link.href = profileHref(container, chef.slug);
      link.textContent = chef.name || 'Chef';
      crowns.textContent = String(chef.crowns || 0) + ' crown' + (Number(chef.crowns) === 1 ? '' : 's');
      item.appendChild(position);
      item.appendChild(link);
      item.appendChild(crowns);
      container.appendChild(item);
    });
  }

  function refreshRecentGifts(gifts) {
    var container = byId('arena-recent-gifts');
    if (!container || !Array.isArray(gifts)) { return; }
    clearPanel(container);
    if (!gifts.length) {
      appendPanelEmpty(container, 'No battle gifts have been delivered yet.');
      return;
    }
    gifts.forEach(function (entry) {
      var gift = entry || {};
      var item = document.createElement('li');
      var icon = svgEl('svg', { 'class': 'arena-ico', 'aria-hidden': 'true' });
      var copy = document.createElement('span');
      var recipient = document.createElement('a');
      var artifact = document.createElement('b');
      var tokens = document.createElement('em');
      icon.appendChild(svgEl('use', { href: '#ad-gift' }));
      recipient.href = profileHref(container, gift.recipient_slug);
      recipient.textContent = gift.recipient || 'Chef';
      artifact.textContent = gift.item || 'Gift';
      tokens.textContent = String(gift.tokens || 0) + 'T';
      copy.appendChild(recipient);
      copy.appendChild(artifact);
      item.appendChild(icon);
      item.appendChild(copy);
      item.appendChild(tokens);
      container.appendChild(item);
    });
  }

  function refreshPanels(data) {
    if (!data) { return; }
    if (Object.prototype.hasOwnProperty.call(data, 'crown_streak')) {
      var streak = byId('arena-crown-streak');
      if (streak) { streak.textContent = String(data.crown_streak || 0); }
    }
    if (Object.prototype.hasOwnProperty.call(data, 'crown_ladder')) { refreshCrownLadder(data.crown_ladder); }
    if (Object.prototype.hasOwnProperty.call(data, 'recent_gifts')) { refreshRecentGifts(data.recent_gifts); }
    if (Object.prototype.hasOwnProperty.call(data, 'top_supporter')) { refreshTopSupporter(data.top_supporter); }
  }

  function refreshTopSupporter(top) {
    var el = byId('arena-top-supporter');
    if (!el) { return; }
    if (top && top.name) {
      el.textContent = 'Top Supporter: ' + top.name + ' ' + String(top.tokens || 0) + 'T';
    } else {
      el.textContent = 'Top Supporter: —';
    }
  }

  /* ---- deadline countdown ---- */

  function formatRemaining(seconds) {
    var total = Math.max(0, Number(seconds) || 0);
    var days = Math.floor(total / 86400);
    var clock = [
      Math.floor((total % 86400) / 3600),
      Math.floor((total % 3600) / 60),
      total % 60
    ].map(function (value) { return String(value).padStart(2, '0'); }).join(':');
    return (days ? String(days) + 'd ' : '') + clock;
  }

  function paintDeadline() {
    var panel = byId('arena-phase-deadline');
    var value = panel && panel.querySelector('strong');
    if (!panel || !value || !deadlineAnchor) { return; }
    var elapsed = Math.max(0, (Date.now() - deadlineAnchor.receivedAt) / 1000);
    value.textContent = formatRemaining(Math.max(0, Math.floor(deadlineAnchor.serverRemaining - elapsed))) + ' remaining';
  }

  function stopDeadlineTicker() {
    if (deadlineTicker) { global.clearInterval(deadlineTicker); }
    deadlineTicker = null;
    deadlineAnchor = null;
  }

  function refreshDeadline(data) {
    var panel = byId('arena-phase-deadline');
    if (!panel) { return; }
    var deadline = data && data.deadline;
    var value = panel.querySelector('strong');
    var caption = byId('arena-deadline-label');
    if (!deadline || typeof deadline.seconds_remaining === 'undefined') {
      stopDeadlineTicker();
      panel.classList.add('is-empty');
      panel.setAttribute('data-deadline-iso', '');
      panel.setAttribute('data-deadline-kind', '');
      if (caption) { caption.textContent = 'Live deadline'; }
      if (value) { value.textContent = 'No active deadline'; }
      return;
    }
    panel.classList.remove('is-empty');
    panel.setAttribute('data-deadline-iso', deadline.deadline_iso || '');
    // The server already works out what this particular countdown ends —
    // submission, voting or the battle itself. Say that rather than "deadline",
    // and re-say it on every poll: the phase changes under a running clock.
    panel.setAttribute('data-deadline-kind', deadline.kind || '');
    if (caption && deadline.label) { caption.textContent = deadline.label; }
    // Reconcile against the authoritative server clock so a client with a
    // skewed clock still counts down from the right number.
    var deadlineAt = Date.parse(deadline.deadline_iso || '');
    var serverAt = Date.parse(data.server_time || '');
    var serverRemaining = Number(deadline.seconds_remaining);
    if (!Number.isNaN(deadlineAt) && !Number.isNaN(serverAt)) {
      serverRemaining = Math.max(0, Math.floor((deadlineAt - serverAt) / 1000));
    }
    deadlineAnchor = { receivedAt: Date.now(), serverRemaining: Math.max(0, serverRemaining || 0) };
    paintDeadline();
    if (!deadlineTicker) { deadlineTicker = global.setInterval(paintDeadline, 1000); }
  }

  /* ---- metrics + phase rail ---- */

  function refreshReadModel(data) {
    if (!data) { return; }
    var metrics = data.arena_metrics || data.metrics;
    if (metrics) {
      var viewers = byId('arena-metric-viewers');
      var votes = byId('arena-metric-votes');
      var gifts = byId('arena-metric-gifts');
      if (viewers) { viewers.textContent = metricText(metrics.active_viewers); }
      if (votes) { votes.textContent = metricText(metrics.public_votes); }
      if (gifts) { gifts.textContent = metricText(metrics.battle_gifts); }
    }

    var phase = data.arena_phase || data.phase;
    var phaseRail = data.phase_rail || data.arena_phase_rail;
    var rail = byId('arena-phase-rail');
    if (!rail) { return; }
    var phaseName = byId('arena-current-phase');
    var phaseCopy = byId('arena-current-phase-copy');
    var activeStep = phase && phase.step ? Number(phase.step) : 0;

    if (Array.isArray(phaseRail) && phaseRail.length) {
      ensurePhaseRailSteps(rail, phaseRail);
    }
    var steps = rail.querySelectorAll('[data-phase-step]');

    if (!activeStep) {
      Array.prototype.forEach.call(steps, function (step) {
        step.classList.remove('is-active', 'is-complete');
        step.removeAttribute('aria-current');
      });
      rail.classList.add('is-open');
      rail.setAttribute('data-phase-key', '');
      if (phaseName) { phaseName.textContent = 'Open floor'; }
      if (phaseCopy) { phaseCopy.textContent = 'Choose a chef on the floor to inspect their profile or issue a challenge.'; }
      return;
    }
    rail.classList.remove('is-open');
    Array.prototype.forEach.call(steps, function (step) {
      var stepNo = Number(step.getAttribute('data-phase-step'));
      var isActive = stepNo === activeStep;
      step.classList.toggle('is-active', isActive);
      step.classList.toggle('is-complete', stepNo > 0 && stepNo < activeStep);
      if (isActive) { step.setAttribute('aria-current', 'step'); }
      else { step.removeAttribute('aria-current'); }
    });
    rail.setAttribute('data-phase-key', phase.key || '');
    if (phaseName) { phaseName.textContent = phase.label || 'Battle in progress'; }
    if (phaseCopy) { phaseCopy.textContent = 'The centre tile opens the live battle room, chat and public actions.'; }
  }

  function ensurePhaseRailSteps(rail, phaseRail) {
    var existing = rail.querySelectorAll('[data-phase-step]');
    var needsRebuild = existing.length !== phaseRail.length;
    if (!needsRebuild) {
      Array.prototype.forEach.call(existing, function (el, idx) {
        var rung = phaseRail[idx];
        if (!rung) { needsRebuild = true; return; }
        if (Number(el.getAttribute('data-phase-step')) !== Number(rung.step)) { needsRebuild = true; }
        if ((el.getAttribute('data-phase-key') || '') !== String(rung.key || '')) { needsRebuild = true; }
        var label = el.querySelector('b');
        if (label && rung.label && label.textContent !== String(rung.label)) {
          label.textContent = String(rung.label);
        }
      });
    }
    if (!needsRebuild) { return; }
    rail.textContent = '';
    phaseRail.forEach(function (rung) {
      if (!rung || !rung.step) { return; }
      var step = document.createElement('span');
      step.className = 'arena-phase-step';
      step.setAttribute('data-phase-step', String(rung.step));
      if (rung.key) { step.setAttribute('data-phase-key', String(rung.key)); }
      var index = document.createElement('span');
      index.className = 'arena-phase-step__index';
      index.setAttribute('aria-hidden', 'true');
      index.textContent = String(rung.step);
      var label = document.createElement('b');
      label.textContent = String(rung.label || '');
      step.appendChild(index);
      step.appendChild(document.createTextNode(' '));
      step.appendChild(label);
      rail.appendChild(step);
    });
  }

  /* ---- centre live stage ---- */

  function centreKey(center) {
    if (!center) { return 'empty'; }
    if (center.type === 'active_battle' || center.type === 'facing_pair') {
      return 'battle-' + String(center.battle_id || 'unknown');
    }
    if (center.type === 'crown') { return 'crown-' + String(center.name || 'holder'); }
    return 'empty';
  }

  function appendStageChef(stage, label, chef, modifier) {
    var card = document.createElement('article');
    var image = document.createElement('img');
    var copy = document.createElement('div');
    var role = document.createElement('span');
    var name = document.createElement('strong');
    var media = null;
    card.className = 'arena-live-chef' + (modifier ? ' ' + modifier : '');
    if (chef.side) {
      card.setAttribute('data-side', String(chef.side));
    }
    image.src = chef.avatar_url || '';
    image.alt = chef.name || 'Chef';
    image.width = 72;
    image.height = 72;
    role.textContent = label;
    name.textContent = chef.name || 'Chef';
    copy.appendChild(role);
    copy.appendChild(name);
    if (chef.profile_url) {
      media = document.createElement('a');
      media.className = 'arena-live-chef__profile';
      media.href = chef.profile_url;
      media.setAttribute('aria-label', (chef.name || 'Chef') + ' profile');
      if (chef.slug) {
        media.setAttribute('data-chef-slug', String(chef.slug));
      }
      media.appendChild(image);
      media.appendChild(copy);
      card.appendChild(media);
    } else {
      card.appendChild(image);
      card.appendChild(copy);
    }
    stage.appendChild(card);
  }

  function appendStageCentre(stage, options) {
    var link = document.createElement('a');
    var label = document.createElement('span');
    var title = document.createElement('b');
    var detail = document.createElement('em');
    link.className = 'arena-live-centre' + (options.className ? ' ' + options.className : '');
    link.href = options.href || '#arena-render';
    link.setAttribute('aria-label', options.ariaLabel);
    label.textContent = options.label;
    title.textContent = options.title;
    detail.textContent = options.detail;
    link.appendChild(label);
    link.appendChild(title);
    link.appendChild(detail);
    stage.appendChild(link);
  }

  function appendStageNote(stage, text) {
    var note = document.createElement('p');
    note.className = 'arena-live-awaiting';
    note.textContent = text;
    stage.appendChild(note);
  }

  function formatDateTime(value) {
    var date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) { return ''; }
    return date.toLocaleString(undefined, {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }

  function crownNote(center) {
    var until = formatDateTime(center.crown_until);
    return until ? 'Crown held until ' + until + '.' : 'The centre awaits the next challenge.';
  }

  function refreshCrownWindow(data) {
    var center = data && data.center;
    if (!center || center.type !== 'crown') { return; }
    var stage = byId('arena-live-stage');
    var note = stage && stage.querySelector('.arena-live-awaiting');
    if (!note) { return; }
    note.textContent = crownNote(center);
  }

  function refreshLiveStage(data) {
    var stage = byId('arena-live-stage');
    var center = data && data.center;
    if (!stage || !center) { return; }
    var key = centreKey(center);
    // Rebuilding an unchanged stage would restart avatar loads on every poll.
    if (stage.getAttribute('data-centre-key') === key) { return; }
    clearPanel(stage);
    stage.setAttribute('data-centre-key', key);

    if (center.type === 'active_battle' || center.type === 'facing_pair') {
      appendStageChef(stage, 'Challenger', center.challenger || {}, 'arena-live-chef--challenger');
      appendStageCentre(stage, {
        href: center.battle_url,
        className: 'battle-cursor-target js-battle-cursor-target',
        ariaLabel: 'Open the live battle room',
        label: center.status_display || center.battle_phase || 'Live battle',
        title: 'VS',
        detail: center.theme || 'Open battle room'
      });
      appendStageChef(stage, 'Opponent', center.opponent || {}, 'arena-live-chef--opponent');
      return;
    }

    if (center.type === 'crown') {
      appendStageChef(stage, 'Crown holder', center, 'arena-live-chef--crown');
      appendStageCentre(stage, {
        href: center.profile_url,
        className: 'arena-live-centre--crown',
        ariaLabel: 'View crown holder profile',
        label: 'Current holder',
        title: 'Crown',
        detail: 'View profile'
      });
      appendStageNote(stage, crownNote(center));
      return;
    }

    appendStageNote(stage, 'No live battle is holding the centre.');
    appendStageCentre(stage, {
      href: '/chef-battle/rankings/',
      className: 'arena-live-centre--quiet',
      ariaLabel: 'Explore Arena ranks',
      label: 'Arena centre',
      title: 'Open',
      detail: 'Explore the ranks'
    });
    appendStageNote(stage, 'Choose a chef below to start a challenge.');
  }

  /* ---- entry point ---- */

  function refresh(data) {
    if (!data) { return; }
    data = hydrateFixtures(data);
    refreshPanels(data);
    refreshReadModel(data);
    refreshDeadline(data);
    refreshLiveStage(data);
    refreshCrownWindow(data);
    refreshBroadcastCopy(data);
  }

  global.ArenaDeck = {
    refresh: refresh,
    centreKey: centreKey,
    formatRemaining: formatRemaining,
    hydrateFixtures: hydrateFixtures
  };
})(window);
