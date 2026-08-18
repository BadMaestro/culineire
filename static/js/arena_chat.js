/**
 * The spectator chat in the arena stands.
 *
 * The Owner's rules, 2026-08-17. One room for spectators and chefs. A spectator
 * hears three cells either side of his own, and three rows by the compass -- not
 * a game mechanic and not a penalty, but how hearing works, reproduced. A chef
 * is outside that in both directions because he cannot get up and move closer.
 * The chat keeps everything written from the start of a battle to its end.
 *
 * WHO HEARS WHAT IS NOT DECIDED HERE. The server sends a line's words only to
 * people close enough to hear them; everyone else receives the line WITHOUT a
 * body and this file draws "Talking Something" in its place. Shipping the text
 * and hiding it in CSS would leave it one view-source away from someone the
 * rule says must not read it.
 *
 * Behaviour carried over from the Owner's own local chat on port 8799, which he
 * asked to reuse: paint once and then fetch only what is new by id, so a quiet
 * hall costs an empty array rather than a re-render of the whole conversation;
 * Enter sends; a dropped request puts the text back in the box instead of
 * losing it; and the log only sticks to the bottom if the reader was already
 * there, so reading back through the evening is not yanked away.
 */
(function () {
  'use strict';

  var root = document.getElementById('arena-chat');
  if (!root) { return; }

  var log = document.getElementById('arena-chat-log');
  var empty = document.getElementById('arena-chat-empty');
  var form = document.getElementById('arena-chat-form');
  var input = document.getElementById('arena-chat-input');
  var live = document.getElementById('arena-chat-live');
  var feedUrl = root.getAttribute('data-feed-url');
  var sendUrl = root.getAttribute('data-send-url');

  var lastId = 0;
  var busy = false;
  var POLL_MS = 4000;

  function csrf() {
    var field = form && form.querySelector('[name=csrfmiddlewaretoken]');
    return field ? field.value : '';
  }

  function nearBottom() {
    return log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  }

  function append(line) {
    var item = document.createElement('li');
    item.className = 'arena-chat__line' + (line.heard ? '' : ' arena-chat__line--distant');
    item.setAttribute('data-id', line.id);

    var who = document.createElement('span');
    who.className = 'arena-chat__who';
    who.textContent = line.name;

    var said = document.createElement('span');
    if (line.heard) {
      said.className = 'arena-chat__said';
      said.textContent = line.body;
    } else {
      // Out of earshot. The person is visibly talking and that is all anyone
      // this far away is entitled to know.
      said.className = 'arena-chat__said arena-chat__said--muffled';
      said.textContent = 'Talking Something';
    }

    item.appendChild(who);
    item.appendChild(said);
    log.appendChild(item);
    if (line.id > lastId) { lastId = line.id; }
  }

  function absorb(lines) {
    if (!lines || !lines.length) { return; }
    var stick = nearBottom();
    if (empty && empty.parentNode) { empty.remove(); }
    lines.forEach(append);
    if (stick) { log.scrollTop = log.scrollHeight; }
  }

  function seatMe(seated) {
    if (form) { form.hidden = !seated; }
    if (live) { live.hidden = !seated; }
    // The placeholder has to agree with the badge beside it. It shipped saying
    // "Take a seat to join the conversation" to EVERYONE, so a chef - who holds
    // a place in the octagon and needs no seat - read an instruction he could
    // not follow, next to a LIVE badge saying he was already in the room.
    if (empty && empty.parentNode) {
      empty.textContent = seated
        ? 'Nobody has spoken yet.'
        : 'Take a seat to join the conversation.';
    }
  }

  function poll() {
    if (busy) { return; }
    busy = true;
    fetch(feedUrl + '?since=' + encodeURIComponent(lastId), {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        seatMe(!!data.seated);
        absorb(data.messages);
      })
      .catch(function () { /* one dropped tick is not a failure; try the next */ })
      .then(function () { busy = false; });
  }

  function send() {
    var text = input.value.trim();
    if (!text) { return; }
    var body = new FormData();
    body.append('body', text);
    body.append('csrfmiddlewaretoken', csrf());
    input.value = '';
    input.focus();
    fetch(sendUrl, { method: 'POST', credentials: 'same-origin', body: body })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ok) { absorb(data.messages); } else { input.value = text; }
      })
      .catch(function () { input.value = text; });   // put it back, lose nothing
  }

  if (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      send();
    });
  }

  poll();
  setInterval(poll, POLL_MS);
})();
