(function () {
  "use strict";

  var DRAFT_PREFIX = "culineire:form-autosave:v1:";
  var PENDING_CLEAR_KEY = "culineire:form-autosave:pending-clear:v1";
  var PENDING_TTL = 30 * 60 * 1000;
  var SAVE_DELAY = 350;
  var EXCLUDED_TYPES = {
    button: true,
    file: true,
    hidden: true,
    image: true,
    password: true,
    reset: true,
    submit: true,
  };
  var SENSITIVE_FIELD_RE = /(csrf|password|passwd|token|secret|otp|one[-_]?time|credit[-_ ]?card|card[-_ ]?(number|holder|expiry|exp)|cvc|cvv|iban|payment|stripe|turnstile)/i;

  function storageAvailable(storage) {
    try {
      var testKey = "__autosave_test__";
      storage.setItem(testKey, "1");
      storage.removeItem(testKey);
      return true;
    } catch (error) {
      return false;
    }
  }

  var canUseLocalStorage = storageAvailable(window.localStorage);
  var canUseSessionStorage = storageAvailable(window.sessionStorage);

  if (!canUseLocalStorage) {
    return;
  }

  function readJson(storage, key, fallback) {
    try {
      var raw = storage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (error) {
      return fallback;
    }
  }

  function writeJson(storage, key, value) {
    try {
      storage.setItem(key, JSON.stringify(value));
      return true;
    } catch (error) {
      return false;
    }
  }

  function getDraftKey(form, index) {
    var explicitKey = form.getAttribute("data-autosave-key");
    var key = explicitKey || [
      window.location.pathname,
      form.getAttribute("action") || window.location.pathname,
      String(index),
    ].join("|");
    return DRAFT_PREFIX + key;
  }

  function isSensitiveField(field) {
    var name = field.name || "";
    var id = field.id || "";
    var autocomplete = field.getAttribute("autocomplete") || "";
    return SENSITIVE_FIELD_RE.test(name) || SENSITIVE_FIELD_RE.test(id) || SENSITIVE_FIELD_RE.test(autocomplete);
  }

  function isSavableField(field) {
    if (!field || !field.name || field.disabled) return false;
    if (field.closest("[data-autosave-exclude]")) return false;
    if (field.getAttribute("data-autosave") === "exclude") return false;
    if (isSensitiveField(field)) return false;

    var type = (field.getAttribute("type") || field.type || "").toLowerCase();
    if (EXCLUDED_TYPES[type]) return false;

    return true;
  }

  function getSavableFields(form) {
    return Array.prototype.filter.call(
      form.querySelectorAll("input, select, textarea"),
      isSavableField,
    );
  }

  function serializeForm(form) {
    return {
      version: 1,
      updatedAt: Date.now(),
      path: window.location.pathname,
      fields: getSavableFields(form).map(function (field) {
        var tagName = field.tagName.toLowerCase();
        var type = (field.getAttribute("type") || field.type || tagName).toLowerCase();

        if (type === "checkbox" || type === "radio") {
          return {
            name: field.name,
            type: type,
            value: field.value,
            checked: field.checked,
          };
        }

        if (tagName === "select" && field.multiple) {
          return {
            name: field.name,
            type: "select-multiple",
            value: Array.prototype.map.call(field.selectedOptions, function (option) {
              return option.value;
            }),
          };
        }

        return {
          name: field.name,
          type: tagName === "select" ? "select" : type,
          value: field.value,
        };
      }),
    };
  }

  function groupRecordsByName(draft) {
    return (draft.fields || []).reduce(function (groups, record) {
      if (!record || !record.name) return groups;
      if (!groups[record.name]) groups[record.name] = [];
      groups[record.name].push(record);
      return groups;
    }, {});
  }

  function fieldValueMatchesRecord(field, records) {
    var tagName = field.tagName.toLowerCase();
    var type = (field.getAttribute("type") || field.type || tagName).toLowerCase();

    if (type === "checkbox" || type === "radio") {
      var matched = records.find(function (record) {
        return record.value === field.value;
      }) || records[0];
      return Boolean(matched) && field.checked === Boolean(matched.checked);
    }

    if (tagName === "select" && field.multiple) {
      var selected = Array.prototype.map.call(field.selectedOptions, function (option) {
        return option.value;
      });
      var expected = records[0] && Array.isArray(records[0].value) ? records[0].value : [];
      return selected.length === expected.length && selected.every(function (value) {
        return expected.indexOf(value) !== -1;
      });
    }

    return Boolean(records[0]) && field.value === String(records[0].value || "");
  }

  function draftDiffersFromCurrent(form, draft) {
    if (!draft || !Array.isArray(draft.fields) || !draft.fields.length) return false;
    var recordsByName = groupRecordsByName(draft);
    return getSavableFields(form).some(function (field) {
      var records = recordsByName[field.name] || [];
      return records.length > 0 && !fieldValueMatchesRecord(field, records);
    });
  }

  function formHasServerErrors(form) {
    return Boolean(form.querySelector(".authoring-errors, .authoring-error, .errorlist, [aria-invalid='true']"));
  }

  function shouldPromptForDraft(form, draft) {
    if (!draft || !Array.isArray(draft.fields) || !draft.fields.length) return false;
    return !formHasServerErrors(form) || draftDiffersFromCurrent(form, draft);
  }

  function dispatchFieldEvents(field) {
    field.dispatchEvent(new Event("input", { bubbles: true }));
    field.dispatchEvent(new Event("change", { bubbles: true }));
  }

  function restoreDraft(form, draft) {
    var recordsByName = groupRecordsByName(draft);

    getSavableFields(form).forEach(function (field) {
      var records = recordsByName[field.name] || [];
      if (!records.length) return;

      var tagName = field.tagName.toLowerCase();
      var type = (field.getAttribute("type") || field.type || tagName).toLowerCase();

      if (type === "checkbox" || type === "radio") {
        var matched = records.find(function (record) {
          return record.value === field.value;
        }) || records[0];
        field.checked = Boolean(matched.checked);
        dispatchFieldEvents(field);
        return;
      }

      if (tagName === "select" && field.multiple) {
        var selectedValues = records[0] && Array.isArray(records[0].value) ? records[0].value : [];
        Array.prototype.forEach.call(field.options, function (option) {
          option.selected = selectedValues.indexOf(option.value) !== -1;
        });
        dispatchFieldEvents(field);
        return;
      }

      field.value = String(records[0].value || "");
      dispatchFieldEvents(field);
    });
  }

  function formatSavedTime(timestamp) {
    if (!timestamp) return "Saved recently";
    try {
      return "Saved " + new Date(timestamp).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      });
    } catch (error) {
      return "Saved recently";
    }
  }

  function showRestorePrompt(form, draft, draftKey) {
    if (form.querySelector(".autosave-prompt")) return;

    var prompt = document.createElement("div");
    prompt.className = "autosave-prompt";
    prompt.setAttribute("role", "status");
    prompt.innerHTML =
      '<div class="autosave-prompt__copy">' +
      '<strong>Unsaved draft found</strong>' +
      '<span>' + formatSavedTime(draft.updatedAt) + ". Restore it or discard it.</span>" +
      "</div>" +
      '<div class="autosave-prompt__actions">' +
      '<button class="autosave-prompt__button autosave-prompt__button--primary" type="button" data-autosave-restore>Restore</button>' +
      '<button class="autosave-prompt__button" type="button" data-autosave-discard>Discard</button>' +
      "</div>";

    prompt.querySelector("[data-autosave-restore]").addEventListener("click", function () {
      restoreDraft(form, draft);
      prompt.remove();
    });

    prompt.querySelector("[data-autosave-discard]").addEventListener("click", function () {
      window.localStorage.removeItem(draftKey);
      prompt.remove();
    });

    form.insertBefore(prompt, form.firstChild);
  }

  function getPendingClears() {
    if (!canUseSessionStorage) return [];
    var pending = readJson(window.sessionStorage, PENDING_CLEAR_KEY, []);
    return Array.isArray(pending) ? pending : [];
  }

  function setPendingClears(pending) {
    if (!canUseSessionStorage) return;
    writeJson(window.sessionStorage, PENDING_CLEAR_KEY, pending);
  }

  function addPendingClear(draftKey) {
    if (!canUseSessionStorage) return;
    var now = Date.now();
    var pending = getPendingClears().filter(function (item) {
      return item && item.key !== draftKey && now - Number(item.createdAt || 0) < PENDING_TTL;
    });
    pending.push({ key: draftKey, createdAt: now });
    setPendingClears(pending);
  }

  function processPendingClears(activeDraftKeys) {
    if (!canUseSessionStorage) return;

    var now = Date.now();
    var remaining = [];

    getPendingClears().forEach(function (item) {
      if (!item || !item.key) return;
      if (now - Number(item.createdAt || 0) >= PENDING_TTL) return;
      if (activeDraftKeys.indexOf(item.key) !== -1) return;
      window.localStorage.removeItem(item.key);
    });

    setPendingClears(remaining);
  }

  function initAutosaveForm(form, index) {
    var draftKey = getDraftKey(form, index);
    var saveTimer = null;

    function saveNow() {
      saveTimer = null;
      writeJson(window.localStorage, draftKey, serializeForm(form));
    }

    function scheduleSave() {
      window.clearTimeout(saveTimer);
      saveTimer = window.setTimeout(saveNow, SAVE_DELAY);
    }

    form.addEventListener("input", function (event) {
      if (isSavableField(event.target)) scheduleSave();
    });
    form.addEventListener("change", function (event) {
      if (isSavableField(event.target)) scheduleSave();
    });
    form.addEventListener("submit", function () {
      if (saveTimer) {
        window.clearTimeout(saveTimer);
      }
      saveNow();
      addPendingClear(draftKey);
    });
    window.addEventListener("beforeunload", function () {
      if (saveTimer) saveNow();
    });

    var draft = readJson(window.localStorage, draftKey, null);
    if (shouldPromptForDraft(form, draft)) {
      showRestorePrompt(form, draft, draftKey);
    }

    return draftKey;
  }

  function init() {
    var forms = Array.prototype.slice.call(document.querySelectorAll('form[data-autosave="true"]'));
    var activeDraftKeys = forms.map(initAutosaveForm);
    processPendingClears(activeDraftKeys);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
}());
