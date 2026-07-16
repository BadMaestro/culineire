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
  var POLL_INTERVAL   = 10000;   // 10 s — refresh arena state (and presence)

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
    10     : [660, 715],
    11     : [720, 780],
    12     : [785, 850],
  };

  var RING_COUNTS = { 1: 6, 2: 10, 3: 14, 4: 18, 5: 22, 6: 26, 7: 30, 8: 34, 9: 40, 10: 48, 11: 56, 12: 64 };

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
  /* Spectator placement â€” data-driven polar slot generator             */
  /* ------------------------------------------------------------------ */
  // Receives the real spectator records and ring capacities, then returns
  // every available seat in angular order. No identity or count is invented:
  // empty seats simply carry spectator:null. Keeping this pure makes adding
  // future presence sources or different viewport rings safe and testable.
  function buildSpectatorPolarSlots(spectators, ringNumbers) {
    var slots = [];
    var sourceIndex = 0;
    for (var r = 0; r < ringNumbers.length; r++) {
      var ring = ringNumbers[r];
      var count = RING_COUNTS[ring];
      var outerR = RING_RADII[ring][1];
      var sweep = (2 * Math.PI) / count;
      var offset = -Math.PI / 2 - sweep / 2;
      for (var index = 0; index < count; index++) {
        slots.push({
          ring: ring,
          index: index,
          startAngle: offset + index * sweep + GAP / outerR,
          endAngle: offset + (index + 1) * sweep - GAP / outerR,
          spectator: spectators[sourceIndex++] || null,
        });
      }
    }
    return slots;
  }

  /* ------------------------------------------------------------------ */
  /* Teleport tracking — remember which slugs were in centre last render */
  /* ------------------------------------------------------------------ */
  var _prevCentreSlugs = {};   // {slug: true} for chefs shown in centre/facing last draw

  function _slugsFromCenter(center) {
    var out = {};
    if (!center) return out;
    if (center.challenger && center.challenger.slug) out[center.challenger.slug] = true;
    if (center.opponent   && center.opponent.slug)   out[center.opponent.slug]   = true;
    return out;
  }

  // Append a one-shot gold flash ring at (cx, cy) to group g.
  function _flashRing(g, cx, cy, R) {
    var ring = svgEl('circle', {
      cx: cx.toFixed(1), cy: cy.toFixed(1), r: R.toFixed(1),
      fill: 'none', stroke: '#f8d28a', 'stroke-width': '3',
      opacity: '0', 'pointer-events': 'none',
      class: 'arena-teleport-flash',
    });
    g.appendChild(ring);
  }

  /* ------------------------------------------------------------------ */
  /* Draw                                                                 */
  /* ------------------------------------------------------------------ */
  function clearGroup(id) {
    var g = document.getElementById(id);
    while (g && g.firstChild) { g.removeChild(g.firstChild); }
    return g;
  }



  /* Corner arc rings — extend spectator seating into the 4 diagonal corners */
  function drawCornerRings(group) {
    var BASE_R    = RING_RADII[12][1];  // 850 — just outside outermost ring
    var DEPTH     = 65;                 // radial depth per corner ring, matching ring 12
    var NUM_RINGS = 4;                  // rings of corner seating
    var NUM_CELLS = 6;                  // arc segments per corner per ring

    // Corner centres at 45°, 135°, 225°, 315° in SVG coords (y-down)
    var corners = [Math.PI / 4, 3 * Math.PI / 4, 5 * Math.PI / 4, 7 * Math.PI / 4];
    var SPAN = Math.PI / 3.2;          // ~56° arc span per corner

    for (var ri = 0; ri < NUM_RINGS; ri++) {
      var innerR = BASE_R + ri * DEPTH;
      var outerR = innerR + DEPTH;
      var sweep  = SPAN / NUM_CELLS;

      for (var ci = 0; ci < corners.length; ci++) {
        var base = corners[ci] - SPAN / 2;
        for (var si = 0; si < NUM_CELLS; si++) {
          var startA = base + si * sweep + GAP / outerR;
          var endA   = base + (si + 1) * sweep - GAP / outerR;
          var path   = ringSegmentPath(CX, CY, innerR + GAP, outerR - GAP / 2, startA, endA);
          group.appendChild(svgEl('path', {
            d: path,
            fill: RING_COLOURS.spectator_empty,
            stroke: '#fff', 'stroke-width': '1.5',
            filter: 'url(#arena-cell-shadow)',
            'pointer-events': 'none',
            class: 'arena-cell arena-cell--spectator arena-cell--corner',
          }));
        }
      }
    }
  }

  function drawArena(data) {
    // Snapshot which slugs were in centre before this redraw (for teleport detection).
    var nextCentreSlugs = _slugsFromCenter(data.center);

    var group   = clearGroup('arena-cells');
    var centreG = clearGroup('arena-centre');
    var octPoly = document.getElementById('arena-oct-poly');
    if (!group || !centreG) { return; }

    octPoly.setAttribute('points', octagonPoints(CX, CY, RING_RADII[12][1] + 10));
    drawCornerRings(group);

    // Rings 9–12: spectator seats. Real spectators are distributed in polar
    // order across the available rings instead of being silently capped at
    // ring 9. The remaining slots retain the neutral empty-seat appearance.
    var spectators = data.spectators || [];
    var spectatorSlots = buildSpectatorPolarSlots(spectators, [9, 10, 11, 12]);
    for (var ss = 0; ss < spectatorSlots.length; ss++) {
      var slot = spectatorSlots[ss];
      var slotInner = RING_RADII[slot.ring][0];
      var slotOuter = RING_RADII[slot.ring][1];
      var slotPath = ringSegmentPath(CX, CY, slotInner + GAP, slotOuter - GAP / 2, slot.startAngle, slot.endAngle);
      var slotClass = 'arena-cell arena-cell--spectator arena-cell--ring-' + slot.ring + (slot.spectator ? ' arena-cell--has-spectator' : '');
      var slotEl = svgEl('path', {
        d: slotPath,
        fill: slot.spectator ? RING_COLOURS.spectator : RING_COLOURS.spectator_empty,
        stroke: '#fff', 'stroke-width': '1.5',
        filter: 'url(#arena-cell-shadow)',
        cursor: slot.spectator ? 'pointer' : 'default',
        class: slotClass,
      });
      attachSpectatorEvents(slotEl, slot.spectator);
      group.appendChild(slotEl);
      if (slot.spectator) {
        appendAvatarToCell(group, slot.spectator, slotInner, slotOuter, slot.startAngle, slot.endAngle);
      } else {
        addEmptyLabel(group, slotInner, slotOuter, slot.startAngle, slot.endAngle);
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

    // Update tracking for the next render cycle.
    _prevCentreSlugs = nextCentreSlugs;
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
  // isNew=true triggers a teleport-in flash ring animation.
  function drawBattleCell(g, cx, cy, R, chef, battleUrl, popupUrl, isNew) {
    var cellClass = 'arena-cell arena-center--active';
    if (isNew) cellClass += ' arena-cell--teleport-in';
    var poly = svgEl('polygon', {
      points: octagonPoints(cx, cy, R),
      fill: '#c8942a', stroke: '#fff', 'stroke-width': '2',
      filter: 'url(#arena-cell-shadow)',
      cursor: (battleUrl || popupUrl) ? 'pointer' : 'default',
      class: cellClass,
    });
    if (isNew) _flashRing(g, cx, cy, R + 12);
    if (popupUrl || battleUrl) {
      poly.addEventListener('click', function () {
        if (popupUrl) { openBattlePopup(popupUrl, battleUrl); }
        else { window.location.href = battleUrl; }
      });
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

  // Facing pair: SCHEDULED / MENU_LOCKED — chefs approach from a deterministic angle.
  function drawFacingPair(g, center) {
    var theta = ((center.battle_id || 0) % 8) * (Math.PI / 4);
    var DIST = 48;
    var R = 28;
    var cx1 = CX + DIST * Math.cos(theta);
    var cy1 = CY + DIST * Math.sin(theta);
    var cx2 = CX - DIST * Math.cos(theta);
    var cy2 = CY - DIST * Math.sin(theta);

    var chNew = center.challenger && !_prevCentreSlugs[center.challenger.slug];
    var opNew = center.opponent   && !_prevCentreSlugs[center.opponent.slug];
    drawBattleCell(g, cx1, cy1, R, center.challenger, center.battle_url, center.popup_url, chNew);
    drawBattleCell(g, cx2, cy2, R, center.opponent,   center.battle_url, center.popup_url, opNew);

    var swords = svgEl('text', {
      x: CX, y: CY, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
      fill: '#c8942a', 'font-size': '14', 'pointer-events': 'none', opacity: '0.75',
    });
    swords.textContent = '⚔';
    g.appendChild(swords);
  }

  function drawCentre(g, center) {
    // Facing pair: SCHEDULED / MENU_LOCKED — pre-combat staging.
    if (center.type === 'facing_pair') {
      drawFacingPair(g, center);
      return;
    }

    // Active battle: two combatant octagons facing each other with VS between.
    if (center.type === 'active_battle') {
      var CELL_R = 38;   // combatant cell radius
      var CELL_D = 50;   // horizontal offset of each cell from centre
      var chNew2 = center.challenger && !_prevCentreSlugs[center.challenger.slug];
      var opNew2 = center.opponent   && !_prevCentreSlugs[center.opponent.slug];
      drawBattleCell(g, CX - CELL_D, CY, CELL_R, center.challenger, center.battle_url, center.popup_url, chNew2);
      drawBattleCell(g, CX + CELL_D, CY, CELL_R, center.opponent, center.battle_url, center.popup_url, opNew2);
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

  function refreshCrownLadder(ladder) {
    var container = document.getElementById('arena-crown-ladder');
    if (!container || !Array.isArray(ladder)) { return; }
    clearPanel(container);
    if (!ladder.length) {
      appendPanelEmpty(container, 'No crowns have been awarded today.');
      return;
    }
    for (var i = 0; i < ladder.length; i++) {
      var chef = ladder[i] || {};
      var item = document.createElement('li');
      var position = document.createElement('span');
      var link = document.createElement('a');
      var crowns = document.createElement('em');
      position.textContent = String(i + 1);
      link.href = profileHref(container, chef.slug);
      link.textContent = chef.name || 'Chef';
      crowns.textContent = String(chef.crowns || 0) + ' crown' + (Number(chef.crowns) === 1 ? '' : 's');
      item.appendChild(position);
      item.appendChild(link);
      item.appendChild(crowns);
      container.appendChild(item);
    }
  }

  function refreshRecentGifts(gifts) {
    var container = document.getElementById('arena-recent-gifts');
    if (!container || !Array.isArray(gifts)) { return; }
    clearPanel(container);
    if (!gifts.length) {
      appendPanelEmpty(container, 'No battle gifts have been delivered yet.');
      return;
    }
    for (var i = 0; i < gifts.length; i++) {
      var gift = gifts[i] || {};
      var item = document.createElement('li');
      var icon = svgEl('svg', { 'class': 'arena-ico', 'aria-hidden': 'true' });
      var use = svgEl('use', { href: '#ad-gift' });
      var copy = document.createElement('span');
      var recipient = document.createElement('a');
      var artifact = document.createElement('b');
      var tokens = document.createElement('em');
      icon.appendChild(use);
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
    }
  }

  function refreshArenaPanels(data) {
    if (!data) { return; }
    if (Object.prototype.hasOwnProperty.call(data, 'crown_streak')) {
      var streak = document.getElementById('arena-crown-streak');
      if (streak) { streak.textContent = String(data.crown_streak || 0); }
    }
    if (Object.prototype.hasOwnProperty.call(data, 'crown_ladder')) { refreshCrownLadder(data.crown_ladder); }
    if (Object.prototype.hasOwnProperty.call(data, 'recent_gifts')) { refreshRecentGifts(data.recent_gifts); }
  }

  function metricText(value) {
    return value === null || typeof value === 'undefined' ? '—' : String(value);
  }

  function formatArenaRemaining(seconds) {
    var total = Math.max(0, Number(seconds) || 0);
    var days = Math.floor(total / 86400);
    var hours = Math.floor((total % 86400) / 3600);
    var minutes = Math.floor((total % 3600) / 60);
    var secs = total % 60;
    var clock = [hours, minutes, secs].map(function (value) {
      return String(value).padStart(2, '0');
    }).join(':');
    return (days ? String(days) + 'd ' : '') + clock;
  }

  function refreshArenaDeadline(data) {
    var panel = document.getElementById('arena-phase-deadline');
    if (!panel) { return; }
    var deadline = data && data.deadline;
    var value = panel.querySelector('strong');
    if (!deadline || typeof deadline.seconds_remaining === 'undefined') {
      panel.classList.add('is-empty');
      panel.setAttribute('data-deadline-iso', '');
      if (value) { value.textContent = 'No active deadline'; }
      return;
    }
    panel.classList.remove('is-empty');
    panel.setAttribute('data-deadline-iso', deadline.deadline_iso || '');
    if (value) { value.textContent = formatArenaRemaining(deadline.seconds_remaining) + ' remaining'; }
  }

  function refreshArenaReadModel(data) {
    if (!data) { return; }
    var metrics = data.arena_metrics || data.metrics;
    if (metrics) {
      var viewers = document.getElementById('arena-metric-viewers');
      var votes = document.getElementById('arena-metric-votes');
      var gifts = document.getElementById('arena-metric-gifts');
      if (viewers) { viewers.textContent = metricText(metrics.active_viewers); }
      if (votes) { votes.textContent = metricText(metrics.public_votes); }
      if (gifts) { gifts.textContent = metricText(metrics.battle_gifts); }
    }
    var phase = data.arena_phase || data.phase;
    var rail = document.getElementById('arena-phase-rail');
    var phaseName = document.getElementById('arena-current-phase');
    var phaseCopy = document.getElementById('arena-current-phase-copy');
    if (!rail) { return; }
    var steps = rail.querySelectorAll('[data-phase-step]');
    if (!phase || !phase.step) {
      for (var clearIndex = 0; clearIndex < steps.length; clearIndex++) {
        steps[clearIndex].classList.remove('is-active');
      }
      rail.setAttribute('data-phase-key', '');
      if (phaseName) { phaseName.textContent = 'Open floor'; }
      if (phaseCopy) { phaseCopy.textContent = 'Choose a chef on the floor to inspect their profile or issue a challenge.'; }
      return;
    }
    for (var i = 0; i < steps.length; i++) {
      steps[i].classList.toggle('is-active', Number(steps[i].getAttribute('data-phase-step')) === Number(phase.step));
    }
    rail.setAttribute('data-phase-key', phase.key || '');
    if (phaseName) { phaseName.textContent = phase.label || 'Battle in progress'; }
    if (phaseCopy) { phaseCopy.textContent = 'The centre tile opens the live battle room, chat and public actions.'; }
  }

  function arenaCentreKey(center) {
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
    card.className = 'arena-live-chef' + (modifier ? ' ' + modifier : '');
    image.src = chef.avatar_url || '';
    image.alt = chef.name || 'Chef';
    image.width = 72;
    image.height = 72;
    role.textContent = label;
    name.textContent = chef.name || 'Chef';
    copy.appendChild(role);
    copy.appendChild(name);
    card.appendChild(image);
    card.appendChild(copy);
    stage.appendChild(card);
  }

  function appendStageCentre(stage, options) {
    var link = document.createElement('a');
    var label = document.createElement('span');
    var title = document.createElement('b');
    var detail = document.createElement('em');
    link.className = 'arena-live-centre' + (options.className ? ' ' + options.className : '');
    link.href = options.href || '#arena-puzzle';
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

  function formatArenaDateTime(value) {
    var date = value ? new Date(value) : null;
    if (!date || Number.isNaN(date.getTime())) { return ''; }
    return date.toLocaleString(undefined, {
      day: 'numeric', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit'
    });
  }

  function refreshArenaCrownWindow(data) {
    var center = data && data.center;
    if (!center || center.type !== 'crown') { return; }
    var stage = document.getElementById('arena-live-stage');
    var note = stage && stage.querySelector('.arena-live-awaiting');
    if (!note) { return; }
    var crownUntil = formatArenaDateTime(center.crown_until);
    note.textContent = crownUntil ? 'Crown held until ' + crownUntil + '.' : 'The centre awaits the next challenge.';
  }

  function refreshArenaLiveStage(data) {
    var stage = document.getElementById('arena-live-stage');
    var center = data && data.center;
    if (!stage || !center) { return; }
    var key = arenaCentreKey(center);
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
        detail: center.theme || 'Open battle room',
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
        detail: 'View profile',
      });
      var crownUntil = formatArenaDateTime(center.crown_until);
      appendStageNote(stage, crownUntil ? 'Crown held until ' + crownUntil + '.' : 'The centre awaits the next challenge.');
      return;
    }
    appendStageNote(stage, 'No live battle is holding the centre.');
    appendStageCentre(stage, {
      href: '/chef-battle/rankings/',
      className: 'arena-live-centre--quiet',
      ariaLabel: 'Explore Arena ranks',
      label: 'Arena centre',
      title: 'Open',
      detail: 'Explore the ranks',
    });
    appendStageNote(stage, 'Choose a chef below to start a challenge.');
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
          refreshArenaPanels(data);
          refreshArenaReadModel(data);
          refreshArenaDeadline(data);
          refreshArenaLiveStage(data);
          refreshArenaCrownWindow(data);
          maybeCelebrate(data.latest_result);
        }
      })
      .catch(function () {});
  }

  /* ------------------------------------------------------------------ */
  /* Battle Room popup (Stage C)                                         */
  /* ------------------------------------------------------------------ */
  var _popupChatInterval = null;

  function openBattlePopup(popupUrl, battleUrl) {
    var popup = document.getElementById('arena-battle-popup');
    var inner = document.getElementById('arena-popup-inner');
    if (!popup || !inner) {
      if (battleUrl) { window.location.href = battleUrl; }
      return;
    }
    inner.innerHTML = '<p class="arena-popup__loading">Loading battle…</p>';
    popup.hidden = false;
    document.body.style.overflow = 'hidden';

    fetch(popupUrl, { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.text() : null; })
      .then(function (html) {
        if (!html) {
          inner.innerHTML = '<p class="arena-popup__loading">No active battle right now.</p>';
          return;
        }
        inner.innerHTML = html;
        _initPopupChat(inner);
      })
      .catch(function () {
        inner.innerHTML = '<p class="arena-popup__loading">Could not load battle. <a href="' + (battleUrl || '#') + '">Open full room</a></p>';
      });
  }

  function closeBattlePopup() {
    var popup = document.getElementById('arena-battle-popup');
    if (popup) { popup.hidden = true; }
    document.body.style.overflow = '';
    if (_popupChatInterval) {
      clearInterval(_popupChatInterval);
      _popupChatInterval = null;
    }
  }

  function _initPopupChat(container) {
    var form = container.querySelector('#abp-chat-form');
    var msgBox = container.querySelector('#abp-chat-messages');
    if (!form || !msgBox) { return; }

    var pollUrl = form.getAttribute('data-poll-url');
    var sendUrl = form.getAttribute('data-url');
    var lastId = 0;
    var existing = msgBox.querySelectorAll('[data-id]');
    for (var i = 0; i < existing.length; i++) {
      var id = parseInt(existing[i].getAttribute('data-id'), 10);
      if (id > lastId) { lastId = id; }
    }
    msgBox.scrollTop = msgBox.scrollHeight;

    function pollChat() {
      if (!pollUrl) { return; }
      fetch(pollUrl + '?since=' + lastId, { credentials: 'same-origin' })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data || !data.messages || !data.messages.length) { return; }
          var empty = msgBox.querySelector('.abp__chat-empty');
          if (empty) { empty.remove(); }
          for (var j = 0; j < data.messages.length; j++) {
            var m = data.messages[j];
            var div = document.createElement('div');
            div.className = 'abp__chat-msg';
            div.setAttribute('data-id', m.id);
            div.innerHTML = '<b class="abp__chat-who">' + _escHtml(m.display_name) + '</b> '
              + '<span class="abp__chat-body">' + _escHtml(m.body) + '</span>'
              + '<span class="abp__chat-time">' + _escHtml(m.created_at) + '</span>';
            msgBox.appendChild(div);
            if (m.id > lastId) { lastId = m.id; }
          }
          msgBox.scrollTop = msgBox.scrollHeight;
        })
        .catch(function () {});
    }

    pollChat();
    _popupChatInterval = setInterval(pollChat, 10000);

    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var input = form.querySelector('input[name="body"]');
      var body = input ? input.value.trim() : '';
      if (!body) { return; }
      var formData = new FormData(form);
      fetch(sendUrl, {
        method: 'POST',
        body: formData,
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': getCsrfToken() },
      }).then(function () {
        if (input) { input.value = ''; }
        setTimeout(pollChat, 400);
      }).catch(function () {});
    });
  }

  function _escHtml(s) {
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
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
      ['Facing pair (pre-battle)', function () {
        setCentre({ type: 'facing_pair', battle_id: 3, battle_url: '#',
          challenger: { name: a.name, avatar_url: a.avatar_url },
          opponent: { name: b.name, avatar_url: b.avatar_url } });
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
    refreshArenaPanels(data);
    refreshArenaReadModel(data);
    refreshArenaDeadline(data);
    refreshArenaCrownWindow(data);
    initBattleBlast(data.latest_result);

    // Dismiss tooltip on outside click
    document.addEventListener('click', function (e) {
      var tip = getTooltip();
      if (tip && !tip.hidden && !tip.contains(e.target)) { hideTooltip(); }
    });
    var closeBtn = document.querySelector('.arena-tooltip__close');
    if (closeBtn) { closeBtn.addEventListener('click', hideTooltip); }

    // Battle Room popup close
    var popupCloseBtn = document.getElementById('arena-popup-close');
    var popupBackdrop = document.getElementById('arena-popup-backdrop');
    if (popupCloseBtn) { popupCloseBtn.addEventListener('click', closeBattlePopup); }
    if (popupBackdrop) { popupBackdrop.addEventListener('click', closeBattlePopup); }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') { closeBattlePopup(); }
    });

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
