/**
 * CulinEire Sponsor Modal
 * AJAX-powered modal for each sponsor cell:
 *  - Enquiry form with logo upload
 *  - Drag-to-reposition canvas preview
 *  - Scale slider
 *  - Admin moderation panel (approve / reject)
 */

(function () {
  'use strict';

  /* ------------------------------------------------------------------ */
  /* State                                                               */
  /* ------------------------------------------------------------------ */
  var modal     = null;
  var modalBody = null;
  var currentCell  = null;
  var logoImg      = null;
  var logoOffset   = { x: 0, y: 0 };
  var logoScale    = 1.0;
  var dragActive   = false;
  var dragLast     = null;
  var canvasEl     = null;

  /* ------------------------------------------------------------------ */
  /* Init                                                                */
  /* ------------------------------------------------------------------ */
  document.addEventListener('DOMContentLoaded', function () {
    modal     = document.getElementById('sponsor-modal');
    modalBody = document.getElementById('sponsor-modal-body');

    var closeBtn = document.getElementById('sponsor-modal-close');
    if (closeBtn) {
      closeBtn.addEventListener('click', closeModal);
    }

    if (modal) {
      modal.addEventListener('click', function (e) {
        if (e.target === modal) { closeModal(); }
      });
    }

    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape' && modal && !modal.hidden) { closeModal(); }
    });

    // Global drag listeners (canvas drag continues outside canvas)
    document.addEventListener('mousemove', onMouseMove);
    document.addEventListener('mouseup',   onMouseUp);
    document.addEventListener('touchmove', onTouchMove, { passive: false });
    document.addEventListener('touchend',  onTouchEnd);
  });

  /* ------------------------------------------------------------------ */
  /* Open / Close                                                        */
  /* ------------------------------------------------------------------ */
  function openModal(cellData) {
    currentCell = cellData;
    logoImg     = null;
    logoOffset  = { x: 0, y: 0 };
    logoScale   = 1.0;
    dragActive  = false;
    canvasEl    = null;

    renderModal(cellData);
    modal.hidden = false;
    document.body.style.overflow = 'hidden';

    // If admin, fetch extra enquiry + pending-logo data
    if (window.IS_ADMIN && cellData && cellData.id) {
      loadAdminPanel(cellData.id);
    }
  }

  function closeModal() {
    if (modal) { modal.hidden = true; }
    document.body.style.overflow = '';
    currentCell = null;
  }

  /* ------------------------------------------------------------------ */
  /* Render                                                              */
  /* ------------------------------------------------------------------ */
  function renderModal(cell) {
    if (!modalBody) { return; }

    var ring   = cell ? cell.ring   : 0;
    var status = cell ? cell.status : 'available';

    var html = '';

    /* -- Header -- */
    html += '<div class="spm-header">';
    html += '<div class="spm-ring-label ' + ringLabelClass(ring, status) + '">';
    html += ring === 0 ? 'Central Founding Partner' : 'Ring ' + ring;
    html += '</div>';
    html += '<span class="spm-status spm-status--' + status + '">' + statusText(status) + '</span>';
    html += '</div>';

    /* -- Content -- */
    if (status === 'sold') {
      html += renderSold(cell);
    } else if (status === 'reserved') {
      html += renderReserved();
    } else {
      html += renderAvailable(cell, ring);
    }

    /* -- Admin placeholder -- */
    html += '<div id="spm-admin-panel" hidden></div>';

    modalBody.innerHTML = html;
    bindFormEvents(cell, ring);
  }

  /* ---- Sold ---- */
  function renderSold(cell) {
    var html = '<div class="spm-sold-content">';
    if (cell.sponsor_logo) {
      html += '<div><img src="' + esc(cell.sponsor_logo) + '" alt="' + esc(cell.sponsor_name || '') + '"></div>';
    }
    if (cell.sponsor_name) {
      html += '<p class="spm-sponsor-name">' + esc(cell.sponsor_name) + '</p>';
    }
    if (cell.sponsor_tagline) {
      html += '<p class="spm-sponsor-tagline">' + esc(cell.sponsor_tagline) + '</p>';
    }
    if (cell.sponsor_url) {
      html += '<a href="' + esc(cell.sponsor_url) + '" target="_blank" rel="noopener noreferrer" class="spm-visit-btn">Visit website &rarr;</a>';
    }
    html += '</div>';
    return html;
  }

  /* ---- Reserved ---- */
  function renderReserved() {
    return '<div class="spm-reserved-msg">' +
      '<p>This spot is currently reserved and pending confirmation.</p>' +
      '<p class="spm-reserved-note">It will become available again if the reservation expires.</p>' +
      '</div>';
  }

  /* ---- Available ---- */
  function renderAvailable(cell, ring) {
    var isCentre = (ring === 0);
    var html = '';

    if (isCentre) {
      html += '<p class="spm-price spm-price--secret">Price on request</p>';
      html += '<p class="spm-desc">The most exclusive placement on the puzzle. One annual contract with Bearcave Ltd. — your brand at the very heart of CulinEire.</p>';
    } else {
      html += '<p class="spm-price">' + esc(cell ? cell.price_display : ringPrice(ring)) + '</p>';
      html += '<p class="spm-desc">Your logo appears here, linked to your website, visible to every CulinEire visitor. Annual contract with Bearcave Ltd.</p>';
    }

    /* Enquiry form */
    html += '<form id="spm-enquiry-form" class="spm-form" novalidate>';

    /* Section: contact */
    html += '<div class="spm-form-section-label">Contact details</div>';
    html += field('spm-name',    'text',  'Name',    'Your full name',        true,  'name');
    html += field('spm-email',   'email', 'Email',   'your@email.com',        true,  'email');
    html += field('spm-company', 'text',  'Company', 'Your company name',     false, 'organization');
    html += field('spm-website', 'url',   'Website', 'https://yoursite.com',  false, 'url');

    html += '<div class="spm-field">';
    html += '<label class="spm-label" for="spm-message">Message</label>';
    html += '<textarea id="spm-message" name="message" class="spm-textarea" rows="3" placeholder="Tell us about your brand..."></textarea>';
    html += '</div>';

    /* Section: logo */
    html += '<div class="spm-form-section-label">Logo preview <span class="spm-optional">optional</span></div>';
    html += '<div class="spm-logo-upload">';
    html += '<label class="spm-logo-drop" for="spm-logo-input" id="spm-logo-label">';
    html += uploadIcon();
    html += '<span id="spm-upload-text">Click to upload your logo</span>';
    html += '</label>';
    html += '<input type="file" id="spm-logo-input" name="logo" accept="image/*" style="display:none">';
    html += '</div>';

    /* Canvas (hidden until image chosen) */
    html += '<div id="spm-canvas-wrap" class="spm-canvas-wrap" hidden>';
    html += '<p class="spm-canvas-label">Drag to position your logo inside the cell</p>';
    html += '<div class="spm-canvas-outer"><canvas id="spm-canvas" width="220" height="220"></canvas></div>';
    html += '<div class="spm-scale-row">';
    html += '<span class="spm-scale-label">Size</span>';
    html += '<input type="range" id="spm-scale" min="0.2" max="2.5" step="0.05" value="1.0" class="spm-scale-input">';
    html += '<span id="spm-scale-val" class="spm-scale-val">1.0&times;</span>';
    html += '</div>';
    html += '</div>';

    html += '<div id="spm-form-error" class="spm-error" hidden></div>';
    html += '<div id="spm-form-success" class="spm-success" hidden></div>';

    html += '<div class="spm-actions">';
    html += '<button type="submit" class="spm-buy-btn" id="spm-submit">Reserve this spot</button>';
    html += '</div>';
    html += '<p class="spm-note">Bearcave Ltd. will contact you within 24 hours to arrange the annual contract.</p>';
    html += '</form>';

    return html;
  }

  function field(id, type, label, placeholder, required, autocomplete) {
    return '<div class="spm-field">' +
      '<label class="spm-label" for="' + id + '">' + esc(label) + (required ? ' <span class="spm-req">*</span>' : '') + '</label>' +
      '<input type="' + type + '" id="' + id + '" name="' + id.replace('spm-', '') + '" class="spm-input"' +
        ' placeholder="' + esc(placeholder) + '"' +
        (autocomplete ? ' autocomplete="' + autocomplete + '"' : '') + '>' +
      '</div>';
  }

  function uploadIcon() {
    return '<svg class="spm-upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>' +
      '<polyline points="17 8 12 3 7 8"/>' +
      '<line x1="12" y1="3" x2="12" y2="15"/>' +
      '</svg>';
  }

  /* ------------------------------------------------------------------ */
  /* Bind form events after HTML injection                               */
  /* ------------------------------------------------------------------ */
  function bindFormEvents(cell, ring) {
    var form = document.getElementById('spm-enquiry-form');
    if (form) {
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        submitEnquiry(cell);
      });
    }

    var logoInput = document.getElementById('spm-logo-input');
    if (logoInput) {
      logoInput.addEventListener('change', handleLogoUpload);
    }

    var scaleSlider = document.getElementById('spm-scale');
    if (scaleSlider) {
      scaleSlider.addEventListener('input', function () {
        logoScale = parseFloat(this.value);
        var valEl = document.getElementById('spm-scale-val');
        if (valEl) { valEl.textContent = logoScale.toFixed(1) + '×'; }
        redrawCanvas();
      });
    }

    canvasEl = document.getElementById('spm-canvas');
    if (canvasEl) {
      canvasEl.addEventListener('mousedown',  onCanvasMouseDown);
      canvasEl.addEventListener('touchstart', onCanvasTouchStart, { passive: false });
    }
  }

  /* ------------------------------------------------------------------ */
  /* Logo upload                                                         */
  /* ------------------------------------------------------------------ */
  function handleLogoUpload(e) {
    var file = e.target.files[0];
    if (!file) { return; }

    var label = document.getElementById('spm-upload-text');
    if (label) { label.textContent = file.name; }

    var reader = new FileReader();
    reader.onload = function (ev) {
      var img   = new Image();
      img.onload = function () {
        logoImg    = img;
        logoOffset = { x: 0, y: 0 };
        logoScale  = 1.0;

        var slider = document.getElementById('spm-scale');
        if (slider) { slider.value = '1.0'; }
        var valEl = document.getElementById('spm-scale-val');
        if (valEl)  { valEl.textContent = '1.0×'; }

        var wrap = document.getElementById('spm-canvas-wrap');
        if (wrap) { wrap.hidden = false; }

        redrawCanvas();
      };
      img.src = ev.target.result;
    };
    reader.readAsDataURL(file);
  }

  /* ------------------------------------------------------------------ */
  /* Canvas                                                              */
  /* ------------------------------------------------------------------ */
  var CANVAS_R  = 90;   // octagon radius on canvas (px)
  var CANVAS_CX = 110;
  var CANVAS_CY = 110;

  function redrawCanvas() {
    var canvas = canvasEl || document.getElementById('spm-canvas');
    if (!canvas) { return; }
    var ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    var ring      = currentCell ? currentCell.ring : 1;
    var fillColor = cellFill(ring);

    /* Draw octagonal cell shape */
    ctx.beginPath();
    for (var i = 0; i < 8; i++) {
      var a = Math.PI / 8 + i * Math.PI / 4;
      var px = CANVAS_CX + CANVAS_R * Math.cos(a);
      var py = CANVAS_CY + CANVAS_R * Math.sin(a);
      if (i === 0) { ctx.moveTo(px, py); }
      else         { ctx.lineTo(px, py); }
    }
    ctx.closePath();
    ctx.fillStyle = fillColor;
    ctx.fill();
    ctx.strokeStyle = 'rgba(255,255,255,0.35)';
    ctx.lineWidth   = 2;
    ctx.stroke();

    /* Guide crosshair */
    ctx.save();
    ctx.strokeStyle = 'rgba(255,255,255,0.25)';
    ctx.lineWidth   = 1;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(CANVAS_CX - 18, CANVAS_CY); ctx.lineTo(CANVAS_CX + 18, CANVAS_CY);
    ctx.moveTo(CANVAS_CX, CANVAS_CY - 18); ctx.lineTo(CANVAS_CX, CANVAS_CY + 18);
    ctx.stroke();
    ctx.setLineDash([]);
    ctx.restore();

    /* Draw logo */
    if (logoImg) {
      var maxSize = CANVAS_R * 1.5 * logoScale;
      var lw, lh;
      if (logoImg.width >= logoImg.height) {
        lw = maxSize;
        lh = maxSize * (logoImg.height / logoImg.width);
      } else {
        lh = maxSize;
        lw = maxSize * (logoImg.width / logoImg.height);
      }
      var lx = CANVAS_CX + logoOffset.x - lw / 2;
      var ly = CANVAS_CY + logoOffset.y - lh / 2;
      ctx.drawImage(logoImg, lx, ly, lw, lh);
    }
  }

  var CELL_COLOURS = {
    0: '#2a5c34', 1: '#bfb49a', 2: '#ccc1aa', 3: '#d8d0c0',
    4: '#e4ddd1', 5: '#ede8df', 6: '#f4f1ec',
  };

  function cellFill(ring) {
    return CELL_COLOURS[ring] || '#d8d0c0';
  }

  /* ------------------------------------------------------------------ */
  /* Canvas drag                                                         */
  /* ------------------------------------------------------------------ */
  function onCanvasMouseDown(e) {
    e.preventDefault();
    dragActive = true;
    dragLast   = { x: e.clientX, y: e.clientY };
  }

  function onMouseMove(e) {
    if (!dragActive) { return; }
    logoOffset.x += e.clientX - dragLast.x;
    logoOffset.y += e.clientY - dragLast.y;
    dragLast = { x: e.clientX, y: e.clientY };
    redrawCanvas();
  }

  function onMouseUp() {
    dragActive = false;
  }

  function onCanvasTouchStart(e) {
    e.preventDefault();
    if (e.touches.length === 1) {
      dragActive = true;
      dragLast   = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
  }

  function onTouchMove(e) {
    if (!dragActive || e.touches.length !== 1) { return; }
    e.preventDefault();
    logoOffset.x += e.touches[0].clientX - dragLast.x;
    logoOffset.y += e.touches[0].clientY - dragLast.y;
    dragLast = { x: e.touches[0].clientX, y: e.touches[0].clientY };
    redrawCanvas();
  }

  function onTouchEnd() {
    dragActive = false;
  }

  /* ------------------------------------------------------------------ */
  /* Form submission                                                     */
  /* ------------------------------------------------------------------ */
  function submitEnquiry(cell) {
    if (!cell) { return; }

    var errEl = document.getElementById('spm-form-error');
    var sucEl = document.getElementById('spm-form-success');
    var btn   = document.getElementById('spm-submit');
    var form  = document.getElementById('spm-enquiry-form');

    if (errEl) { errEl.hidden = true; errEl.textContent = ''; }
    if (sucEl) { sucEl.hidden = true; }

    var name    = val('spm-name');
    var email   = val('spm-email');
    var company = val('spm-company');
    var website = val('spm-website');
    var message = val('spm-message');

    if (!name)  { showErr(errEl, 'Please enter your name.'); return; }
    if (!email) { showErr(errEl, 'Please enter your email address.'); return; }

    var fd = new FormData();
    fd.append('name',    name);
    fd.append('email',   email);
    fd.append('company', company);
    fd.append('website', website);
    fd.append('message', message);

    var logoInput = document.getElementById('spm-logo-input');
    if (logoInput && logoInput.files.length > 0) {
      fd.append('logo',     logoInput.files[0]);
      fd.append('offset_x', (logoOffset.x / CANVAS_R * 100).toFixed(2));
      fd.append('offset_y', (logoOffset.y / CANVAS_R * 100).toFixed(2));
      fd.append('scale',    logoScale.toFixed(3));
    }

    if (btn) { btn.disabled = true; btn.textContent = 'Sending…'; }

    fetch('/sponsors/cell/' + cell.id + '/enquire/', {
      method:  'POST',
      headers: { 'X-CSRFToken': getCsrf() },
      body:    fd,
    })
    .then(function (r) {
      return r.json().then(function (d) { return { ok: r.ok, data: d }; });
    })
    .then(function (res) {
      if (res.ok && res.data.ok) {
        if (form) { form.hidden = true; }
        if (sucEl) {
          sucEl.innerHTML = '<strong>Enquiry submitted!</strong> Bearcave Ltd. will be in touch within 24 hours to arrange your annual contract.';
          sucEl.hidden = false;
        }
      } else {
        showErr(errEl, res.data.error || 'Something went wrong. Please try again.');
        if (btn) { btn.disabled = false; btn.textContent = 'Reserve this spot'; }
      }
    })
    .catch(function () {
      showErr(errEl, 'Network error. Please check your connection and try again.');
      if (btn) { btn.disabled = false; btn.textContent = 'Reserve this spot'; }
    });
  }

  function val(id) {
    var el = document.getElementById(id);
    return el ? el.value.trim() : '';
  }

  function showErr(el, msg) {
    if (el) { el.textContent = msg; el.hidden = false; }
  }

  /* ------------------------------------------------------------------ */
  /* Admin panel                                                         */
  /* ------------------------------------------------------------------ */
  function loadAdminPanel(cellId) {
    fetch('/sponsors/cell/' + cellId + '/', {
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
    })
    .then(function (r) { return r.json(); })
    .then(function (data) { renderAdminPanel(data); })
    .catch(function () { /* silent — admin panel is optional enhancement */ });
  }

  function renderAdminPanel(data) {
    var panel = document.getElementById('spm-admin-panel');
    if (!panel) { return; }

    var html = '<div class="spm-admin">';
    html += '<div class="spm-admin-title">Admin moderation</div>';

    if (data.enquiry_submitted_at) {
      html += '<div class="spm-admin-enquiry">';
      html += row('From',      esc(data.enquiry_name) + ' &lt;' + esc(data.enquiry_email) + '&gt;');
      if (data.enquiry_company) { html += row('Company', esc(data.enquiry_company)); }
      if (data.enquiry_website) {
        html += '<div class="spm-admin-row"><span class="spm-admin-lbl">Website</span>' +
          '<a href="' + esc(data.enquiry_website) + '" target="_blank">' + esc(data.enquiry_website) + '</a></div>';
      }
      if (data.enquiry_message) { html += row('Message', esc(data.enquiry_message)); }
      html += row('Submitted', fmtDate(data.enquiry_submitted_at));
      html += '</div>';
    } else {
      html += '<p class="spm-admin-empty">No enquiry submitted yet.</p>';
    }

    if (data.logo_pending) {
      html += '<div class="spm-admin-pending-logo">';
      html += '<span class="spm-admin-lbl">Pending logo</span>';
      html += '<img src="' + esc(data.logo_pending) + '" alt="Pending logo" class="spm-admin-logo-img">';
      html += '</div>';
    }

    if (data.status === 'reserved' || data.logo_pending) {
      html += '<div class="spm-admin-btns">';
      html += '<button class="spm-admin-approve" data-id="' + data.id + '">Approve &amp; publish</button>';
      html += '<button class="spm-admin-reject"  data-id="' + data.id + '">Reject &amp; reset</button>';
      html += '</div>';
    }

    html += '</div>';
    panel.innerHTML = html;
    panel.hidden    = false;

    var appBtn = panel.querySelector('.spm-admin-approve');
    var rejBtn = panel.querySelector('.spm-admin-reject');
    if (appBtn) { appBtn.addEventListener('click', function () { moderateCell(data.id, 'approve'); }); }
    if (rejBtn) { rejBtn.addEventListener('click', function () { moderateCell(data.id, 'reject');  }); }
  }

  function row(label, value) {
    return '<div class="spm-admin-row"><span class="spm-admin-lbl">' + label + '</span><span>' + value + '</span></div>';
  }

  function moderateCell(cellId, action) {
    var fd = new FormData();
    fd.append('action', action);

    fetch('/sponsors/cell/' + cellId + '/moderate/', {
      method:  'POST',
      headers: { 'X-CSRFToken': getCsrf() },
      body:    fd,
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.ok) {
        var panel = document.getElementById('spm-admin-panel');
        if (panel) {
          var msg = action === 'approve' ? 'Approved and published.' : 'Rejected — spot reset to available.';
          panel.innerHTML = '<div class="spm-admin"><p class="spm-admin-done">' + msg + '</p></div>';
        }
        // Reload to refresh puzzle state
        setTimeout(function () { location.reload(); }, 1400);
      }
    })
    .catch(function () {
      alert('Action failed. Please refresh the page and try again.');
    });
  }

  /* ------------------------------------------------------------------ */
  /* Helpers                                                             */
  /* ------------------------------------------------------------------ */
  function getCsrf() {
    var m = document.cookie.match(/csrftoken=([^;]+)/);
    return m ? m[1] : '';
  }

  function esc(str) {
    if (!str) { return ''; }
    return String(str)
      .replace(/&/g,  '&amp;')
      .replace(/</g,  '&lt;')
      .replace(/>/g,  '&gt;')
      .replace(/"/g,  '&quot;');
  }

  function fmtDate(iso) {
    if (!iso) { return ''; }
    try { return new Date(iso).toLocaleString(); } catch (e) { return iso; }
  }

  function ringPrice(ring) {
    var p = { 1: '€800/yr', 2: '€400/yr', 3: '€200/yr', 4: '€100/yr', 5: '€50/yr', 6: '€25/yr' };
    return p[ring] || '€25/yr';
  }

  function ringLabelClass(ring, status) {
    if (ring === 0)            { return 'spm-ring-label--centre'; }
    if (status === 'sold')     { return 'spm-ring-label--sold'; }
    if (status === 'reserved') { return 'spm-ring-label--reserved'; }
    return '';
  }

  function statusText(status) {
    return { available: 'Available', reserved: 'Reserved', sold: 'Sold' }[status] || status;
  }

  /* ------------------------------------------------------------------ */
  /* Export                                                              */
  /* ------------------------------------------------------------------ */
  window.SponsorModal = { open: openModal, close: closeModal };

}());
