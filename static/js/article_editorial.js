/**
 * article_editorial.js
 *
 * Vanilla JS panel for the Editorial Tools section on the article authoring form.
 *
 * Buttons:
 *   Suggest Format  — POST to editorial_suggest, populates a staging textarea
 *   Preview         — POST to editorial_preview, renders HTML in the preview pane
 *   Apply           — copies the suggested/staged text into the main body textarea
 *
 * URLs are read from data-suggest-url / data-preview-url on the panel element.
 * CSRF token is read from the form's [name=csrfmiddlewaretoken] input.
 */
(function () {
  'use strict';

  function getCsrf() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  function postJson(url, payload, csrf) {
    return fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf,
      },
      body: JSON.stringify(payload),
    });
  }

  function setStatus(el, msg, isError) {
    if (!el) return;
    el.textContent = msg;
    el.className = 'editorial-tools__status' + (isError ? ' editorial-tools__status--error' : '');
  }

  function init() {
    var panel = document.getElementById('editorial-tools-panel');
    if (!panel) return;

    var suggestUrl  = panel.dataset.suggestUrl;
    var previewUrl  = panel.dataset.previewUrl;

    var bodyTa      = document.getElementById('id_body');
    var stagingTa   = document.getElementById('et-staging');
    var previewPane = document.getElementById('et-preview-pane');
    var previewInner= document.getElementById('et-preview-inner');
    var suggestBtn  = document.getElementById('et-suggest-btn');
    var previewBtn  = document.getElementById('et-preview-btn');
    var applyBtn    = document.getElementById('et-apply-btn');
    var statusEl    = document.getElementById('et-status');

    if (!bodyTa) return;

    // Track staging text (suggested body)
    var stagedBody = '';

    // ── Suggest Format ──────────────────────────────────────────────────────
    if (suggestBtn) {
      suggestBtn.addEventListener('click', function () {
        var titleEl   = document.getElementById('id_title');
        var excerptEl = document.getElementById('id_excerpt');
        setStatus(statusEl, 'Analysing...', false);
        suggestBtn.disabled = true;

        var csrf = getCsrf();
        postJson(suggestUrl, {
          title:   titleEl   ? titleEl.value   : '',
          excerpt: excerptEl ? excerptEl.value : '',
          body:    bodyTa.value,
        }, csrf)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            stagedBody = data.suggested_body || '';
            if (stagingTa) {
              stagingTa.value = stagedBody;
            }
            if (applyBtn) {
              applyBtn.hidden = false;
            }
            if (previewPane) previewPane.hidden = true;
            setStatus(statusEl,
              'Suggestion ready. Click Apply to use it, or Preview to review.',
              false);
          })
          .catch(function () {
            setStatus(statusEl, 'Request failed. Please try again.', true);
          })
          .finally(function () {
            suggestBtn.disabled = false;
          });
      });
    }

    // ── Preview ─────────────────────────────────────────────────────────────
    if (previewBtn) {
      previewBtn.addEventListener('click', function () {
        var body = stagingTa && stagingTa.value ? stagingTa.value : bodyTa.value;
        setStatus(statusEl, 'Rendering preview...', false);
        previewBtn.disabled = true;

        var csrf = getCsrf();
        postJson(previewUrl, { body: body }, csrf)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (previewInner) {
              previewInner.innerHTML = data.preview_html || '';
            }
            if (previewPane) previewPane.hidden = false;
            setStatus(statusEl, '', false);
          })
          .catch(function () {
            setStatus(statusEl, 'Preview failed. Please try again.', true);
          })
          .finally(function () {
            previewBtn.disabled = false;
          });
      });
    }

    // ── Apply ────────────────────────────────────────────────────────────────
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        var text = (stagingTa && stagingTa.value) ? stagingTa.value : stagedBody;
        if (!text) return;
        bodyTa.value = text;
        // Trigger autogrow if in use
        bodyTa.dispatchEvent(new Event('input'));
        if (previewPane) previewPane.hidden = true;
        if (stagingTa) stagingTa.value = '';
        applyBtn.hidden = true;
        stagedBody = '';
        setStatus(statusEl, 'Applied. Review the body field above before submitting.', false);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
