/**
 * CulinEire Chef Battles Arena
 * Renders a concentric octagonal SVG ring of chefs, grouped by rank.
 *
 * Layout (outer → inner):
 *   Ring 8 – 34 cells – Kitchen Porter
 *   Ring 7 – 30 cells – Prep Chef
 *   Ring 6 – 26 cells – Commis Chef
 *   Ring 5 – 22 cells – Chef de Partie
 *   Ring 4 – 18 cells – Sous Chef
 *   Ring 3 – 14 cells – Head Chef
 *   Ring 2 – 10 cells – Executive Chef
 *   Ring 1 –  6 cells – Culinary Master
 *   Centre –  1 cell  – active battle
 */

(function () {
  'use strict';

  var CX = 550, CY = 550;
  var GAP = 3;
  var PING_INTERVAL   = 60000;   // 60 s — heartbeat to update last_seen_at
  var POLL_INTERVAL   = 20000;   // 20 s — refresh arena state

  // ?demo in the URL turns on the presentation dev-panel and freezes the
  // 20s state poll so staged renders persist. Purely client-side, no writes.
  var DEMO_MODE = false;
  try { DEMO_MODE = new URLSearchParams(window.location.search).has('demo'); } catch (e) {}

  var RING_RADII = {
    centre : [0,   85],
    1      : [85,  145],
    2      : [145, 215],
    3      : [215, 295],
    4      : [295, 375],
    5      : [375, 445],
    6      : [445, 505],
    7      : [505, 560],
    8      : [560, 610],
    9      : [610, 655],
  };

  var RING_COUNTS = { 1: 6, 2: 10, 3: 14, 4: 18, 5: 22, 6: 26, 7: 30, 8: 34, 9: 40 };

  // Battle phases where the chef is shown in the VS centre cells, not in their ring.
  // Any phase in ACTIVE_STATUSES that is NOT pre-battle scheduling.
  var CENTRE_PHASES = {
    active: true, cooking: true, awaiting_submissions: true,
    presentation: true, revealed: true, voting: true,
    ingredient_penalty: true, disputed: true,
  };
  // Phases where the chef is in a facing pair (pre-combat staging); ring cell is also vacated.
  var FACING_PHASES = {
    scheduled: true, menu_locked: true,
  };

  var RING_RANK_KEY = {
    1: 'culinary_master',
    2: 'executive_chef',
    3: 'head_chef',
    4: 'sous_chef',
    5: 'chef_de_partie',
    6: 'commis_chef',
    7: 'prep_cook',
    8: 'kitchen_porter',
  };

  var RING_COLOURS = {
    chef       : { 8: '#e4ddd1', 7: '#d8d0c0', 6: '#ccc1aa', 5: '#bfb49a', 4: '#a89878', 3: '#8f7c5c', 2: '#73603f', 1: '#5a4a2e' },
    empty      : { 8: '#f4f1ec', 7: '#ede8df', 6: '#e4ddd1', 5: '#d8d0c0', 4: '#ccc1aa', 3: '#bfb49a', 2: '#a89878', 1: '#8f7c5c' },
    spectator  : '#2a5fb0',
    spectator_empty: '#c5d3e8',
  };

  /* ------------------------------------------------------------------ */
  /* Math helpers (octagonal geometry, ported from sponsors_puzzle.js)   */
  /* ------------------------------------------------------------------ */
  function octRadius(angle, R) {
    var sector = Math.PI / 4;
    var half   = sector / 2;
    var norm = ((angle % sector) + sector) % sector;
    return R * Math.cos(half) / Math.cos(norm - half);
  }

  function octPoint(cx, cy, angle, R) {
    var r = octRadius(angle, R);
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  }

  function ringSegmentPoints(cx, cy, innerR, outerR, startAngle, endAngle) {
    var STEPS = 12;
    var pts   = [];
    var i, angle, pt;

    for (i = 0; i <= STEPS; i++) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pt = octPoint(cx, cy, angle, outerR);
      pts.push(pt);
    }
    for (i = STEPS; i >= 0; i--) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pt = octPoint(cx, cy, angle, innerR);
      pts.push(pt);
    }
    return pts;
  }

  function pathFromPoints(pts) {
    if (!pts.length) { return ''; }
    var first = pts[0][0].toFixed(2) + ',' + pts[0][1].toFixed(2);
    var rest = [];
    for (var i = 1; i < pts.length; i++) {
      rest.push(pts[i][0].toFixed(2) + ',' + pts[i][1].toFixed(2));
    }
    return 'M ' + first + ' L ' + rest.join(' L ') + ' Z';
  }

  function ringSegmentPath(cx, cy, innerR, outerR, startAngle, endAngle) {
    return pathFromPoints(ringSegmentPoints(cx, cy, innerR, outerR, startAngle, endAngle));
  }

  function pointBounds(points) {
    var minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;
    for (var i = 0; i < points.length; i++) {
      minX = Math.min(minX, points[i][0]);
      minY = Math.min(minY, points[i][1]);
      maxX = Math.max(maxX, points[i][0]);
      maxY = Math.max(maxY, points[i][1]);
    }
    return { minX: minX, minY: minY, maxX: maxX, maxY: maxY,
      width: Math.max(1, maxX - minX), height: Math.max(1, maxY - minY) };
  }

  function octagonPoints(cx, cy, R) {
    var pts = [];
    for (var i = 0; i < 8; i++) {
      var angle = i * Math.PI / 4;
      pts.push((cx + R * Math.cos(angle)).toFixed(2) + ',' + (cy + R * Math.sin(angle)).toFixed(2));
    }
    return pts.join(' ');
  }

  function svgEl(tag, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) {
        el.setAttribute(k, attrs[k]);
      }
    }
    return el;
  }

  function segmentCentroid(innerR, outerR, startAngle, endAngle) {
    var midAngle = (startAngle + endAngle) / 2;
    var midR     = (innerR + outerR) / 2;
    var r = octRadius(midAngle, midR);
    return [CX + r * Math.cos(midAngle), CY + r * Math.sin(midAngle)];
  }

  /* ------------------------------------------------------------------ */
  /* Draw                                                                 */
  /* ------------------------------------------------------------------ */
  function clearGroup(id) {
    var g = document.getElementById(id);
    while (g && g.firstChild) { g.removeChild(g.firstChild); }
    return g;
  }

  function drawArena(data) {
    var group   = clearGroup('arena-cells');
    var centreG = clearGroup('arena-centre');
    var octPoly = document.getElementById('arena-oct-poly');
    if (!group || !centreG) { return; }

    octPoly.setAttribute('points', octagonPoints(CX, CY, RING_RADII[9][1] + 10));

    // Ring 9: spectators (outer ring, different colour scheme)
    var spectators = data.spectators || [];
    var s9count = RING_COUNTS[9];
    var s9inner = RING_RADII[9][0];
    var s9outer = RING_RADII[9][1];
    var s9sweep = (2 * Math.PI) / s9count;
    var s9offset = -Math.PI / 2 - s9sweep / 2;

    for (var si = 0; si < s9count; si++) {
      var s9start = s9offset + si * s9sweep + GAP / s9outer;
      var s9end   = s9offset + (si + 1) * s9sweep - GAP / s9outer;
      var s9path  = ringSegmentPath(CX, CY, s9inner + GAP, s9outer - GAP / 2, s9start, s9end);

      var spec = spectators[si] || null;
      var s9fill = spec ? RING_COLOURS.spectator : RING_COLOURS.spectator_empty;

      var s9class = 'arena-cell arena-cell--spectator arena-cell--ring-9' + (spec ? ' arena-cell--has-spectator' : '');
      var s9el = svgEl('path', {
        d: s9path, fill: s9fill,
        stroke: '#fff', 'stroke-width': '1.5',
        filter: 'url(#arena-cell-shadow)',
        cursor: spec ? 'pointer' : 'default',
        class: s9class,
      });

      attachSpectatorEvents(s9el, spec);
      group.appendChild(s9el);

      if (spec) {
        appendAvatarToCell(group, spec, s9inner, s9outer, s9start, s9end);
      } else {
        addEmptyLabel(group, s9inner, s9outer, s9start, s9end);
      }
    }

    var rings = [8, 7, 6, 5, 4, 3, 2, 1];
    for (var ri = 0; ri < rings.length; ri++) {
      var ring    = rings[ri];
      var rankKey = RING_RANK_KEY[ring];
      var chefs   = (data.rings && data.rings[rankKey]) || [];
      var count   = RING_COUNTS[ring];
      var innerR  = RING_RADII[ring][0];
      var outerR  = RING_RADII[ring][1];
      var sweep   = (2 * Math.PI) / count;
      var offset  = -Math.PI / 2 - sweep / 2;

      for (var pos = 0; pos < count; pos++) {
        var startAngle = offset + pos * sweep + GAP / outerR;
        var endAngle   = offset + (pos + 1) * sweep - GAP / outerR;
        var path = ringSegmentPath(CX, CY, innerR + GAP, outerR - GAP / 2, startAngle, endAngle);

        var chef   = chefs[pos] || null;
        // If the chef is in VS centre or a facing pair, their ring cell is vacated.
        if (chef && chef.battle_phase && (CENTRE_PHASES[chef.battle_phase] || FACING_PHASES[chef.battle_phase])) {
          chef = null;
        }
        var bucket = chef ? 'chef' : 'empty';
        var fill   = (RING_COLOURS[bucket] || RING_COLOURS.empty)[ring];

        var cellClass = 'arena-cell arena-cell--' + bucket + ' arena-cell--ring-' + ring;
        if (chef && chef.in_battle)  { cellClass += ' arena-cell--in-battle'; }
        if (chef && chef.is_online)  { cellClass += ' arena-cell--online'; }
        // Cutlery cursor only on chefs currently in an active battle — owner
        // scope 2026-07-01: the honing cursor signals a live fight, not every
        // enrolled chef sitting in the ring.
        if (chef && chef.in_battle) { cellClass += ' battle-cursor-target js-battle-cursor-target'; }

        var pathEl = svgEl('path', {
          d             : path,
          fill          : fill,
          stroke        : '#fff',
          'stroke-width': '1.5',
          filter        : 'url(#arena-cell-shadow)',
          cursor        : chef ? 'pointer' : 'default',
          class         : cellClass,
          'data-ring'   : ring,
          'data-pos'    : pos,
        });

        attachCellEvents(pathEl, chef);
        group.appendChild(pathEl);

        if (chef) {
          appendAvatarToCell(group, chef, innerR, outerR, startAngle, endAngle);
          if (chef.is_online) {
            appendOnlineDot(group, innerR, outerR, startAngle, endAngle);
          }
        } else {
          addEmptyLabel(group, innerR, outerR, startAngle, endAngle);
        }
      }
    }

    drawCentre(centreG, data.center || { type: 'empty' });
  }

  function addEmptyLabel(group, innerR, outerR, startAngle, endAngle) {
    var centroid = segmentCentroid(innerR + GAP, outerR - GAP / 2, startAngle, endAngle);
    var textEl = svgEl('text', {
      x: centroid[0].toFixed(1), y: centroid[1].toFixed(1),
      'text-anchor': 'middle', 'dominant-baseline': 'middle',
      fill: 'rgba(60,55,45,0.35)', 'font-family': 'Inter, sans-serif',
      'font-size': '9', 'pointer-events': 'none',
    });
    textEl.textContent = '+';
    group.appendChild(textEl);
  }

  function appendAvatarToCell(group, chef, innerR, outerR, startAngle, endAngle) {
    var points  = ringSegmentPoints(CX, CY, innerR + GAP, outerR - GAP / 2, startAngle, endAngle);
    var bounds  = pointBounds(points);
    var size    = Math.max(bounds.width, bounds.height);
    var cx      = (bounds.minX + bounds.maxX) / 2;
    var cy      = (bounds.minY + bounds.maxY) / 2;
    var svgDefs = document.querySelector('#arena-puzzle defs');

    if (svgDefs && chef.avatar_url) {
      var clipId  = 'ac-' + cx.toFixed(0) + '-' + cy.toFixed(0);
      var clip    = svgEl('clipPath', { id: clipId });
      clip.appendChild(svgEl('path', { d: pathFromPoints(points) }));
      svgDefs.appendChild(clip);

      var img = svgEl('image', {
        href: chef.avatar_url,
        x: (cx - size / 2).toFixed(1), y: (cy - size / 2).toFixed(1),
        width: size.toFixed(1), height: size.toFixed(1),
        preserveAspectRatio: 'xMidYMid slice',
        'pointer-events': 'none',
      });
      var clipped = svgEl('g', { 'clip-path': 'url(#' + clipId + ')' });
      clipped.appendChild(img);
      group.appendChild(clipped);
    }
  }

  function appendOnlineDot(group, innerR, outerR, startAngle, endAngle) {
    var midAngle  = (startAngle + endAngle) / 2;
    var outerEdge = outerR - GAP / 2;
    var r         = octRadius(midAngle, outerEdge);
    var dotX      = CX + r * Math.cos(midAngle);
    var dotY      = CY + r * Math.sin(midAngle);

    // White ring + green dot
    var ring = svgEl('circle', {
      cx: dotX.toFixed(1), cy: dotY.toFixed(1), r: '5.5',
      fill: '#fff', 'pointer-events': 'none',
    });
    var dot = svgEl('circle', {
      cx: dotX.toFixed(1), cy: dotY.toFixed(1), r: '4',
      fill: '#22c55e', 'pointer-events': 'none',
      class: 'arena-online-dot',
    });
    group.appendChild(ring);
    group.appendChild(dot);
  }

  function octagonPointPairs(cx, cy, R) {
    var pts = [];
    for (var i = 0; i < 8; i++) {
      var angle = i * Math.PI / 4;
      pts.push([cx + R * Math.cos(angle), cy + R * Math.sin(angle)]);
    }
    return pts;
  }

  // One combatant cell for the centre VS staging (Phase 1 of the battle
  // choreography): gold octagon + clipped avatar + first-name label.
  function drawBattleCell(g, cx, cy, R, chef, battleUrl) {
    var poly = svgEl('polygon', {
      points: octagonPoints(cx, cy, R),
      fill: '#c8942a', stroke: '#fff', 'stroke-width': '2',
      filter: 'url(#arena-cell-shadow)',
      cursor: battleUrl ? 'pointer' : 'default',
      class: 'arena-cell arena-center--active',
    });
    if (battleUrl) {
      poly.addEventListener('click', function () { window.location.href = battleUrl; });
    }
    g.appendChild(poly);

    var svgDefs = document.querySelector('#arena-puzzle defs');
    if (svgDefs && chef && chef.avatar_url) {
      // 'ac-' prefix so the existing clipPath cleanup in pollArenaState sweeps it
      var clipId = 'ac-c-' + cx.toFixed(0) + '-' + cy.toFixed(0);
      var clip = svgEl('clipPath', { id: clipId });
      clip.appendChild(svgEl('path', { d: pathFromPoints(octagonPointPairs(cx, cy, R)) }));
      svgDefs.appendChild(clip);

      var img = svgEl('image', {
        href: chef.avatar_url,
        x: (cx - R).toFixed(1), y: (cy - R).toFixed(1),
        width: (R * 2).toFixed(1), height: (R * 2).toFixed(1),
        preserveAspectRatio: 'xMidYMid slice', 'pointer-events': 'none',
      });
      var clipped = svgEl('g', { 'clip-path': 'url(#' + clipId + ')' });
      clipped.appendChild(img);
      g.appendChild(clipped);
    }

    if (chef && chef.name) {
      var lbl = svgEl('text', {
        x: cx, y: cy + R + 13, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: '#fff', 'font-family': 'Inter, sans-serif', 'font-size': '10', 'font-weight': '600',
        'pointer-events': 'none',
      });
      lbl.textContent = chef.name.split(' ')[0];
      g.appendChild(lbl);
    }
  }

  function drawCentre(g, center) {
    // Active battle: two combatant octagons facing each other with VS between.
    if (center.type === 'active_battle') {
      var CELL_R = 38;   // combatant cell radius
      var CELL_D = 50;   // horizontal offset of each cell from centre
      drawBattleCell(g, CX - CELL_D, CY, CELL_R, center.challenger, center.battle_url);
      drawBattleCell(g, CX + CELL_D, CY, CELL_R, center.opponent, center.battle_url);
      var vs = svgEl('text', {
        x: CX, y: CY, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: '#fff', 'font-family': 'Georgia, serif', 'font-size': '18', 'font-weight': 'bold',
        'pointer-events': 'none',
      });
      vs.textContent = 'VS';
      g.appendChild(vs);
      return;
    }

    // Crown holder or empty: single centre octagon.
    var R   = RING_RADII.centre[1] - GAP;
    var pts = octagonPoints(CX, CY, R);
    var isCrown = center.type === 'crown';

    var poly = svgEl('polygon', {
      points: pts,
      fill: isCrown ? '#c8942a' : '#6c6054',
      stroke: '#fff', 'stroke-width': '2',
      filter: 'url(#arena-cell-shadow)',
      cursor: isCrown ? 'pointer' : 'default',
      class: 'arena-cell arena-cell--centre' + (isCrown ? ' arena-center--active' : ''),
    });
    if (isCrown && center.profile_url) {
      poly.addEventListener('click', function () { window.location.href = center.profile_url; });
    }
    g.appendChild(poly);

    if (isCrown) {
      var crownIcon = svgEl('text', {
        x: CX, y: CY - 22, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        'font-size': '20', 'pointer-events': 'none',
      });
      crownIcon.textContent = '\u{1F451}';
      g.appendChild(crownIcon);

      var crownLbl = svgEl('text', {
        x: CX, y: CY, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: '#fff', 'font-family': 'Georgia, serif', 'font-size': '17', 'font-weight': 'bold',
        'pointer-events': 'none',
      });
      crownLbl.textContent = center.name || '?';
      g.appendChild(crownLbl);

      var crownLbl2 = svgEl('text', {
        x: CX, y: CY + 19, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: 'rgba(255,255,255,0.8)', 'font-family': 'Inter, sans-serif', 'font-size': '10',
        'pointer-events': 'none',
      });
      crownLbl2.textContent = 'CROWN HOLDER';
      g.appendChild(crownLbl2);
    } else {
      var text1 = svgEl('text', {
        x: CX, y: CY - 8, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: '#fff', 'font-family': 'Georgia, serif', 'font-size': '23', 'font-weight': 'bold',
        'pointer-events': 'none',
      });
      text1.textContent = 'Arena';

      var text2 = svgEl('text', {
        x: CX, y: CY + 15, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: 'rgba(255,255,255,0.7)', 'font-family': 'Georgia, serif', 'font-size': '10',
        'pointer-events': 'none',
      });
      text2.textContent = 'No battle in progress';

      g.appendChild(text1);
      g.appendChild(text2);
    }
  }

  /* ------------------------------------------------------------------ */
  /* Ripple animation                                                    */
  /* ------------------------------------------------------------------ */
  function fireCellRipple(e) {
    var svg = document.getElementById('arena-puzzle');
    if (!svg || !e) { return; }
    try {
      var pt = svg.createSVGPoint();
      pt.x = e.clientX;
      pt.y = e.clientY;
      var svgPt = pt.matrixTransform(svg.getScreenCTM().inverse());
      var circle = document.createElementNS('http://www.w3.org/2000/svg', 'circle');
      circle.setAttribute('cx', svgPt.x.toFixed(1));
      circle.setAttribute('cy', svgPt.y.toFixed(1));
      circle.setAttribute('r', '0');
      circle.setAttribute('fill', 'rgba(58,48,40,0.28)');
      circle.setAttribute('pointer-events', 'none');
      svg.appendChild(circle);

      var MAX_R = 110, DURATION = 420, start = null;
      function step(ts) {
        if (!start) { start = ts; }
        var progress = Math.min((ts - start) / DURATION, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        circle.setAttribute('r', (MAX_R * eased).toFixed(1));
        circle.setAttribute('fill-opacity', (0.28 * (1 - progress)).toFixed(3));
        if (progress < 1) { requestAnimationFrame(step); } else { circle.remove(); }
      }
      requestAnimationFrame(step);
    } catch (err) {}
  }

  /* ------------------------------------------------------------------ */
  /* Battle blast — celebrates the most recently completed battle for   */
  /* anyone watching the arena, not just its two participants.          */
  /* ------------------------------------------------------------------ */
  var _lastSeenResultId = null; // null = not yet initialised from the page's own data

  function fireBattleBlast(result) {
    var el = document.getElementById('battle-blast');
    if (!el || !result) { return; }

    var badge = document.getElementById('blast-badge');
    var winnerEl = document.getElementById('blast-winner');
    var scoreEl = document.getElementById('blast-score');
    if (badge) { badge.textContent = 'Battle Complete'; }
    if (winnerEl) { winnerEl.textContent = result.winner_name + ' Wins!'; }
    if (scoreEl) { scoreEl.textContent = result.result_reason || result.theme || ''; }

    el.hidden = false;
    // force layout so the entrance transition/animation actually plays
    // eslint-disable-next-line no-unused-expressions
    el.offsetWidth;
    el.classList.add('is-active');
  }

  function dismissBattleBlast() {
    var el = document.getElementById('battle-blast');
    if (!el) { return; }
    el.classList.remove('is-active');
    window.setTimeout(function () { el.hidden = true; }, 350);
  }

  function initBattleBlast(initialResult) {
    _lastSeenResultId = initialResult ? initialResult.battle_id : null;
    var dismissBtn = document.getElementById('blast-dismiss');
    if (dismissBtn) { dismissBtn.addEventListener('click', dismissBattleBlast); }
  }

  function maybeCelebrate(latestResult) {
    if (!latestResult) { return; }
    if (_lastSeenResultId !== null && latestResult.battle_id !== _lastSeenResultId) {
      fireBattleBlast(latestResult);
    }
    _lastSeenResultId = latestResult.battle_id;
  }

  /* ------------------------------------------------------------------ */
  /* Tooltip                                                             */
  /* ------------------------------------------------------------------ */
  var _tooltipEl = null;

  function getTooltip() {
    if (!_tooltipEl) { _tooltipEl = document.getElementById('arena-tooltip'); }
    return _tooltipEl;
  }

  function showTooltip(chef, anchorEl) {
    var tip = getTooltip();
    if (!tip) { return; }

    tip.setAttribute('data-rank', chef.rank || '');
    tip.querySelector('.arena-tooltip__avatar').src = chef.avatar_url || '';
    tip.querySelector('.arena-tooltip__avatar').alt = chef.name || '';
    tip.querySelector('.arena-tooltip__name').textContent = chef.name || '';
    tip.querySelector('.arena-tooltip__rank').textContent = chef.rank_label || '';
    var ratingEl = tip.querySelector('.arena-tooltip__rating');
    ratingEl.textContent = chef.rating ? 'Rating: ' + chef.rating : '';
    ratingEl.hidden = !chef.rating;
    tip.querySelector('.arena-tooltip__link').href = '/chef-battle/profile/' + chef.slug + '/';

    var battleBadge = tip.querySelector('.arena-tooltip__badge--battle');
    var onlineBadge = tip.querySelector('.arena-tooltip__badge--online');
    if (battleBadge) { battleBadge.hidden = !chef.in_battle; }
    if (onlineBadge) { onlineBadge.hidden = !chef.is_online; }

    // W / L / Streak stats (hidden for spectators who are not enrolled chefs)
    var statsEl = tip.querySelector('.arena-tooltip__stats');
    var wEl = tip.querySelector('.js-chef-wins');
    var lEl = tip.querySelector('.js-chef-losses');
    var sEl = tip.querySelector('.js-chef-streak');
    if (statsEl) { statsEl.hidden = !!chef.is_spectator; }
    if (wEl) { wEl.textContent = chef.wins || 0; }
    if (lEl) { lEl.textContent = chef.losses || 0; }
    if (sEl) { sEl.textContent = chef.win_streak || 0; }

    // Approximate artifact potential (hidden for spectators and when both are 0)
    var potEl = tip.querySelector('.js-chef-potential');
    if (potEl) {
      var atk = chef.atk || 0;
      var def = chef['def'] || 0;
      if (!chef.is_spectator && (atk > 0 || def > 0)) {
        tip.querySelector('.js-chef-atk').textContent = atk;
        tip.querySelector('.js-chef-def').textContent = def;
        potEl.hidden = false;
      } else {
        potEl.hidden = true;
      }
    }

    // Challenge button — only for enrolled viewers targeting enrolled chefs, not self, not in battle
    var challengeBtn = tip.querySelector('.js-challenge-btn');
    if (challengeBtn) {
      var viewer = window.ARENA_VIEWER || {};
      var canChallenge = viewer.enrolled && viewer.slug && viewer.slug !== chef.slug && !chef.in_battle && !chef.is_spectator;
      if (canChallenge) {
        challengeBtn.href = '/chef-battle/challenge/new/?opponent=' + chef.slug;
        challengeBtn.hidden = false;
      } else {
        challengeBtn.hidden = true;
      }
    }

    tip.hidden = false;

    // Position below the SVG cell using its bounding rect
    var svgEl = document.getElementById('arena-puzzle');
    var cellRect = anchorEl.getBoundingClientRect();
    var containerRect = svgEl ? svgEl.getBoundingClientRect() : cellRect;
    var scrollY = window.scrollY || window.pageYOffset;
    var scrollX = window.scrollX || window.pageXOffset;

    var tipLeft = cellRect.left + scrollX + (cellRect.width / 2) - (tip.offsetWidth / 2);
    var tipTop  = cellRect.bottom + scrollY + 8;

    // Keep within viewport horizontally
    var margin = 8;
    var maxLeft = scrollX + window.innerWidth - tip.offsetWidth - margin;
    tipLeft = Math.max(scrollX + margin, Math.min(tipLeft, maxLeft));

    tip.style.left = tipLeft + 'px';
    tip.style.top  = tipTop + 'px';
  }

  function hideTooltip() {
    var tip = getTooltip();
    if (tip) { tip.hidden = true; }
  }

  function attachCellEvents(el, chef) {
    if (!chef) { return; }
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      fireCellRipple(e);
      showTooltip(chef, el);
    });
    el.addEventListener('mouseenter', function () { el.setAttribute('opacity', '0.82'); });
    el.addEventListener('mouseleave', function () { el.removeAttribute('opacity'); });
  }

  function attachSpectatorEvents(el, spec) {
    if (!spec) { return; }
    var spectatorChef = {
      name: spec.name,
      slug: spec.slug,
      avatar_url: spec.avatar_url,
      rank_label: 'Spectator',
      rating: spec.tokens + ' tokens',
      in_battle: false,
      is_online: false,
      is_spectator: true,
    };
    el.addEventListener('click', function (e) {
      e.stopPropagation();
      fireCellRipple(e);
      showTooltip(spectatorChef, el);
    });
    el.addEventListener('mouseenter', function () { el.setAttribute('opacity', '0.82'); });
    el.addEventListener('mouseleave', function () { el.removeAttribute('opacity'); });
  }

  /* ------------------------------------------------------------------ */
  /* Polling: ping (heartbeat) + state refresh                           */
  /* ------------------------------------------------------------------ */
  function getCsrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  function pingArena() {
    fetch('/chef-battle/arena/ping/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrfToken() },
    }).catch(function () {});
  }

  function pollArenaState() {
    fetch('/chef-battle/arena/state/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': getCsrfToken() },
    })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (data) {
          // Clean up dynamic clipPaths from previous render before redraw
          var defs = document.querySelector('#arena-puzzle defs');
          if (defs) {
            var oldClips = defs.querySelectorAll('clipPath[id^="ac-"]');
            for (var i = 0; i < oldClips.length; i++) { oldClips[i].remove(); }
          }
          drawArena(data);
          maybeCelebrate(data.latest_result);
        }
      })
      .catch(function () {});
  }

  /* ------------------------------------------------------------------ */
  /* Demo panel — presentation stepper for every arena effect (?demo)    */
  /* ------------------------------------------------------------------ */
  function collectChefs(data) {
    var out = [];
    var rings = (data && data.rings) || {};
    for (var k in rings) {
      if (Object.prototype.hasOwnProperty.call(rings, k)) {
        for (var i = 0; i < rings[k].length; i++) { if (rings[k][i]) { out.push(rings[k][i]); } }
      }
    }
    return out;
  }

  function buildDemoPanel(data) {
    var chefs = collectChefs(data);
    var a = chefs[0] || { name: 'Chef A', avatar_url: '', slug: '' };
    var b = chefs[1] || { name: 'Chef B', avatar_url: '', slug: '' };
    var centreG = document.getElementById('arena-centre');

    function setCentre(center) { clearGroup('arena-centre'); drawCentre(centreG, center); }

    var stages = [
      ['Empty (Arena)', function () { setCentre({ type: 'empty' }); }],
      ['Crown holder', function () {
        setCentre({ type: 'crown', name: a.name, avatar_url: a.avatar_url,
          profile_url: a.slug ? '/chef-battle/profile/' + a.slug + '/' : '#' });
      }],
      ['Battle: VS centre', function () {
        setCentre({ type: 'active_battle', battle_url: '#',
          challenger: { name: a.name, avatar_url: a.avatar_url },
          opponent: { name: b.name, avatar_url: b.avatar_url } });
      }],
      ['Cell ripple', function () {
        var svg = document.getElementById('arena-puzzle');
        var r = svg.getBoundingClientRect();
        fireCellRipple({ clientX: r.left + r.width / 2, clientY: r.top + r.height / 2 });
      }],
      ['Winner Blast', function () {
        fireBattleBlast({ battle_id: -1, winner_name: a.name,
          result_reason: 'Public vote: 5-3', theme: 'Demo Battle' });
      }],
    ];

    var panel = document.createElement('div');
    panel.className = 'arena-demo-panel';
    var h = document.createElement('p');
    h.className = 'arena-demo-panel__title';
    h.textContent = 'Duel stages · demo';
    panel.appendChild(h);
    stages.forEach(function (s) {
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'arena-demo-panel__btn';
      btn.textContent = s[0];
      btn.addEventListener('click', s[1]);
      panel.appendChild(btn);
    });
    var note = document.createElement('p');
    note.className = 'arena-demo-panel__note';
    note.textContent = 'Client-side preview. Live poll paused.';
    panel.appendChild(note);
    document.body.appendChild(panel);
  }

  /* ------------------------------------------------------------------ */
  /* Init                                                                 */
  /* ------------------------------------------------------------------ */
  document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('arena-data-json');
    var data = { rings: {}, center: { type: 'empty' } };
    if (el) {
      try { data = JSON.parse(el.textContent); } catch (e) {}
    }
    drawArena(data);
    initBattleBlast(data.latest_result);

    // Dismiss tooltip on outside click
    document.addEventListener('click', function (e) {
      var tip = getTooltip();
      if (tip && !tip.hidden && !tip.contains(e.target)) { hideTooltip(); }
    });
    var closeBtn = document.querySelector('.arena-tooltip__close');
    if (closeBtn) { closeBtn.addEventListener('click', hideTooltip); }

    if (DEMO_MODE) {
      buildDemoPanel(data);
      return;   // no heartbeat, no poll — keep staged demo renders frozen
    }

    // Start heartbeat immediately then repeat
    pingArena();
    setInterval(pingArena, PING_INTERVAL);

    // State polling (refresh SVG every 20s)
    setInterval(pollArenaState, POLL_INTERVAL);
  });

})();
