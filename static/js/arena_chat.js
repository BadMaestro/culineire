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
  var reactUrl = root.getAttribute('data-react-url');
  var relationUrl = root.getAttribute('data-relation-url');
  var reportUrl = root.getAttribute('data-report-url');
  var mySlug = root.getAttribute('data-me') || '';

  var lastId = 0;
  var busy = false;
  var POLL_MS = 4000;

  /* The three the Owner named. A fixed set, not an emoji picker: a live chat
   * wants a tap, and a panel of a thousand faces is a different product. */
  var REACTIONS = [
    { key: 'fire', glyph: '🔥', label: 'Fire' },
    { key: 'clap', glyph: '👏', label: 'Clap' },
    { key: 'star', glyph: '⭐',       label: 'Star' }
  ];

  /* The line currently being answered, or null. Held here rather than read off
   * the DOM so the composer and the log cannot disagree about it. */
  var replyingTo = null;

  /* WHICH ROOM IS OPEN. null is the hall; a number is a private conversation.
   *
   * One variable, because there is one component. Switching rooms clears the
   * log and resets the delta - it does NOT build a second chat - so every
   * feature written for the hall (identity, colours, reactions, replies, mute)
   * works in a private room without being written twice. */
  var room = null;
  var roomName = '';

  function csrf() {
    var field = form && form.querySelector('[name=csrfmiddlewaretoken]');
    return field ? field.value : '';
  }

  function nearBottom() {
    return log.scrollHeight - log.scrollTop - log.clientHeight < 40;
  }

  /* One tag badge, or nothing at all.
   *
   * Nothing is the point: an absent tag must vanish, never print as "[]". The
   * brackets are drawn in CSS (::before/::after) rather than written into the
   * text, so the badge reads as `[IRL]` to a person and as `IRL` to a screen
   * reader and to anyone copying the line. */
  function tagBadge(value, kind) {
    if (!value) { return null; }
    var badge = document.createElement('span');
    badge.className = 'arena-chat__tag arena-chat__tag--' + kind;
    badge.textContent = value;
    return badge;
  }

  /* A role or channel marker - ADMIN, PRIVATE - so meaning never rides on
   * colour alone. Colour says it faster; this says it at all. */
  function marker(text, kind) {
    var el = document.createElement('span');
    el.className = 'arena-chat__marker arena-chat__marker--' + kind;
    el.textContent = text;
    return el;
  }

  function append(line) {
    var item = document.createElement('li');
    // The class carries the SERVER's answer for what this line is. The client
    // never decides that a line is admin or private; it is told.
    var cls = 'arena-chat__line';
    if (!line.heard) { cls += ' arena-chat__line--distant'; }
    if (line.role === 'admin') {
      cls += ' arena-chat__line--admin';
    } else if (line.channel === 'private') {
      cls += ' arena-chat__line--private';
    }
    item.className = cls;
    item.setAttribute('data-id', line.id);

    var who = document.createElement('span');
    who.className = 'arena-chat__who';

    // Alliance, then clan, then the name. The order is the identity.
    var alliance = tagBadge(line.alliance_tag, 'alliance');
    if (alliance) { who.appendChild(alliance); }
    var clan = tagBadge(line.clan_tag, 'clan');
    if (clan) { who.appendChild(clan); }

    var name = document.createElement('span');
    name.className = 'arena-chat__name';
    name.textContent = line.name;
    who.appendChild(name);

    if (line.role === 'admin') { who.appendChild(marker('Admin', 'admin')); }
    if (line.channel === 'private') { who.appendChild(marker('Private', 'private')); }

    // Everything after the name is an action on THIS line, so the trigger
    // lives on the line and the menu is built on demand - one menu component,
    // not one menu per message sitting in the DOM waiting to be opened.
    if (line.slug && line.slug !== mySlug) {
      var more = document.createElement('button');
      more.type = 'button';
      more.className = 'arena-chat__more';
      more.setAttribute('aria-haspopup', 'menu');
      more.setAttribute('aria-label', 'Actions for ' + line.name);
      more.textContent = '⋯';                    // MIDLINE HORIZONTAL ELLIPSIS
      more.addEventListener('click', function (event) {
        event.stopPropagation();
        openActions(line, more);
      });
      who.appendChild(more);
    }

    // The line being answered, quoted once and never nested further.
    if (line.reply_to) {
      var quote = document.createElement('span');
      quote.className = 'arena-chat__quote';
      var qname = document.createElement('b');
      qname.textContent = line.reply_to.name;
      quote.appendChild(qname);
      if (line.reply_to.preview) {
        quote.appendChild(document.createTextNode(' ' + line.reply_to.preview));
      }
      item.appendChild(quote);
    }

    var said = document.createElement('span');
    if (line.blocked) {
      // Blocked: the server sent no words at all, so there is nothing to show
      // and no Show to offer.
      said.className = 'arena-chat__said arena-chat__said--muffled';
      said.textContent = 'You blocked this person.';
    } else if (line.muted) {
      // Muted: a preference, so the words are here and the reader may choose.
      said.className = 'arena-chat__said arena-chat__said--muffled';
      said.textContent = 'This user is muted · ';
      var show = document.createElement('button');
      show.type = 'button';
      show.className = 'arena-chat__show';
      show.textContent = 'Show';
      show.addEventListener('click', function () {
        said.className = 'arena-chat__said';
        said.textContent = line.heard ? line.body : 'Talking Something';
      });
      said.appendChild(show);
    } else if (line.heard) {
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
    item.appendChild(reactionRow(line));
    log.appendChild(item);
    if (line.id > lastId) { lastId = line.id; }
  }

  /* The reaction strip under a line. Counts are the server's; a tap is
   * optimistic only in the sense that the server answers with the new truth
   * and this redraws from that answer rather than from a guess. */
  function reactionRow(line) {
    var row = document.createElement('span');
    row.className = 'arena-chat__reactions';
    row.setAttribute('data-for', line.id);
    REACTIONS.forEach(function (r) {
      var state = (line.reactions && line.reactions[r.key]) || null;
      var count = state ? state.count : 0;
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'arena-chat__react'
        + (state && state.mine ? ' is-mine' : '')
        + (count ? '' : ' is-empty');
      btn.setAttribute('data-emoji', r.key);
      btn.setAttribute('aria-pressed', state && state.mine ? 'true' : 'false');
      btn.setAttribute('aria-label', r.label + (count ? ' (' + count + ')' : ''));
      btn.textContent = r.glyph + (count ? ' ' + count : '');
      btn.addEventListener('click', function () { react(line.id, r.key, row); });
      row.appendChild(btn);
    });
    return row;
  }

  function react(messageId, emoji, row) {
    post(reactUrl, { message_id: messageId, emoji: emoji }).then(function (data) {
      if (!data || !data.ok) { return; }
      // Redraw this strip from the server's own counts.
      var fresh = reactionRow({ id: messageId, reactions: data.reactions });
      if (row.parentNode) { row.parentNode.replaceChild(fresh, row); }
    });
  }

  /* ONE action menu, for every line, on every device.
   *
   * The spec asks for a bottom sheet on a phone and an anchored popover on a
   * desktop, and says in the same breath not to build two of them. So this
   * builds ONE element with one set of buttons and one behaviour; whether it
   * arrives from the bottom of the screen or beside the trigger is decided by
   * a container query in the stylesheet, from the panel's own width. The
   * functionality is identical because it is literally the same code.
   */
  var openMenu = null;

  function closeActions() {
    if (openMenu && openMenu.parentNode) { openMenu.parentNode.removeChild(openMenu); }
    openMenu = null;
  }

  function menuButton(label, kind, onClick) {
    var b = document.createElement('button');
    b.type = 'button';
    b.className = 'arena-chat__action' + (kind ? ' arena-chat__action--' + kind : '');
    b.setAttribute('role', 'menuitem');
    b.textContent = label;
    b.addEventListener('click', function () { closeActions(); onClick(); });
    return b;
  }

  function openActions(line, trigger) {
    closeActions();
    var sheet = document.createElement('div');
    sheet.className = 'arena-chat__sheet';
    sheet.setAttribute('role', 'menu');
    sheet.setAttribute('aria-label', 'Actions for ' + line.name);

    var head = document.createElement('p');
    head.className = 'arena-chat__sheet-head';
    head.textContent = line.name;
    sheet.appendChild(head);

    sheet.appendChild(menuButton('View profile', '', function () {
      window.location.href = '/chef-battle/profile/' + encodeURIComponent(line.slug) + '/';
    }));
    sheet.appendChild(menuButton('Reply', '', function () { startReply(line); }));
    sheet.appendChild(menuButton('Message privately', '', function () {
      openDm(line.slug, line.name);
    }));
    sheet.appendChild(menuButton(
      line.muted ? 'Unmute' : 'Mute', '',
      function () { relation(line.muted ? 'unmute' : 'mute', line.slug); }
    ));
    // Blocking is the destructive one of the pair, so it asks first.
    sheet.appendChild(menuButton(
      line.blocked ? 'Unblock' : 'Block', 'danger',
      function () {
        if (line.blocked) { relation('unblock', line.slug); return; }
        if (window.confirm('Block ' + line.name + '? They will not be able to '
                           + 'message you privately.')) {
          relation('block', line.slug);
        }
      }
    ));
    sheet.appendChild(menuButton('Report', 'danger', function () { openReport(line); }));

    root.appendChild(sheet);
    openMenu = sheet;
    // Anchored to the trigger when there is room beside it; the stylesheet
    // ignores these on a narrow container, where the sheet spans the panel.
    var box = trigger.getBoundingClientRect();
    var mine = root.getBoundingClientRect();
    sheet.style.setProperty('--sheet-top', (box.bottom - mine.top + 4) + 'px');
    sheet.style.setProperty('--sheet-left', (box.left - mine.left) + 'px');
    var first = sheet.querySelector('.arena-chat__action');
    if (first) { first.focus(); }
  }

  function openReport(line) {
    var reasons = [
      ['spam', 'Spam'],
      ['harassment', 'Harassment or bullying'],
      ['hate', 'Hate or abusive content'],
      ['sexual', 'Sexual content'],
      ['violence', 'Threats or violence'],
      ['personal_information', 'Personal information'],
      ['scam', 'Scam or fraud'],
      ['illegal', 'Illegal content'],
      ['other', 'Other']
    ];
    var sheet = document.createElement('div');
    sheet.className = 'arena-chat__sheet arena-chat__sheet--report';
    sheet.setAttribute('role', 'menu');
    var head = document.createElement('p');
    head.className = 'arena-chat__sheet-head';
    head.textContent = 'Report this message';
    sheet.appendChild(head);
    reasons.forEach(function (pair) {
      sheet.appendChild(menuButton(pair[1], '', function () {
        post(reportUrl, { message_id: line.id, reason: pair[0] }).then(function (data) {
          notice(data && data.ok
            ? (data.already_reported ? 'Already reported. Thank you.'
                                     : 'Reported. Thank you.')
            : 'Could not send that report.');
        });
      }));
    });
    root.appendChild(sheet);
    openMenu = sheet;
  }

  function relation(action, slug) {
    post(relationUrl, { action: action, slug: slug }).then(function (data) {
      if (!data || !data.ok) { notice('That did not work.'); return; }
      // The whole log is repainted from the server on the next tick, because a
      // mute changes every line by that person, not only the one tapped.
      lastId = 0;
      log.innerHTML = '';
      poll();
      notice(data.blocked ? 'Blocked.' : (data.muted ? 'Muted.' : 'Done.'));
    });
  }

  /* Why a private room could not be opened, in the reader's words. The server
   * decides; this only translates. */
  var DM_REFUSALS = {
    blocked: 'You cannot message this person.',
    recipient_accepts_no_messages: 'This chef does not accept private messages.',
    recipient_accepts_team_only: 'This chef only accepts messages from their clan.',
    cannot_message_yourself: 'That is you.',
    not_authenticated: 'Sign in to send private messages.'
  };

  function openDm(slug, name) {
    post(root.getAttribute('data-dm-open-url'), { slug: slug }).then(function (data) {
      if (!data || !data.ok) {
        notice((data && DM_REFUSALS[data.error]) || 'Could not open that conversation.');
        return;
      }
      enterRoom(data.conversation, name);
    });
  }

  /* Switch the ONE component to another room. Not a second chat: the log is
   * cleared, the delta reset, and the same renderer paints whatever the server
   * sends next. */
  function enterRoom(id, name) {
    room = id;
    roomName = name || '';
    replyingTo = null;
    cancelReply();
    lastId = 0;
    log.innerHTML = '';
    paintRoomChrome();
    poll();
  }

  function leaveRoom() {
    enterRoom(null, '');
  }

  /* The header and composer say, unmistakably, which room this is - the spec's
   * own requirement that a DM can never be mistaken for the public hall. */
  function paintRoomChrome() {
    var bar = document.getElementById('arena-chat-room');
    var label = document.getElementById('arena-chat-room-name');
    root.classList.toggle('is-private', room !== null);
    if (bar) { bar.hidden = (room === null); }
    if (label) { label.textContent = roomName; }
    if (input) {
      input.placeholder = room === null
        ? 'Join the conversation...'
        : 'Message ' + roomName + ' privately...';
    }
  }

  function startReply(line) {
    replyingTo = line;
    var bar = document.getElementById('arena-chat-replying');
    if (bar) {
      bar.hidden = false;
      var who = bar.querySelector('.arena-chat__replying-name');
      if (who) { who.textContent = line.name; }
    }
    if (input) { input.focus(); }
  }

  function cancelReply() {
    replyingTo = null;
    var bar = document.getElementById('arena-chat-replying');
    if (bar) { bar.hidden = true; }
  }

  /* A short, self-clearing line under the composer. Errors and confirmations
   * belong where the reader is already looking, not in an alert box. */
  function notice(text) {
    var el = document.getElementById('arena-chat-notice');
    if (!el) { return; }
    el.textContent = text;
    el.hidden = false;
    window.clearTimeout(notice._t);
    notice._t = window.setTimeout(function () { el.hidden = true; }, 4000);
  }

  function post(url, fields) {
    var body = new FormData();
    Object.keys(fields).forEach(function (k) { body.append(k, fields[k]); });
    body.append('csrfmiddlewaretoken', csrf());
    return fetch(url, { method: 'POST', credentials: 'same-origin', body: body })
      .then(function (r) { return r.json(); })
      .catch(function () { return null; });
  }

  var cancelBtn = document.getElementById('arena-chat-replying-cancel');
  if (cancelBtn) { cancelBtn.addEventListener('click', cancelReply); }

  var leaveBtn = document.getElementById('arena-chat-room-leave');
  if (leaveBtn) { leaveBtn.addEventListener('click', leaveRoom); }

  document.addEventListener('click', function (event) {
    if (openMenu && !openMenu.contains(event.target)) { closeActions(); }
  });
  document.addEventListener('keydown', function (event) {
    if (event.key === 'Escape') {
      if (openMenu) { closeActions(); } else if (replyingTo) { cancelReply(); }
    }
  });

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

  /* The number beside LIVE: how many people are actually in the hall.
   *
   * Written into its own element, never into the badge's own text, so "LIVE"
   * stays a word a screen reader can read on its own and the count can vanish
   * (server says nothing) without taking the badge with it. */
  function showListening(count) {
    var el = document.getElementById('arena-chat-listening');
    if (!el) { return; }
    if (typeof count !== 'number' || count < 0) {
      el.hidden = true;
      el.textContent = '';
      return;
    }
    el.hidden = false;
    el.textContent = String(count);
  }

  function poll() {
    if (busy) { return; }
    busy = true;
    var url = feedUrl + '?since=' + encodeURIComponent(lastId)
      + (room !== null ? '&conversation=' + encodeURIComponent(room) : '');
    fetch(url, {
      credentials: 'same-origin',
      headers: { 'X-Requested-With': 'XMLHttpRequest' }
    })
      .then(function (response) {
        // 404 here means the room is not ours (or no longer exists). Fall back
        // to the hall rather than polling a closed door forever.
        if (response.status === 404 && room !== null) {
          notice('That conversation is no longer available.');
          leaveRoom();
          return null;
        }
        return response.json();
      })
      .then(function (data) {
        if (!data) { return; }
        seatMe(!!data.seated);
        // The hall's headcount is the hall's. A private room does not have one
        // and must not inherit the last number the hall reported.
        showListening(room === null ? data.listening : null);
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
    if (replyingTo) { body.append('reply_to', replyingTo.id); }
    if (room !== null) { body.append('conversation', room); }
    body.append('csrfmiddlewaretoken', csrf());
    input.value = '';
    input.focus();
    cancelReply();
    fetch(sendUrl, { method: 'POST', credentials: 'same-origin', body: body })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ok) {
          absorb(data.messages);
        } else {
          input.value = text;
          notice(data && data.error === 'rate_limited'
            ? 'Slow down a moment.'
            : 'That did not send.');
        }
      })
      .catch(function () {
        input.value = text;                          // put it back, lose nothing
        notice('That did not send.');
      });
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
