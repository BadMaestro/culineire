/**
 * CulinEire Sponsor Puzzle
 * Renders a concentric octagonal SVG puzzle.
 *
 * Layout (outer → inner):
 *   Ring 4 – 40 cells – €100
 *   Ring 3 – 30 cells – €200
 *   Ring 2 – 20 cells – €400
 *   Ring 1 – 10 cells – €800
 *   Centre  – 1  cell  – price on request
 */

(function () {
  'use strict';

  /* ------------------------------------------------------------------ */
  /* Config                                                               */
  /* ------------------------------------------------------------------ */
  var CX = 550, CY = 550;   // SVG centre
  var GAP = 3;               // gap between cells (px)

  // Radii of each ring boundary (inner edge, then outer edge per ring)
  var RING_RADII = {
    centre : [0,   65],
    1      : [65,  145],
    2      : [145, 235],
    3      : [235, 325],
    4      : [325, 400],
    5      : [400, 460],
    6      : [460, 515],
  };

  var RING_COUNTS = { 1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60 };

  var RING_COLOURS = {
    available : { 6: '#f4f1ec', 5: '#ede8df', 4: '#e4ddd1', 3: '#d8d0c0', 2: '#ccc1aa', 1: '#bfb49a', 0: '#b8af96' },
    reserved  : { 6: '#faf0d8', 5: '#f5e6c8', 4: '#f2ddb2', 3: '#efd49c', 2: '#ebca86', 1: '#e6c070', 0: '#e0b85a' },
    sold      : { 6: '#ddf0dd', 5: '#c8dfc8', 4: '#b0d4b0', 3: '#8fc58f', 2: '#6db46d', 1: '#4a9e4a', 0: '#2a7a2a' },
  };

  var STATUS_LABEL = { available: 'Available', reserved: 'Reserved', sold: 'Sold' };

  /* ------------------------------------------------------------------ */
  /* Math helpers                                                         */
  /* ------------------------------------------------------------------ */

  /**
   * For a regular octagon with circumradius R, return the actual distance
   * from centre to boundary at a given angle.
   * (octagon vertices at 22.5°, 67.5°, … from +x axis)
   */
  function octRadius(angle, R) {
    var sector = Math.PI / 4;        // π/4 = 45°
    var half   = sector / 2;         // π/8 = 22.5°
    // normalise angle into [0, sector)
    var norm = ((angle % sector) + sector) % sector;
    return R * Math.cos(half) / Math.cos(norm - half);
  }

  /**
   * Point on the octagonal boundary at a given angle and "octagon size" R.
   */
  function octPoint(cx, cy, angle, R) {
    var r = octRadius(angle, R);
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  }

  /**
   * Build an SVG arc-path string for one ring segment.
   * The segment spans angles [startAngle, endAngle] between inner and outer radii.
   */
  function ringSegmentPath(cx, cy, innerR, outerR, startAngle, endAngle) {
    var STEPS = 12;   // number of points on each arc edge
    var pts   = [];
    var i, angle, pt;

    // Outer edge: clockwise from startAngle → endAngle
    for (i = 0; i <= STEPS; i++) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pt = octPoint(cx, cy, angle, outerR);
      pts.push(pt[0].toFixed(2) + ',' + pt[1].toFixed(2));
    }

    // Inner edge: counter-clockwise from endAngle → startAngle
    for (i = STEPS; i >= 0; i--) {
      angle = startAngle + (endAngle - startAngle) * i / STEPS;
      pt = octPoint(cx, cy, angle, innerR);
      pts.push(pt[0].toFixed(2) + ',' + pt[1].toFixed(2));
    }

    return 'M ' + pts[0] + ' L ' + pts.slice(1).join(' L ') + ' Z';
  }

  /**
   * Build the full octagon polygon points string (for clip-path or border).
   */
  function octagonPoints(cx, cy, R) {
    var pts = [];
    for (var i = 0; i < 8; i++) {
      var angle = Math.PI / 8 + i * Math.PI / 4;
      var r     = octRadius(angle, R);
      pts.push((cx + r * Math.cos(angle)).toFixed(2) + ',' + (cy + r * Math.sin(angle)).toFixed(2));
    }
    return pts.join(' ');
  }

  /* ------------------------------------------------------------------ */
  /* SVG helper                                                           */
  /* ------------------------------------------------------------------ */
  function svgEl(tag, attrs) {
    var el = document.createElementNS('http://www.w3.org/2000/svg', tag);
    for (var k in attrs) {
      if (Object.prototype.hasOwnProperty.call(attrs, k)) {
        el.setAttribute(k, attrs[k]);
      }
    }
    return el;
  }

  /* ------------------------------------------------------------------ */
  /* Build cell lookup by ring+position                                   */
  /* ------------------------------------------------------------------ */
  function buildCellMap(cells) {
    var map = {};
    for (var i = 0; i < cells.length; i++) {
      var c = cells[i];
      var key = c.ring + '_' + c.position_in_ring;
      map[key] = c;
    }
    return map;
  }

  /* ------------------------------------------------------------------ */
  /* Draw puzzle                                                          */
  /* ------------------------------------------------------------------ */
  function drawPuzzle(cells) {
    var svg     = document.getElementById('sponsor-puzzle');
    var group   = document.getElementById('puzzle-cells');
    var centreG = document.getElementById('puzzle-centre');
    var octPoly = document.getElementById('oct-poly');

    // Set octagon clip polygon
    octPoly.setAttribute('points', octagonPoints(CX, CY, RING_RADII[6][1] + 10));

    var cellMap = buildCellMap(cells);

    /* -- Draw rings 4 → 1 -------------------------------------------- */
    var rings = [6, 5, 4, 3, 2, 1];
    for (var ri = 0; ri < rings.length; ri++) {
      var ring    = rings[ri];
      var count   = RING_COUNTS[ring];
      var innerR  = RING_RADII[ring][0];
      var outerR  = RING_RADII[ring][1];
      var sweep   = (2 * Math.PI) / count;
      // offset so cells are vertically centred (start from top)
      var offset  = -Math.PI / 2 - sweep / 2;

      for (var pos = 0; pos < count; pos++) {
        var startAngle = offset + pos * sweep + GAP / outerR;
        var endAngle   = offset + (pos + 1) * sweep - GAP / outerR;

        var path = ringSegmentPath(CX, CY, innerR + GAP, outerR - GAP / 2, startAngle, endAngle);

        var cellData = cellMap[ring + '_' + pos] || null;
        var status   = cellData ? cellData.status : 'available';
        var fill     = (RING_COLOURS[status] || RING_COLOURS.available)[ring];

        var pathEl = svgEl('path', {
          d            : path,
          fill         : fill,
          stroke       : '#fff',
          'stroke-width': '1.5',
          'filter'     : 'url(#cell-shadow)',
          'cursor'     : 'pointer',
          'class'      : 'puzzle-cell puzzle-cell--' + status + ' puzzle-cell--ring-' + ring,
          'data-ring'  : ring,
          'data-pos'   : pos,
          'data-status': status,
        });

        if (cellData && cellData.sponsor_logo && status === 'sold') {
          pathEl.setAttribute('fill', fill);
          pathEl.setAttribute('opacity', '0.85');
        }

        attachCellEvents(pathEl, cellData, ring, pos);
        group.appendChild(pathEl);

        // Price label inside cell
        addCellPriceLabel(group, ring, innerR, outerR, startAngle, endAngle, status, cellData);

        // Add sponsor logo for sold cells (rendered as SVG image)
        if (cellData && cellData.sponsor_logo && status === 'sold') {
          appendLogoToCell(group, cellData, ring, pos, innerR, outerR, offset, sweep, count);
        }
      }
    }

    /* -- Draw centre -------------------------------------------------- */
    drawCentre(centreG, cellMap['0_0'] || null);
  }

  function drawCentre(g, cellData) {
    // Centre octagon
    var R = RING_RADII.centre[1] - GAP;
    var pts = octagonPoints(CX, CY, R);

    var status = (cellData && cellData.status !== 'available') ? cellData.status : 'centre';
    var fill   = '#2a5c34';  // CulinEire green

    var poly = svgEl('polygon', {
      points       : pts,
      fill         : fill,
      stroke       : '#fff',
      'stroke-width': '2',
      'filter'     : 'url(#cell-shadow)',
      'cursor'     : 'pointer',
      'class'      : 'puzzle-cell puzzle-cell--centre',
    });

    attachCellEvents(poly, cellData, 0, 0);
    g.appendChild(poly);

    // CulinEire text in centre
    var text1 = svgEl('text', {
      x           : CX,
      y           : CY - 8,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      fill        : '#fff',
      'font-family': 'Georgia, serif',
      'font-size' : '22',
      'font-weight': 'bold',
      'pointer-events': 'none',
    });
    text1.textContent = 'CulinEire';

    var text2 = svgEl('text', {
      x           : CX,
      y           : CY + 18,
      'text-anchor': 'middle',
      'dominant-baseline': 'middle',
      fill        : 'rgba(255,255,255,0.7)',
      'font-family': 'Georgia, serif',
      'font-size' : '11',
      'pointer-events': 'none',
    });
    text2.textContent = '★ FOUNDING SPONSOR';

    g.appendChild(text1);
    g.appendChild(text2);
  }

  /**
   * Compute the centroid angle and approximate radius for a ring segment,
   * used to position logos.
   */
  function segmentCentroid(innerR, outerR, startAngle, endAngle) {
    var midAngle = (startAngle + endAngle) / 2;
    var midR     = (innerR + outerR) / 2;
    var r = octRadius(midAngle, midR);
    return [CX + r * Math.cos(midAngle), CY + r * Math.sin(midAngle)];
  }

  var RING_PRICE_LABEL = {1: '€800', 2: '€400', 3: '€200', 4: '€100', 5: '€50', 6: '€25'};
  var RING_FONT_SIZE   = {1: 13, 2: 12, 3: 11, 4: 10, 5: 9, 6: 8};

  function addCellPriceLabel(group, ring, innerR, outerR, startAngle, endAngle, status, cellData) {
    // Don't show price label on sold cells that have a logo — logo replaces it
    if (status === 'sold' && cellData && cellData.sponsor_logo) { return; }

    var centroid  = segmentCentroid(innerR + GAP, outerR - GAP / 2, startAngle, endAngle);
    var midAngle  = (startAngle + endAngle) / 2;
    var fontSize  = RING_FONT_SIZE[ring] || 9;

    // Rotate text to follow the ring radially (so it's readable outward)
    var rotateDeg = (midAngle * 180 / Math.PI) + 90;
    // Keep text upright for left-side cells
    if (rotateDeg > 90 && rotateDeg < 270) { rotateDeg += 180; }

    var label;
    if (status === 'sold' && cellData && cellData.sponsor_name) {
      // Show short sponsor name (first word, max 6 chars)
      var name = cellData.sponsor_name.split(' ')[0];
      label = name.length > 6 ? name.slice(0, 5) + '…' : name;
    } else {
      label = RING_PRICE_LABEL[ring] || '';
    }

    var textColour = (status === 'sold') ? 'rgba(255,255,255,0.9)' : 'rgba(60,55,45,0.65)';

    var textEl = svgEl('text', {
      x                  : centroid[0].toFixed(1),
      y                  : centroid[1].toFixed(1),
      'text-anchor'      : 'middle',
      'dominant-baseline': 'middle',
      fill               : textColour,
      'font-family'      : 'Inter, sans-serif',
      'font-size'        : fontSize,
      'font-weight'      : '600',
      'pointer-events'   : 'none',
      transform          : 'rotate(' + rotateDeg.toFixed(1) + ',' + centroid[0].toFixed(1) + ',' + centroid[1].toFixed(1) + ')',
    });
    textEl.textContent = label;
    group.appendChild(textEl);
  }

  function appendLogoToCell(group, cellData, ring, pos, innerR, outerR, offset, sweep, count) {
    var startAngle = offset + pos * sweep;
    var endAngle   = offset + (pos + 1) * sweep;
    var centroid   = segmentCentroid(innerR + GAP, outerR - GAP / 2, startAngle, endAngle);
    var size = Math.min((outerR - innerR) * 0.6, 36);

    var img = svgEl('image', {
      href            : cellData.sponsor_logo,
      x               : (centroid[0] - size / 2).toFixed(1),
      y               : (centroid[1] - size / 2).toFixed(1),
      width           : size.toFixed(1),
      height          : size.toFixed(1),
      preserveAspectRatio: 'xMidYMid meet',
      'pointer-events': 'none',
    });
    group.appendChild(img);
  }

  /* ------------------------------------------------------------------ */
  /* Cell events — open modal on click                                   */
  /* ------------------------------------------------------------------ */
  function attachCellEvents(el, cellData, ring, pos) {
    el.addEventListener('click', function () {
      if (window.SponsorModal) {
        window.SponsorModal.open(cellData);
      }
    });
    el.addEventListener('mouseenter', function () {
      el.setAttribute('opacity', '0.82');
    });
    el.addEventListener('mouseleave', function () {
      el.removeAttribute('opacity');
    });
  }

  /* ------------------------------------------------------------------ */
  /* Init                                                                 */
  /* ------------------------------------------------------------------ */
  document.addEventListener('DOMContentLoaded', function () {
    var el = document.getElementById('sponsor-cells-json');
    var cells = [];
    if (el) {
      try { cells = JSON.parse(el.textContent); } catch (e) {}
    }
    if (cells.length > 0) {
      drawPuzzle(cells);
    } else {
      // No cells in DB yet — show placeholder
      drawEmptyPuzzle();
    }
  });

  function drawEmptyPuzzle() {
    // Generate dummy cells to show the layout
    var dummy = [];
    var n = 0;
    var layout = [[6, 60], [5, 50], [4, 40], [3, 30], [2, 20], [1, 10]];
    var prices = {6: 25, 5: 50, 4: 100, 3: 200, 2: 400, 1: 800};
    for (var ri = 0; ri < layout.length; ri++) {
      var ring = layout[ri][0], count = layout[ri][1];
      for (var pos = 0; pos < count; pos++) {
        dummy.push({
          id: n++, cell_number: n, ring: ring, position_in_ring: pos,
          status: 'available', sponsor_name: '', sponsor_logo: null,
          sponsor_url: '', sponsor_tagline: '',
          price: prices[ring], price_display: '€' + prices[ring] + '/yr', is_centre: false,
        });
      }
    }
    dummy.push({
      id: 999, cell_number: 0, ring: 0, position_in_ring: 0,
      status: 'available', sponsor_name: '', sponsor_logo: null,
      sponsor_url: '', sponsor_tagline: '',
      price: 30000, price_display: '€30,000/yr', is_centre: true, centre_label: 'Central Founding Partner',
    });
    drawPuzzle(dummy);
  }

})();
