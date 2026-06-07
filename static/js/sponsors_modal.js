/**
 * CulinEire Sponsor Modal
 * Creates a sponsor application, reserves the selected cell, and redirects to
 * Stripe Checkout.
 */

(function () {
  'use strict';

  var modal = null;
  var modalBody = null;
  var currentCell = null;
  var logoImg = null;
  var logoOffset = { x: 0, y: 0 };
  var logoScale = 1.0;
  var logoRotation = 0; // degrees
  var canvasEl = null;
  var previewShape = null;
  var dragActive = false;
  var dragLast = null;
  var CANVAS_R = 90;
  var CANVAS_CX = 110;
  var CANVAS_CY = 110;
  var PUZZLE_CX = 550;
  var PUZZLE_CY = 550;
  var PUZZLE_GAP = 3;
  var RING_RADII = {
    centre: [0, 85],
    1: [85, 145],
    2: [145, 235],
    3: [235, 325],
    4: [325, 400],
    5: [400, 460],
    6: [460, 515],
  };
  var RING_COUNTS = { 1: 10, 2: 20, 3: 30, 4: 40, 5: 50, 6: 60 };

  document.addEventListener('DOMContentLoaded', function () {
    modal = document.getElementById('sponsor-modal');
    modalBody = document.getElementById('sponsor-modal-body');

    var closeBtn = document.getElementById('sponsor-modal-close');
    if (closeBtn) closeBtn.addEventListener('click', closeModal);
    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) closeModal();
      });
    }
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal && !modal.hidden) closeModal();
    });
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup', function () { dragActive = false; });
    document.addEventListener('touchmove', onTouchMove, { passive: false });
    document.addEventListener('touchend', function () { dragActive = false; });
  });

  function openModal(cellData) {
    currentCell = cellData;
    logoImg = null;
    logoOffset = { x: 0, y: 0 };
    logoScale = 1.0;
    logoRotation = 0;
    canvasEl = null;
    previewShape = null;
    renderModal(cellData || {});
    modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }

  function closeModal() {
    if (modal) modal.hidden = true;
    document.body.style.overflow = '';
    currentCell = null;
  }

  function renderModal(cell) {
    var status = cell.status || 'available';
    var ring = cell.ring || 0;
    var html = '';
    html += '<div class="spm-header">';
    html += '<div class="spm-ring-label ' + ringLabelClass(ring, status) + '">' + (ring === 0 ? 'Central Sponsor of the Month' : 'Ring ' + ring) + '</div>';
    html += '<span class="spm-status spm-status--' + esc(status) + '">' + statusText(status) + '</span>';
    html += '</div>';

    if (isActive(status)) {
      html += renderActive(cell);
    } else if (isReserved(status)) {
      html += renderReserved(status);
    } else {
      html += renderAvailable(cell);
    }

    if (isAdminViewer() && cell.application_detail_url) {
      html += '<div class="spm-admin"><div class="spm-admin-title">Admin moderation</div>';
      html += '<a class="spm-admin-link" href="' + esc(cell.application_detail_url) + '">Open sponsor application</a>';
      html += '</div>';
    }

    modalBody.innerHTML = html;
    bindModalEvents();
  }

  function renderActive(cell) {
    var html = '<div class="spm-sold-content">';
    if (cell.sponsor_logo) {
      html += '<div><img src="' + esc(cell.sponsor_logo) + '" alt="' + esc(cell.sponsor_name || '') + '"></div>';
    }
    if (cell.sponsor_name) html += '<p class="spm-sponsor-name">' + esc(cell.sponsor_name) + '</p>';
    if (cell.sponsor_tagline) html += '<p class="spm-sponsor-tagline">' + esc(cell.sponsor_tagline) + '</p>';
    if (cell.sponsor_url) {
      html += '<a href="' + esc(normalizeUrl(cell.sponsor_url)) + '" target="_blank" rel="noopener noreferrer" class="spm-visit-btn">Visit website &rarr;</a>';
    }
    html += '</div>';
    return html;
  }

  function renderReserved(status) {
    var label = status === 'paid_pending_approval' ? 'paid and pending Bearcave compliance/staff review' : 'currently reserved while checkout is pending';
    return '<div class="spm-reserved-msg">' +
      '<p>This spot is ' + label + '.</p>' +
      '<p class="spm-reserved-note">It will become available again if payment is not completed, or if Bearcave records a terminal rejection/refund outcome before publication.</p>' +
      '</div>';
  }

  function renderAvailable(cell) {
    var html = '';
    var isCentral = cell.ring === 0;
    html += '<p class="spm-price">' + esc(cell.price_display || '') + '</p>';
    html += '<p class="spm-desc">' + (isCentral ? 'Payment reserves the central monthly placement pending Bearcave compliance and staff review. The 30-day term starts only when the approved image and link are published. This is a one-off payment, not an annual placement or recurring subscription.' : 'Payment securely reserves this annual ring spot pending Bearcave compliance and staff review. VAT is calculated at checkout. Businesses, sole traders and individuals are welcome. Publication is subject to Bearcave Limited approval.') + '</p>';
    html += '<form id="spm-application-form" class="spm-form" enctype="multipart/form-data" novalidate>';
    html += '<div class="spm-form-section-label">Sponsor details</div>';
    html += field('spm-sponsor-name', 'text', 'Sponsor display name', 'Business, sole trader or individual name', true, 'organization');
    html += field('spm-contact-name', 'text', 'Contact person', 'Full name', true, 'name');
    html += field('spm-email', 'email', 'Email', 'your@email.com', true, 'email');
    html += field('spm-phone', 'tel', 'Phone', 'Optional', false, 'tel');
    html += field('spm-website-url', 'url', 'Website or profile URL', 'Optional', false, 'url');
    html += '<div class="spm-field"><label class="spm-label" for="spm-sponsor-note">Sponsor note</label><textarea id="spm-sponsor-note" class="spm-textarea" rows="3" placeholder="Optional note for Bearcave"></textarea></div>';
    html += '<div class="spm-form-section-label">Logo or avatar</div>';
    html += '<div class="spm-logo-upload"><label class="spm-logo-drop" for="spm-logo-input" id="spm-logo-label">' + uploadIcon() + '<span id="spm-upload-text">Upload logo or avatar (PNG, JPG or WebP)</span></label><input type="file" id="spm-logo-input" accept="image/png,image/jpeg,image/webp" style="display:none"></div>';
    html += '<div id="spm-canvas-wrap" class="spm-canvas-wrap" hidden><p class="spm-canvas-label">Drag the image and adjust size until it fits this exact cell</p><div class="spm-canvas-outer"><canvas id="spm-canvas" width="220" height="220"></canvas></div><div class="spm-scale-row"><span class="spm-scale-label">Size</span><input type="range" id="spm-scale" min="0.2" max="2.5" step="0.05" value="1.0" class="spm-scale-input"><span id="spm-scale-val" class="spm-scale-val">1.0x</span></div><div class="spm-scale-row"><span class="spm-scale-label spm-scale-label--rotate">Rotate</span><input type="range" id="spm-rotate" min="-180" max="180" step="1" value="0" class="spm-scale-input"><span id="spm-rotate-val" class="spm-scale-val">0°</span></div><button type="button" id="spm-image-reset" class="spm-reset-btn">Reset image position</button></div>';
    html += '<div class="spm-form-section-label">Confirmations</div>';
    html += checkbox('spm-confirm-1', 'I confirm that I have the right to use this logo/avatar and that Bearcave Limited may display it on CulinEire if the sponsorship is approved and published.');
    html += checkbox('spm-confirm-2', isCentral ? 'I accept the CulinEire sponsorship terms for the 30-day Central Sponsor of the Month and understand that payment reserves the selected spot for review only. Payment does not guarantee approval, publication or activation.' : 'I accept the CulinEire Annual Ring Sponsorship Terms and understand that payment reserves the selected spot for review only. Payment does not guarantee approval, publication or activation.');
    html += checkbox('spm-confirm-3', 'I confirm, to the best of my knowledge, that neither I, nor any company, organisation or business I represent, nor any relevant owner, director, beneficial owner or controlling person, is subject to EU, UN, Irish or other applicable financial sanctions. I also confirm that I am not applying on behalf of, for the benefit of, or under the control of any sanctioned person, company, organisation or body.');
    html += '<p class="spm-note">Payment reserves the selected spot while CulinEire reviews the application. Sponsorship may be approved, refused, delayed, cancelled, suspended or marked for manual refund where required by compliance, legal, payment, fraud, content, reputational or policy checks.</p>';
    html += '<div id="spm-form-error" class="spm-error" hidden></div>';
    html += '<div class="spm-actions"><button type="submit" class="spm-buy-btn" id="spm-submit">Continue to secure checkout</button></div>';
    html += '</form>';
    return html;
  }

  function field(id, type, label, placeholder, required, autocomplete) {
    return '<div class="spm-field"><label class="spm-label" for="' + id + '">' + esc(label) + (required ? ' <span class="spm-req">*</span>' : '') + '</label><input type="' + type + '" id="' + id + '" class="spm-input" placeholder="' + esc(placeholder) + '"' + (autocomplete ? ' autocomplete="' + autocomplete + '"' : '') + '></div>';
  }

  function checkbox(id, label) {
    return '<label class="spm-check"><input type="checkbox" id="' + id + '"><span>' + esc(label) + '</span></label>';
  }

  function uploadIcon() {
    return '<svg class="spm-upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17 8 12 3 7 8"/><line x1="12" y1="3" x2="12" y2="15"/></svg>';
  }

  function bindModalEvents() {
    var form = document.getElementById('spm-application-form');
    if (form) form.addEventListener('submit', submitApplication);

    var logoInput = document.getElementById('spm-logo-input');
    if (logoInput) logoInput.addEventListener('change', handleLogoUpload);

    var scale = document.getElementById('spm-scale');
    if (scale) {
      scale.addEventListener('input', function () {
        logoScale = parseFloat(scale.value || '1');
        var val = document.getElementById('spm-scale-val');
        if (val) val.textContent = logoScale.toFixed(1) + 'x';
        redrawCanvas();
      });
    }

    var reset = document.getElementById('spm-image-reset');
    if (reset) {
      reset.addEventListener('click', function () {
        logoOffset = { x: 0, y: 0 };
        logoScale = 1.0;
        logoRotation = 0;
        var scaleInput = document.getElementById('spm-scale');
        var scaleVal = document.getElementById('spm-scale-val');
        if (scaleInput) scaleInput.value = '1.0';
        if (scaleVal) scaleVal.textContent = '1.0x';
        var rotInput = document.getElementById('spm-rotate');
        var rotVal = document.getElementById('spm-rotate-val');
        if (rotInput) rotInput.value = '0';
        if (rotVal) rotVal.textContent = '0°';
        redrawCanvas();
      });
    }

    var rotateSlider = document.getElementById('spm-rotate');
    if (rotateSlider) {
      rotateSlider.addEventListener('input', function () {
        logoRotation = parseFloat(rotateSlider.value || '0');
        var rotVal = document.getElementById('spm-rotate-val');
        if (rotVal) rotVal.textContent = logoRotation.toFixed(0) + '°';
        redrawCanvas();
      });
    }

    canvasEl = document.getElementById('spm-canvas');
    if (canvasEl) {
      canvasEl.addEventListener('mousedown', onCanvasMouseDown);
      canvasEl.addEventListener('touchstart', onCanvasTouchStart, { passive: false });
    }
  }

  function handleLogoUpload(e) {
    var file = e.target.files[0];
    if (!file) return;
    var label = document.getElementById('spm-upload-text');
    if (label) label.textContent = file.name;
    var reader = new FileReader();
    reader.onload = function (ev) {
      var img = new Image();
      img.onload = function () {
        logoImg = img;
        logoOffset = { x: 0, y: 0 };
        logoScale = 1.0;
        logoRotation = 0;
        previewShape = null;
        var rotInput = document.getElementById('spm-rotate');
        var rotVal = document.getElementById('spm-rotate-val');
        if (rotInput) rotInput.value = '0';
        if (rotVal) rotVal.textContent = '0°';
        var scaleInput = document.getElementById('spm-scale');
        var scaleVal = document.getElementById('spm-scale-val');
        if (scaleInput) scaleInput.value = '1.0';
        if (scaleVal) scaleVal.textContent = '1.0x';
        var wrap = document.getElementById('spm-canvas-wrap');
        if (wrap) wrap.hidden = false;
        redrawCanvas();
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
  }

  function octRadius(angle, radius) {
    var sector = Math.PI / 4;
    var half = sector / 2;
    var norm = ((angle % sector) + sector) % sector;
    return radius * Math.cos(half) / Math.cos(norm - half);
  }

  function octPoint(cx, cy, angle, radius) {
    var r = octRadius(angle, radius);
    return [cx + r * Math.cos(angle), cy + r * Math.sin(angle)];
  }

  function octagonPoints(cx, cy, radius) {
    var points = [];
    for (var i = 0; i < 8; i++) {
      var angle = i * Math.PI / 4;
      points.push([cx + radius * Math.cos(angle), cy + radius * Math.sin(angle)]);
    }
    return points;
  }

  function ringSegmentPoints(cx, cy, innerR, outerR, startAngle, endAngle) {
    var steps = 12;
    var points = [];
    var i, angle, point;
    for (i = 0; i <= steps; i++) {
      angle = startAngle + (endAngle - startAngle) * i / steps;
      point = octPoint(cx, cy, angle, outerR);
      points.push(point);
    }
    for (i = steps; i >= 0; i--) {
      angle = startAngle + (endAngle - startAngle) * i / steps;
      point = octPoint(cx, cy, angle, innerR);
      points.push(point);
    }
    return points;
  }

  function pointBounds(points) {
    var minX = Infinity;
    var minY = Infinity;
    var maxX = -Infinity;
    var maxY = -Infinity;
    for (var i = 0; i < points.length; i++) {
      minX = Math.min(minX, points[i][0]);
      minY = Math.min(minY, points[i][1]);
      maxX = Math.max(maxX, points[i][0]);
      maxY = Math.max(maxY, points[i][1]);
    }
    return {
      minX: minX,
      minY: minY,
      maxX: maxX,
      maxY: maxY,
      width: Math.max(1, maxX - minX),
      height: Math.max(1, maxY - minY),
    };
  }

  function buildPreviewShape(cell) {
    var canvas = canvasEl || document.getElementById('spm-canvas');
    var canvasWidth = canvas ? canvas.width : 220;
    var canvasHeight = canvas ? canvas.height : 220;
    var ring = Number(cell && cell.ring ? cell.ring : 0);
    var pos = Number(cell && cell.position_in_ring ? cell.position_in_ring : 0);
    var rawPoints;

    if (ring === 0) {
      rawPoints = octagonPoints(PUZZLE_CX, PUZZLE_CY, RING_RADII.centre[1] - PUZZLE_GAP);
    } else {
      var count = RING_COUNTS[ring] || 1;
      var innerR = RING_RADII[ring][0];
      var outerR = RING_RADII[ring][1];
      var sweep = (2 * Math.PI) / count;
      var offset = -Math.PI / 2 - sweep / 2;
      var startAngle = offset + pos * sweep + PUZZLE_GAP / outerR;
      var endAngle = offset + (pos + 1) * sweep - PUZZLE_GAP / outerR;
      rawPoints = ringSegmentPoints(
        PUZZLE_CX,
        PUZZLE_CY,
        innerR + PUZZLE_GAP,
        outerR - PUZZLE_GAP / 2,
        startAngle,
        endAngle
      );
    }

    var bounds = pointBounds(rawPoints);
    var padding = 16;
    var scale = Math.min(
      (canvasWidth - padding * 2) / bounds.width,
      (canvasHeight - padding * 2) / bounds.height
    );
    var tx = (canvasWidth - bounds.width * scale) / 2 - bounds.minX * scale;
    var ty = (canvasHeight - bounds.height * scale) / 2 - bounds.minY * scale;
    var points = rawPoints.map(function (point) {
      return [point[0] * scale + tx, point[1] * scale + ty];
    });
    var previewBounds = pointBounds(points);
    return {
      points: points,
      bounds: previewBounds,
      center: {
        x: (previewBounds.minX + previewBounds.maxX) / 2,
        y: (previewBounds.minY + previewBounds.maxY) / 2,
      },
      refRadius: Math.max(previewBounds.width, previewBounds.height) / 2,
    };
  }

  function drawPreviewPath(ctx, shape) {
    var points = shape && shape.points ? shape.points : octagonPoints(CANVAS_CX, CANVAS_CY, CANVAS_R);
    ctx.beginPath();
    for (var i = 0; i < points.length; i++) {
      if (i === 0) {
        ctx.moveTo(points[i][0], points[i][1]);
      } else {
        ctx.lineTo(points[i][0], points[i][1]);
      }
    }
    ctx.closePath();
  }

  function redrawCanvas() {
    var canvas = canvasEl || document.getElementById('spm-canvas');
    if (!canvas) return;
    var ctx = canvas.getContext('2d');
    previewShape = previewShape || buildPreviewShape(currentCell || {});
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    drawPreviewPath(ctx, previewShape);
    ctx.fillStyle = '#f4f1ec';
    ctx.fill();
    ctx.strokeStyle = 'rgba(58,48,40,0.25)';
    ctx.lineWidth = 2;
    ctx.stroke();
    if (!logoImg) return;
    ctx.save();
    drawPreviewPath(ctx, previewShape);
    ctx.clip();
    var refRadius = previewShape.refRadius || CANVAS_R;
    var center = previewShape.center || { x: CANVAS_CX, y: CANVAS_CY };
    var baseSize = refRadius * 2 * logoScale;
    var lw, lh;
    if (logoImg.width >= logoImg.height) {
      lh = baseSize;
      lw = baseSize * (logoImg.width / logoImg.height);
    } else {
      lw = baseSize;
      lh = baseSize * (logoImg.height / logoImg.width);
    }
    var cx = center.x + logoOffset.x;
    var cy = center.y + logoOffset.y;
    ctx.translate(cx, cy);
    if (logoRotation) ctx.rotate(logoRotation * Math.PI / 180);
    ctx.drawImage(logoImg, -lw / 2, -lh / 2, lw, lh);
    ctx.restore();
  }

  function onCanvasMouseDown(e) {
    e.preventDefault();
    dragActive = true;
    dragLast = { x: e.clientX, y: e.clientY };
  }

  function onCanvasTouchStart(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
      dragActive = true;
      dragLast = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
  }

  function onMouseMove(e) {
    if (!dragActive) return;
    logoOffset.x += e.clientX - dragLast.x;
    logoOffset.y += e.clientY - dragLast.y;
    dragLast = { x: e.clientX, y: e.clientY };
    redrawCanvas();
  }

  function onTouchMove(e) {
    if (!dragActive || e.touches.length !== 1) return;
    e.preventDefault();
    logoOffset.x += e.touches[0].clientX - dragLast.x;
    logoOffset.y += e.touches[0].clientY - dragLast.y;
    dragLast = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    redrawCanvas();
  }

  function submitApplication(e) {
    e.preventDefault();
    if (!currentCell) return;

    var err = document.getElementById('spm-form-error');
    var btn = document.getElementById('spm-submit');
    if (err) {
      err.hidden = true;
      err.textContent = '';
    }

    var logoInput = document.getElementById('spm-logo-input');
    if (!val('spm-sponsor-name') || !val('spm-contact-name') || !val('spm-email')) {
      return showErr('Please complete the required sponsor details.');
    }
    if (!logoInput || !logoInput.files.length) {
      return showErr('Please upload a sponsor logo or avatar.');
    }
    if (!checked('spm-confirm-1') || !checked('spm-confirm-2') || !checked('spm-confirm-3')) {
      return showErr('Please tick all required confirmations.');
    }

    var fd = new FormData();
    fd.append('sponsor_name', val('spm-sponsor-name'));
    fd.append('contact_name', val('spm-contact-name'));
    fd.append('email', val('spm-email'));
    fd.append('phone', val('spm-phone'));
    fd.append('website_url', val('spm-website-url'));
    fd.append('sponsor_note', val('spm-sponsor-note'));
    fd.append('logo', logoInput.files[0]);
    var refRadius = (previewShape && previewShape.refRadius) || CANVAS_R;
    fd.append('logo_offset_x', (logoOffset.x / refRadius * 100).toFixed(2));
    fd.append('logo_offset_y', (logoOffset.y / refRadius * 100).toFixed(2));
    fd.append('logo_scale', logoScale.toFixed(3));
    fd.append('logo_rotation', logoRotation.toFixed(2));
    fd.append('logo_rights_confirmed', 'on');
    fd.append('terms_accepted', 'on');
    fd.append('sanctions_declaration_1', 'on');

    if (btn) {
      btn.disabled = true;
      btn.textContent = 'Opening checkout...';
    }

    fetch('/sponsors/cell/' + currentCell.id + '/enquire/', {
      method: 'POST',
      headers: { 'X-CSRFToken': getCsrf() },
      body: fd,
    })
      .then(function (r) {
        return r.json().then(function (data) { return { ok: r.ok, data: data }; });
      })
      .then(function (res) {
        if (res.ok && res.data.checkout_url) {
          window.location.href = res.data.checkout_url;
          return;
        }
        showErr(res.data.error || 'Checkout could not be started.');
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Continue to secure checkout';
        }
      })
      .catch(function () {
        showErr('Network error. Please try again.');
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Continue to secure checkout';
        }
      });
  }

  function val(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }

  function checked(id) {
    var el = document.getElementById(id);
    return !!(el && el.checked);
  }

  function showErr(msg) {
    var err = document.getElementById('spm-form-error');
    if (err) {
      err.textContent = msg;
      err.hidden = false;
    }
  }

  function isAdminViewer() {
    var el = document.getElementById('sponsor-is-admin-json');
    return el ? JSON.parse(el.textContent) : false;
  }

  function getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function normalizeUrl(url) {
    return /^https?:\/\//i.test(url) ? url : 'https://' + url;
  }

  function isActive(status) {
    return status === 'active' || status === 'sold';
  }

  function isReserved(status) {
    return status === 'payment_pending' || status === 'paid_pending_approval' || status === 'reserved';
  }

  function ringLabelClass(ring, status) {
    if (ring === 0) return 'spm-ring-label--centre';
    if (isActive(status)) return 'spm-ring-label--sold';
    if (isReserved(status)) return 'spm-ring-label--reserved';
    return '';
  }

  function statusText(status) {
    return {
      available: 'Available',
      payment_pending: 'Payment pending',
      paid_pending_approval: 'Paid pending review',
      active: 'Active',
      expired: 'Expired',
      rejected: 'Rejected',
      unavailable: 'Unavailable',
      reserved: 'Reserved',
      sold: 'Sold',
    }[status] || status;
  }

  function esc(str) {
    return String(str || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  window.SponsorModal = { open: openModal, close: closeModal };
}());
