/**
 * recipe_format.js
 *
 * Vanilla JS panel for the Recipe Formatting Tools section on the recipe authoring form.
 *
 * Buttons:
 *   Clean Recipe Text        — POST to recipe_format_suggest, updates a staging area
 *   Preview Recipe Structure — POST to recipe_format_preview, renders HTML preview
 *   Apply Cleaned Text       — copies cleaned fields into the live form textareas
 *
 * URLs read from data-suggest-url / data-preview-url on the panel element.
 * CSRF token read from form's [name=csrfmiddlewaretoken].
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

  function getFieldValue(id) {
    var el = document.getElementById(id);
    return el ? el.value : '';
  }

  function setFieldValue(id, val) {
    var el = document.getElementById(id);
    if (el) {
      el.value = val;
      el.dispatchEvent(new Event('input'));
    }
  }

  function init() {
    var panel = document.getElementById('recipe-format-panel');
    if (!panel) return;

    var suggestUrl  = panel.dataset.suggestUrl;
    var previewUrl  = panel.dataset.previewUrl;

    var previewPane = document.getElementById('rf-preview-pane');
    var previewInner= document.getElementById('rf-preview-inner');
    var cleanBtn    = document.getElementById('rf-clean-btn');
    var previewBtn  = document.getElementById('rf-preview-btn');
    var sanitizeBtn = document.getElementById('rf-sanitize-btn');
    var applyBtn    = document.getElementById('rf-apply-btn');
    var statusEl    = document.getElementById('rf-status');

    // Staged (cleaned) field values
    var staged = null;

    function collectFields() {
      return {
        title:               getFieldValue('id_title'),
        short_description:   getFieldValue('id_short_description'),
        ingredients:         getFieldValue('id_ingredients'),
        method:              getFieldValue('id_method'),
        tips:                getFieldValue('id_tips'),
        irish_context:       getFieldValue('id_irish_context'),
        author_commentary:   getFieldValue('id_author_commentary'),
        prep_time_minutes:   getFieldValue('id_prep_time_minutes'),
        cook_time_minutes:   getFieldValue('id_cook_time_minutes'),
        servings:            getFieldValue('id_servings'),
        difficulty:          getFieldValue('id_difficulty'),
      };
    }

    // ── Clean Recipe Text ───────────────────────────────────────────────────
    if (cleanBtn) {
      cleanBtn.addEventListener('click', function () {
        setStatus(statusEl, 'Cleaning...', false);
        cleanBtn.disabled = true;

        var csrf = getCsrf();
        postJson(suggestUrl, collectFields(), csrf)
          .then(function (r) { return r.json(); })
          .then(function (data) {
            staged = data;
            if (applyBtn) applyBtn.hidden = false;
            if (previewPane) previewPane.hidden = true;
            setStatus(statusEl, 'Text cleaned. Click Apply to use it, or Preview to review.', false);
          })
          .catch(function () {
            setStatus(statusEl, 'Request failed. Please try again.', true);
          })
          .finally(function () {
            cleanBtn.disabled = false;
          });
      });
    }

    // ── Preview Recipe Structure ────────────────────────────────────────────
    if (previewBtn) {
      previewBtn.addEventListener('click', function () {
        var payload = staged ? Object.assign({}, collectFields(), staged) : collectFields();
        setStatus(statusEl, 'Rendering preview...', false);
        previewBtn.disabled = true;

        var csrf = getCsrf();
        postJson(previewUrl, payload, csrf)
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

    // ── Apply Cleaned Text ──────────────────────────────────────────────────
    if (applyBtn) {
      applyBtn.addEventListener('click', function () {
        if (!staged) return;
        var fields = ['ingredients', 'method', 'tips', 'irish_context', 'author_commentary'];
        fields.forEach(function (key) {
          if (staged[key] !== undefined) {
            setFieldValue('id_' + key, staged[key]);
          }
        });
        if (previewPane) previewPane.hidden = true;
        applyBtn.hidden = true;
        staged = null;
        setStatus(statusEl, 'Applied. Review the fields above before submitting.', false);
      });
    }

    // ── Sanitize Text ───────────────────────────────────────────────────────
    function sanitiseText(text) {
      if (!text) return text;
      text = text.replace(/—/g, ', ').replace(/–/g, ', '); // em dash, en dash
      text = text.replace(/-{2,}/g, ', ');                            // double/multiple dashes
      text = text.replace(/,\s*,+/g, ',');                            // consecutive commas
      text = text.replace(/,\s{2,}/g, ', ');                         // comma + extra spaces
      text = text.replace(/^[\s,]+|[\s,]+$/g, '');                   // leading/trailing
      // Strip trailing colons from each line (AI often adds "ingredient:" headers)
      text = text.split('\n').map(function(line) {
        return line.replace(/\s*:\s*$/, '');
      }).join('\n');
      return text;
    }

    if (sanitizeBtn) {
      sanitizeBtn.addEventListener('click', function () {
        var fields = ['short_description', 'ingredients', 'method', 'tips', 'irish_context', 'author_commentary'];
        var changed = 0;
        fields.forEach(function (key) {
          var el = document.getElementById('id_' + key);
          if (!el) return;
          var before = el.value;
          var after  = sanitiseText(before);
          if (after !== before) {
            el.value = after;
            el.dispatchEvent(new Event('input'));
            changed++;
          }
        });
        setStatus(statusEl, changed > 0 ? 'Sanitized ' + changed + ' field(s). Review before saving.' : 'Nothing to sanitize.', false);
      });
    }

    // ── Auto-clean on edit page load ────────────────────────────────────────
    if (panel.dataset.autoClean === 'true' && cleanBtn) {
      setStatus(statusEl, 'Auto-cleaning on load...', false);
      cleanBtn.disabled = true;

      postJson(suggestUrl, collectFields(), getCsrf())
        .then(function (r) { return r.json(); })
        .then(function (data) {
          staged = data;
          if (applyBtn) applyBtn.hidden = false;
          if (previewPane) previewPane.hidden = true;
          setStatus(statusEl, 'Text cleaned automatically. Click Apply to use it, or Preview to review.', false);
        })
        .catch(function () {
          setStatus(statusEl, 'Auto-clean failed. Use the button to retry.', true);
        })
        .finally(function () {
          cleanBtn.disabled = false;
        });
    }

    // ── Auto-sanitize on form submit (create mode) ──────────────────────────
    // In edit mode the moderator already applied AI-clean.
    // In create mode the author may not have clicked Sanitize, so we run it
    // silently on submit to strip em-dashes, trailing colons, etc.
    if (panel.dataset.autoClean !== 'true') {
      var form = panel.closest('form');
      if (form) {
        form.addEventListener('submit', function () {
          var fields = ['short_description', 'ingredients', 'method', 'tips', 'irish_context', 'author_commentary'];
          fields.forEach(function (key) {
            var el = document.getElementById('id_' + key);
            if (!el) return;
            var after = sanitiseText(el.value);
            if (after !== el.value) {
              el.value = after;
            }
          });
        });
      }
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
