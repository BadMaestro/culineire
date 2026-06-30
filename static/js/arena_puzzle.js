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
  };

  var RING_COUNTS = { 1: 6, 2: 10, 3: 14, 4: 18, 5: 22, 6: 26, 7: 30, 8: 34 };

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
    chef  : { 8: '#e4ddd1', 7: '#d8d0c0', 6: '#ccc1aa', 5: '#bfb49a', 4: '#a89878', 3: '#8f7c5c', 2: '#73603f', 1: '#5a4a2e' },
    empty : { 8: '#f4f1ec', 7: '#ede8df', 6: '#e4ddd1', 5: '#d8d0c0', 4: '#ccc1aa', 3: '#bfb49a', 2: '#a89878', 1: '#8f7c5c' },
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
  function drawArena(data) {
    var group   = document.getElementById('arena-cells');
    var centreG = document.getElementById('arena-centre');
    var octPoly = document.getElementById('arena-oct-poly');

    octPoly.setAttribute('points', octagonPoints(CX, CY, RING_RADII[8][1] + 10));

    var rings = [8, 7, 6, 5, 4, 3, 2, 1];
    for (var ri = 0; ri < rings.length; ri++) {
      var ring   = rings[ri];
      var rankKey = RING_RANK_KEY[ring];
      var chefs  = (data.rings && data.rings[rankKey]) || [];
      var count  = RING_COUNTS[ring];
      var innerR = RING_RADII[ring][0];
      var outerR = RING_RADII[ring][1];
      var sweep  = (2 * Math.PI) / count;
      var offset = -Math.PI / 2 - sweep / 2;

      for (var pos = 0; pos < count; pos++) {
        var startAngle = offset + pos * sweep + GAP / outerR;
        var endAngle   = offset + (pos + 1) * sweep - GAP / outerR;
        var path = ringSegmentPath(CX, CY, innerR + GAP, outerR - GAP / 2, startAngle, endAngle);

        var chef   = chefs[pos] || null;
        var bucket = chef ? 'chef' : 'empty';
        var fill   = (RING_COLOURS[bucket] || RING_COLOURS.empty)[ring];

        var cellClass = 'arena-cell arena-cell--' + bucket + ' arena-cell--ring-' + ring;
        if (chef && chef.in_battle) { cellClass += ' arena-cell--in-battle'; }

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
    var points    = ringSegmentPoints(CX, CY, innerR + GAP, outerR - GAP / 2, startAngle, endAngle);
    var bounds    = pointBounds(points);
    var size      = Math.max(bounds.width, bounds.height);
    var cx        = (bounds.minX + bounds.maxX) / 2;
    var cy        = (bounds.minY + bounds.maxY) / 2;
    var clipId    = 'arena-cell-clip-' + Math.random().toString(36).slice(2);
    var svgDefs   = document.querySelector('#arena-puzzle defs');

    if (svgDefs && chef.avatar_url) {
      var clip = svgEl('clipPath', { id: clipId });
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

  function drawCentre(g, center) {
    var R   = RING_RADII.centre[1] - GAP;
    var pts = octagonPoints(CX, CY, R);

    var poly = svgEl('polygon', {
      points: pts,
      fill: center.type === 'active_battle' ? '#c8942a' : '#6c6054',
      stroke: '#fff', 'stroke-width': '2',
      filter: 'url(#arena-cell-shadow)',
      cursor: center.type === 'active_battle' ? 'pointer' : 'default',
      class: 'arena-cell arena-cell--centre',
    });
    if (center.type === 'active_battle' && center.battle_url) {
      poly.addEventListener('click', function () { window.location.href = center.battle_url; });
    }
    g.appendChild(poly);

    if (center.type === 'active_battle') {
      var lbl = svgEl('text', {
        x: CX, y: CY - 4, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: '#fff', 'font-family': 'Georgia, serif', 'font-size': '20', 'font-weight': 'bold',
        'pointer-events': 'none',
      });
      lbl.textContent = (center.challenger ? center.challenger.name.split(' ')[0] : '?') + ' vs ' +
        (center.opponent ? center.opponent.name.split(' ')[0] : '?');
      g.appendChild(lbl);

      var lbl2 = svgEl('text', {
        x: CX, y: CY + 18, 'text-anchor': 'middle', 'dominant-baseline': 'middle',
        fill: 'rgba(255,255,255,0.8)', 'font-family': 'Inter, sans-serif', 'font-size': '11',
        'pointer-events': 'none',
      });
      lbl2.textContent = 'BATTLE IN PROGRESS — click to watch';
      g.appendChild(lbl2);
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
  /* Ripple + click → chef profile                                       */
  /* ------------------------------------------------------------------ */
  function fireCellRipple(e) {
    var svg = document.getElementById('arena-puzzle');
    if (!svg || !e) return;
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

      var MAX_R = 90, DURATION = 380, start = null;
      function step(ts) {
        if (!start) start = ts;
        var progress = Math.min((ts - start) / DURATION, 1);
        var eased = 1 - Math.pow(1 - progress, 3);
        circle.setAttribute('r', (MAX_R * eased).toFixed(1));
        circle.setAttribute('fill-opacity', (0.28 * (1 - progress)).toFixed(3));
        if (progress < 1) { requestAnimationFrame(step); } else { circle.remove(); }
      }
      requestAnimationFrame(step);
    } catch (err) {}
  }

  function attachCellEvents(el, chef) {
    if (!chef) { return; }
    el.addEventListener('click', function (e) {
      fireCellRipple(e);
      setTimeout(function () {
        window.location.href = '/chef-battle/profile/' + chef.slug + '/';
      }, 220);
    });
    el.addEventListener('mouseenter', function () { el.setAttribute('opacity', '0.82'); });
    el.addEventListener('mouseleave', function () { el.removeAttribute('opacity'); });
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
  });

})();
