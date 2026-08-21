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
        liveNote.textContent = 'Live Now';
        liveNote.classList.add('is-live');
      }
      if (floorStrong) { floorStrong.textContent = 'Live cooking in progress'; }
      if (floorEm) { floorEm.textContent = 'One scene · live hierarchy · fixture until wired'; }
      if (tickerPhase) { tickerPhase.textContent = 'Cooking'; }
    } else if (liveNote && !hasLiveBattleCentre(data && data.center)) {
      // The fixture branch had no else, so once it had written "Live Now" the
      // caption survived every later poll and only a reload cleared it. With the
      // fixture disconnected this branch never fired, which would have hidden
      // the fault rather than fixed it — so the retraction is written now, while
      // the reason is known, and not left for whoever switches the fixture back
      // on. Only the live marker is withdrawn; the floor captions belong to the
      // template, which renders them truthfully from active_battle.
      liveNote.classList.remove('is-live');
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

  /* ---- T21: the strip is a distance, not a list ----------------------------
   *
   * Owner, 2026-08-15: the NEXT BATTLE strip - the band directly above THE
   * KITCHEN FLOOR caption - is the STARTING POSITION. A pair that has just
   * accepted stands furthest from it with 48 hours on the clock, and moves
   * visibly closer as the timer runs down; on the second Ready it takes the
   * nearest place in the queue. Until now the pills were ordered by time and
   * carried no distance at all, so nothing on the screen moved.
   *
   * The offset is written as a percentage into a custom property and the CSS
   * transitions it, so the movement is one declaration rather than an
   * animation loop. Pills keep their DOM order - soonest first - and a
   * minimum separation is enforced here so two battles at nearly the same
   * time cannot stack on top of each other: distance still reads as time,
   * and the board stays legible, which is the point of it.
   */
  var PREPARATION_WINDOW_MS = 48 * 60 * 60 * 1000;
  var upcomingTicker = null;

  function placeUpcomingPills() {
    var container = byId('arena-upcoming');
    if (!container) { return; }
    var items = container.querySelectorAll('li[data-start-time]');
    if (!items.length) { return; }
    var now = Date.now();
    // The distance is spent out of the room the pills DO NOT already occupy.
    // A percentage of the track would have been simpler and wrong: the pills
    // have widths of their own, so percentages plus widths overflow the strip
    // and wrap it into a stack of rows - and the arena has to fit the screen
    // whole (A07). Measuring first means the furthest pair sits at the far end
    // of the strip and the nearest against the label, in one row, at any width.
    var style = global.getComputedStyle ? global.getComputedStyle(container) : null;
    var gapPx = style ? (parseFloat(style.columnGap) || 0) : 0;
    var occupied = gapPx * (items.length - 1);
    Array.prototype.forEach.call(items, function (item) { occupied += item.offsetWidth; });
    var available = Math.max(0, container.clientWidth - occupied);

    // The track is a flex row, so what each pill carries is the GAP AHEAD of
    // it - the distance from the pill before it - and those add up along the
    // strip. Writing the absolute position into a margin would measure every
    // pill from its neighbour instead of from the label, which is the mistake
    // this comment exists to stop somebody making again.
    var previousPx = 0;
    Array.prototype.forEach.call(items, function (item) {
      var startsAt = Date.parse(item.getAttribute('data-start-time') || '');
      var px;
      if (Number.isNaN(startsAt)) {
        px = previousPx;
      } else {
        var remaining = Math.max(0, startsAt - now);
        px = Math.min(1, remaining / PREPARATION_WINDOW_MS) * available;
      }
      // Never behind the pill in front of it: the list is ordered soonest
      // first, and a pill that overtook its neighbour would say the queue runs
      // the other way.
      if (px < previousPx) { px = previousPx; }
      item.style.setProperty('--arena-next-offset', Math.round(px - previousPx) + 'px');
      previousPx = px;
    });
  }

  function refreshUpcoming(list) {
    var container = byId('arena-upcoming');
    if (!container || !Array.isArray(list)) { return; }
    clearPanel(container);
    if (!list.length) {
      var empty = document.createElement('li');
      empty.className = 'arena-next-board__empty';
      empty.textContent = 'No battles are scheduled yet.';
      container.appendChild(empty);
      return;
    }
    // Half a pill: avatar then name, mirrored for the opponent so the two faces
    // sit at the outer ends with the clock between them.
    function pillSide(chef, role) {
      var side = document.createElement('span');
      var face = document.createElement('img');
      var name = document.createElement('b');
      side.className = 'arena-next-pill__side' +
        (role === 'opponent' ? ' arena-next-pill__side--opponent' : '');
      face.src = (chef && chef.avatar_url) || '';
      face.alt = '';
      face.width = 22;
      face.height = 22;
      face.loading = 'lazy';
      name.textContent = (chef && chef.name) || 'Chef';
      side.appendChild(face);
      side.appendChild(name);
      return side;
    }

    list.forEach(function (entry) {
      var battle = entry || {};
      var item = document.createElement('li');
      var link = document.createElement('a');
      var when = document.createElement('em');
      link.className = 'arena-next-pill';
      link.href = battle.battle_url || '#';
      when.className = 'arena-next-pill__when';
      when.title = "Approximate start, from the chefs' preparation timer";
      // The server's own short form wins here. formatDateTime spells out
      // "6 Aug 2026, 00:06", which is four times wider than a pill a third of
      // the rail across, and the time is approximate anyway - start_display is
      // already a clock within the day and a date beyond it.
      when.textContent = battle.start_display || formatDateTime(battle.start_time) || '';
      if (battle.start_time) { when.setAttribute('data-start-time', battle.start_time); }
      link.appendChild(pillSide(battle.challenger, 'challenger'));
      link.appendChild(when);
      link.appendChild(pillSide(battle.opponent, 'opponent'));
      item.appendChild(link);
      if (battle.start_time) { item.setAttribute('data-start-time', battle.start_time); }
      container.appendChild(item);
    });
    // T21: place them the moment they exist, then keep them moving between
    // polls. One interval for the whole board, registered once - the same
    // pattern as the deadline ticker above, and the reason it is guarded.
    placeUpcomingPills();
    if (!upcomingTicker) { upcomingTicker = global.setInterval(placeUpcomingPills, 30000); }
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
    if (Object.prototype.hasOwnProperty.call(data, 'upcoming')) { refreshUpcoming(data.upcoming); }
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
      // The status-facts list renders the SAME viewer count as the deck. It was
      // not updated here, so it kept the server value and read 0 next to a
      // hydrated 2.4K — the same number twice on one screen, disagreeing.
      var factsViewers = byId('arena-facts-viewers');
      if (viewers) { viewers.textContent = metricText(metrics.active_viewers); }
      if (factsViewers) { factsViewers.textContent = metricText(metrics.active_viewers); }
      if (votes) { votes.textContent = metricText(metrics.public_votes); }
      if (gifts) { gifts.textContent = metricText(metrics.battle_gifts); }
    }

    var phase = data.arena_phase || data.phase;
    var phaseRail = data.phase_rail || data.arena_phase_rail;
    var rail = byId('arena-phase-rail');
    if (!rail) { return; }
    var phaseName = byId('arena-current-phase');
    var phaseCopy = byId('arena-current-phase-copy');
    var phaseNext = byId('arena-phase-next');
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
      if (phaseNext) { phaseNext.hidden = true; }
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
    if (phaseNext) {
      var nextLabel = rail.querySelector(
        '[data-phase-step="' + String(activeStep + 1) + '"] b'
      );
      phaseNext.hidden = !nextLabel;
      if (nextLabel) {
        var phaseNextText = phaseNext.querySelector('b');
        if (phaseNextText) { phaseNextText.textContent = nextLabel.textContent; }
      }
    }
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

    /* THE STAGE DESCRIPTIONS ARE NOT IN THE POLL, so a rebuild must not throw
       them away. They ride in with the document and stay put - the seven
       stages of a battle never change, and a payload budget keeps the poll
       from carrying 11KB of text every ten seconds to say so (see
       get_arena_phase_rail in selectors.py). Carried across by phase key
       rather than by position, because a rebuild is exactly the case where
       positions may have moved. */
    var carriedBlurbs = {};
    Array.prototype.forEach.call(existing, function (el) {
      var key = el.getAttribute('data-phase-key');
      var blurb = el.getAttribute('data-phase-blurb');
      if (key && blurb) { carriedBlurbs[key] = blurb; }
    });

    rail.textContent = '';
    phaseRail.forEach(function (rung) {
      if (!rung || !rung.step) { return; }
      var step = document.createElement('span');
      step.className = 'arena-phase-step';
      step.setAttribute('data-phase-step', String(rung.step));
      if (rung.key) { step.setAttribute('data-phase-key', String(rung.key)); }
      /* The stage's own sentence travels with the marker, so a rail the poll
         rebuilds explains itself exactly as the server-rendered one does.
         Left off when the payload carries none rather than invented here:
         one source for this text, and it is the server's. */
      var carried = rung.key ? carriedBlurbs[String(rung.key)] : null;
      if (carried) { step.setAttribute('data-phase-blurb', carried); }
      step.setAttribute('role', 'button');
      step.setAttribute('tabindex', '0');
      step.setAttribute('aria-controls', 'arena-phase-blurb');
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
    // FIXTURE DISCONNECTED (Owner, 2026-08-03). One line, reversible: put
    // `data = hydrateFixtures(data);` back here to restore it. The function, the
    // LIVE_FIXTURE constant and the export below are all deliberately kept.
    //
    // What it was doing, measured on production the day it was switched off: the
    // server sent active_viewers 0, public_votes 0, battle_gifts 0 and an empty
    // crown ladder, while the screen showed 2.4K, 3.7K, 620, a populated ladder
    // and a battle between two people who do not exist. It was labelled "fixture
    // until wired" on screen, and it was harmless only while the Arena stays
    // staff-only — on the day it opens, the first thing a visitor would read is
    // an invented audience. ARENA_BATTLE_PLAN §2 forbids fake viewers, gifts,
    // rankings and results in production outright.
    //
    // The page does not need it: with no active battle the template renders
    // "Crown holds the centre" and "0 watching" by itself, which is the truth.
    refreshPanels(data);
    refreshReadModel(data);
    refreshDeadline(data);
    refreshLiveStage(data);
    refreshCrownWindow(data);
    refreshBroadcastCopy(data);
  }

  // T21: the server-rendered pills exist before the first poll, so place them
  // on load too - otherwise the board sits flat for up to thirty seconds.
  if (global.document) {
    if (global.document.readyState === 'loading') {
      global.document.addEventListener('DOMContentLoaded', placeUpcomingPills, { once: true });
    } else {
      placeUpcomingPills();
    }
  }

  global.ArenaDeck = {
    refresh: refresh,
    centreKey: centreKey,
    formatRemaining: formatRemaining,
    hydrateFixtures: hydrateFixtures,
    placeUpcomingPills: placeUpcomingPills
  };
})(window);
