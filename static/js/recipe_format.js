/**
 * recipe_format.js
 *
 * Flow:
 *   1. Preview Recipe Structure — renders current fields as HTML (always works)
 *   2. Clean Recipe Text        — POST to format_suggest, stages cleaned fields
 *   3. Sanitize Text            — client-side content safety on staged (or current) fields
 *   4. Apply Changes            — writes staged fields back into the form (top + bottom button)
 */
(function () {
  'use strict';

  // ── Content-safety word replacements ─────────────────────────────────────
  var REPLACEMENTS = [
    [/\bcrap\b/gi, 'leftovers'],
    [/\bcrappy\b/gi, 'poor-quality'],
    [/\bdamn(ed)?\b/gi, 'really'],
    [/\bhell\b/gi, 'very difficult'],
    [/\bshit\b/gi, 'scraps'],
    [/\bfuck(ing)?\b/gi, ''],
    [/\bass\b/gi, ''],
    [/\bbastard\b/gi, ''],
    [/\bbitch\b/gi, ''],
    [/\bcunt\b/gi, ''],
    [/\bwank(er)?\b/gi, ''],
    [/\bpiss\b/gi, ''],
    [/\bdick\b/gi, ''],
    [/\bcock\b/gi, 'rooster'],
  ];

  function getCsrf() {
    var el = document.querySelector('[name=csrfmiddlewaretoken]');
    return el ? el.value : '';
  }

  function postJson(url, payload, csrf) {
    return fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-CSRFToken': csrf },
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
    if (el) { el.value = val; el.dispatchEvent(new Event('input')); }
  }

  function collectFields() {
    return {
      title:             getFieldValue('id_title'),
      short_description: getFieldValue('id_short_description'),
      ingredients:       getFieldValue('id_ingredients'),
      method:            getFieldValue('id_method'),
      tips:              getFieldValue('id_tips'),
      irish_context:     getFieldValue('id_irish_context'),
      author_commentary: getFieldValue('id_author_commentary'),
      prep_time_minutes: getFieldValue('id_prep_time_minutes'),
      cook_time_minutes: getFieldValue('id_cook_time_minutes'),
      servings:          getFieldValue('id_servings'),
      difficulty:        getFieldValue('id_difficulty'),
    };
  }

  function sanitiseText(text) {
    if (!text) return text;
    // Punctuation cleanup
    text = text.replace(/—/g, ', ').replace(/–/g, ', ');
    text = text.replace(/-{2,}/g, ', ');
    text = text.replace(/,\s*,+/g, ',');
    text = text.replace(/,\s{2,}/g, ', ');
    text = text.replace(/^[\s,]+|[\s,]+$/g, '');
    text = text.split('\n').map(function (line) {
      return line.replace(/\s*:\s*$/, '');
    }).join('\n');
    // Content safety
    REPLACEMENTS.forEach(function (pair) {
      text = text.replace(pair[0], pair[1]);
    });
    // Collapse multiple spaces left by removals
    text = text.replace(/  +/g, ' ').replace(/^ | $/gm, '');
    return text;
  }

  function init() {
    var panel = document.getElementById('recipe-format-panel');
    if (!panel) return;

    var suggestUrl  = panel.dataset.suggestUrl;
    var previewUrl  = panel.dataset.previewUrl;

    var previewPane  = document.getElementById('rf-preview-pane');
    var previewInner = document.getElementById('rf-preview-inner');
    var previewBtn   = document.getElementById('rf-preview-btn');
    var cleanBtn     = document.getElementById('rf-clean-btn');
    var sanitizeBtn  = document.getElementById('rf-sanitize-btn');
    var applyBtn     = document.getElementById('rf-apply-btn');
    var applyBtn2    = document.getElementById('rf-apply-btn-2');
    var statusEl     = document.getElementById('rf-status');

    // staged holds pending changes (not yet written to form fields)
    var staged = null;

    function setApplyEnabled(enabled) {
      if (applyBtn)  applyBtn.disabled  = !enabled;
      if (applyBtn2) applyBtn2.disabled = !enabled;
    }

    function doApply() {
      if (!staged) return;
      var fields = ['ingredients', 'method', 'tips', 'irish_context', 'author_commentary', 'short_description'];
      fields.forEach(function (key) {
        if (staged[key] !== undefined) setFieldValue('id_' + key, staged[key]);
      });
      if (previewPane) previewPane.hidden = true;
      staged = null;
      setApplyEnabled(false);
      setStatus(statusEl, 'Changes applied. Review the fields above before submitting.', false);
    }

    // ── 1. Preview Recipe Structure ─────────────────────────────────────────
    if (previewBtn) {
      previewBtn.addEventListener('click', function () {
        // Preview uses staged content if available, otherwise current form fields
        var payload = staged ? Object.assign({}, collectFields(), staged) : collectFields();
        setStatus(statusEl, 'Rendering preview…', false);
        previewBtn.disabled = true;

        postJson(previewUrl, payload, getCsrf())
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (previewInner) previewInner.innerHTML = data.preview_html || '';
            if (previewPane) previewPane.hidden = false;
            setStatus(statusEl, staged ? 'Preview shows staged (unapplied) changes.' : '', false);
          })
          .catch(function () { setStatus(statusEl, 'Preview failed. Please try again.', true); })
          .finally(function () { previewBtn.disabled = false; });
      });
    }

    // ── 2. Clean Recipe Text ────────────────────────────────────────────────
    if (cleanBtn) {
      cleanBtn.addEventListener('click', function () {
        setStatus(statusEl, 'Cleaning…', false);
        cleanBtn.disabled = true;

        postJson(suggestUrl, collectFields(), getCsrf())
          .then(function (r) { return r.json(); })
          .then(function (data) {
            staged = data;
            setApplyEnabled(true);
            if (previewPane) previewPane.hidden = true;
            setStatus(statusEl, 'Text cleaned and staged. Click Apply Changes to use it, or Preview to review first.', false);
          })
          .catch(function () { setStatus(statusEl, 'Request failed. Please try again.', true); })
          .finally(function () { cleanBtn.disabled = false; });
      });
    }

    // ── 3. Sanitize Text ────────────────────────────────────────────────────
    if (sanitizeBtn) {
      sanitizeBtn.addEventListener('click', function () {
        // Sanitize works on staged fields if present, else on current form fields
        var base = staged ? Object.assign({}, collectFields(), staged) : collectFields();
        var textFields = ['short_description', 'ingredients', 'method', 'tips', 'irish_context', 'author_commentary'];
        var changed = 0;
        var patch = {};
        textFields.forEach(function (key) {
          var before = base[key] || '';
          var after  = sanitiseText(before);
          if (after !== before) { patch[key] = after; changed++; }
        });
        if (changed > 0) {
          staged = Object.assign({}, base, patch);
          setApplyEnabled(true);
          setStatus(statusEl, 'Sanitized ' + changed + ' field(s) and staged. Click Apply Changes to save.', false);
        } else {
          setStatus(statusEl, 'Nothing to sanitize.', false);
        }
      });
    }

    // ── 4. Apply Changes ────────────────────────────────────────────────────
    if (applyBtn)  applyBtn.addEventListener('click',  doApply);
    if (applyBtn2) applyBtn2.addEventListener('click', doApply);

    // ── Auto-clean on edit page load ────────────────────────────────────────
    if (panel.dataset.autoClean === 'true' && cleanBtn) {
      setStatus(statusEl, 'Auto-cleaning on load…', false);
      cleanBtn.disabled = true;

      postJson(suggestUrl, collectFields(), getCsrf())
        .then(function (r) { return r.json(); })
        .then(function (data) {
          staged = data;
          setApplyEnabled(true);
          setStatus(statusEl, 'Text cleaned automatically. Click Apply Changes to use it, or Preview to review first.', false);
        })
        .catch(function () { setStatus(statusEl, 'Auto-clean failed. Use the button to retry.', true); })
        .finally(function () { cleanBtn.disabled = false; });
    }

    // ── Auto-sanitize on form submit (create mode only) ─────────────────────
    if (panel.dataset.autoClean !== 'true') {
      var form = panel.closest('form');
      if (form) {
        form.addEventListener('submit', function () {
          var fields = ['short_description', 'ingredients', 'method', 'tips', 'irish_context', 'author_commentary'];
          fields.forEach(function (key) {
            var el = document.getElementById('id_' + key);
            if (!el) return;
            var after = sanitiseText(el.value);
            if (after !== el.value) el.value = after;
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
