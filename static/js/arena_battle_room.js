/*
 * Battle room popup + battle blast.
 *
 * Ported from arena_puzzle.js so both survive the legacy renderer's removal.
 * The popup embeds the server-rendered battle room fragment and drives its
 * chat; the blast celebrates a finished battle for everyone watching the
 * arena, not only the two participants.
 */
(function (global) {
  'use strict';

  var CHAT_POLL_INTERVAL = 10000;

  var chatTimer = null;
  // null = not yet initialised from the page's own data. Only a *change* after
  // that first snapshot is a fresh result worth celebrating, so a reload never
  // replays the last battle's blast.
  var lastSeenResultId = null;

  function byId(id) { return document.getElementById(id); }

  function csrfToken() {
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    return match ? match[1] : '';
  }

  /* ---- popup ---- */

  function setLoading(inner, text) {
    inner.textContent = '';
    var note = document.createElement('p');
    note.className = 'arena-popup__loading';
    note.textContent = text;
    inner.appendChild(note);
  }

  function open(popupUrl, battleUrl) {
    var popup = byId('arena-battle-popup');
    var inner = byId('arena-popup-inner');
    if (!popup || !inner) {
      if (battleUrl) { global.location.href = battleUrl; }
      return;
    }
    setLoading(inner, 'Loading battle...');
    popup.hidden = false;
    document.body.style.overflow = 'hidden';

    fetch(popupUrl, { credentials: 'same-origin' })
      .then(function (response) { return response.ok ? response.text() : null; })
      .then(function (html) {
        if (!html) {
          setLoading(inner, 'No active battle right now.');
          return;
        }
        // Server-rendered fragment from our own view.
        inner.innerHTML = html;
        initChat(inner);
      })
      .catch(function () {
        setLoading(inner, 'Could not load battle.');
        if (battleUrl) {
          var link = document.createElement('a');
          link.href = battleUrl;
          link.textContent = 'Open full room';
          inner.querySelector('.arena-popup__loading').appendChild(link);
        }
      });
  }

  function close() {
    var popup = byId('arena-battle-popup');
    if (popup) { popup.hidden = true; }
    document.body.style.overflow = '';
    if (chatTimer) {
      global.clearInterval(chatTimer);
      chatTimer = null;
    }
  }

  /* ---- popup chat ---- */

  function appendMessage(box, message) {
    var row = document.createElement('div');
    var who = document.createElement('b');
    var body = document.createElement('span');
    var time = document.createElement('span');
    row.className = 'abp__chat-msg';
    row.setAttribute('data-id', message.id);
    who.className = 'abp__chat-who';
    body.className = 'abp__chat-body';
    time.className = 'abp__chat-time';
    // textContent, not innerHTML: chat bodies are user input.
    who.textContent = message.display_name;
    body.textContent = message.body;
    time.textContent = message.created_at;
    row.appendChild(who);
    row.appendChild(body);
    row.appendChild(time);
    box.appendChild(row);
  }

  function initChat(container) {
    var form = container.querySelector('#abp-chat-form');
    var box = container.querySelector('#abp-chat-messages');
    if (!form || !box) { return; }

    var pollUrl = form.getAttribute('data-poll-url');
    var sendUrl = form.getAttribute('data-url');
    var lastId = 0;
    Array.prototype.forEach.call(box.querySelectorAll('[data-id]'), function (node) {
      var id = parseInt(node.getAttribute('data-id'), 10);
      if (id > lastId) { lastId = id; }
    });
    box.scrollTop = box.scrollHeight;

    function pollChat() {
      if (!pollUrl) { return; }
      fetch(pollUrl + '?since=' + lastId, { credentials: 'same-origin' })
        .then(function (response) { return response.ok ? response.json() : null; })
        .then(function (data) {
          if (!data || !data.messages || !data.messages.length) { return; }
          var empty = box.querySelector('.abp__chat-empty');
          if (empty) { empty.remove(); }
          data.messages.forEach(function (message) {
            appendMessage(box, message);
            if (message.id > lastId) { lastId = message.id; }
          });
          box.scrollTop = box.scrollHeight;
        })
        .catch(function () {});
    }

    pollChat();
    chatTimer = global.setInterval(pollChat, CHAT_POLL_INTERVAL);

    form.addEventListener('submit', function (event) {
      event.preventDefault();
      var input = form.querySelector('input[name="body"]');
      if (!input || !input.value.trim()) { return; }
      fetch(sendUrl, {
        method: 'POST',
        body: new FormData(form),
        credentials: 'same-origin',
        headers: { 'X-CSRFToken': csrfToken() }
      }).then(function () {
        input.value = '';
        global.setTimeout(pollChat, 400);
      }).catch(function () {});
    });
  }

  /* ---- battle blast ---- */

  function fireBlast(result) {
    var blast = byId('battle-blast');
    if (!blast || !result) { return; }
    var badge = byId('blast-badge');
    var winner = byId('blast-winner');
    var score = byId('blast-score');
    if (badge) { badge.textContent = 'Battle Complete'; }
    if (winner) { winner.textContent = result.winner_name + ' Wins!'; }
    if (score) { score.textContent = result.result_reason || result.theme || ''; }

    blast.hidden = false;
    // Force layout so the entrance transition actually plays.
    void blast.offsetWidth;
    blast.classList.add('is-active');
  }

  function dismissBlast() {
    var blast = byId('battle-blast');
    if (!blast) { return; }
    blast.classList.remove('is-active');
    global.setTimeout(function () { blast.hidden = true; }, 350);
  }

  function maybeCelebrate(latestResult) {
    if (!latestResult) { return; }
    if (lastSeenResultId !== null && latestResult.battle_id !== lastSeenResultId) {
      fireBlast(latestResult);
    }
    lastSeenResultId = latestResult.battle_id;
  }

  /* ---- wiring ---- */

  function init(initialResult) {
    lastSeenResultId = initialResult ? initialResult.battle_id : null;

    var dismiss = byId('blast-dismiss');
    if (dismiss) { dismiss.addEventListener('click', dismissBlast); }

    var closeBtn = byId('arena-popup-close');
    var backdrop = byId('arena-popup-backdrop');
    if (closeBtn) { closeBtn.addEventListener('click', close); }
    if (backdrop) { backdrop.addEventListener('click', close); }
    document.addEventListener('keydown', function (event) {
      if (event.key === 'Escape') { close(); }
    });
  }

  global.ArenaBattleRoom = {
    init: init,
    open: open,
    close: close,
    maybeCelebrate: maybeCelebrate
  };
})(window);
