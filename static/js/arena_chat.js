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
  /* Rendered from has_perm on the SERVER. Presentation only - every moderation
   * endpoint re-checks the permission itself. */
  var canModerate = root.getAttribute('data-can-moderate') === '1';
  var canTimeout = root.getAttribute('data-can-timeout') === '1';

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

  /* "now", "2m", "3h", "5d" - the shortest true thing.
   *
   * The server sends an ISO instant and this turns it into an age, so the
   * reader's own clock and timezone decide what it says. Under a minute is
   * "now" rather than a second-by-second counter: a live chat does not need a
   * stopwatch, and a number that changes every second is movement in the
   * corner of the eye for nothing. */
  function relativeTime(iso) {
    var then = Date.parse(iso);
    if (isNaN(then)) { return ''; }
    var seconds = Math.max(0, Math.round((Date.now() - then) / 1000));
    if (seconds < 60) { return 'now'; }
    var minutes = Math.floor(seconds / 60);
    if (minutes < 60) { return minutes + 'm'; }
    var hours = Math.floor(minutes / 60);
    if (hours < 24) { return hours + 'h'; }
    return Math.floor(hours / 24) + 'd';
  }

  /* Ages go stale where they stand, so they are refreshed in place rather than
   * by repainting the log - a repaint would lose the reader's scroll position
   * and any menu they had open. */
  function refreshTimes() {
    var stamps = log.querySelectorAll('.arena-chat__time');
    for (var i = 0; i < stamps.length; i++) {
      var fresh = relativeTime(stamps[i].getAttribute('data-at'));
      if (stamps[i].textContent !== fresh) { stamps[i].textContent = fresh; }
    }
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
    // Only a moderator is ever sent one of these; it reads as withdrawn rather
    // than as ordinary speech, so it cannot be mistaken for live conversation.
    if (line.hidden) { cls += ' arena-chat__line--hidden'; }
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

    // ADMIN is the site speaking officially, so it is red. MOD is authority
    // without officialdom, so it is a badge on an ordinary-coloured line.
    if (line.role === 'admin') { who.appendChild(marker('Admin', 'admin')); }
    else if (line.role === 'moderator') { who.appendChild(marker('Mod', 'mod')); }

    // TIME AND ACTIONS SIT AT THE FAR RIGHT OF THE HEADER, never in the words.
    // The ellipsis used to follow the name inline, where the Owner read it as
    // part of the sentence; it is a vertical ellipsis in its own column now.
    var meta = document.createElement('span');
    meta.className = 'arena-chat__meta';

    if (line.at) {
      var when = document.createElement('time');
      when.className = 'arena-chat__time';
      when.setAttribute('datetime', line.at);
      when.setAttribute('data-at', line.at);
      when.textContent = relativeTime(line.at);
      // The exact moment stays available to anyone who wants it, without
      // spending a pixel on it.
      when.title = new Date(line.at).toLocaleString();
      meta.appendChild(when);
    }

    // One menu component, built on demand - not one menu per message sitting
    // in the DOM waiting to be opened. Own lines get it too: replying to
    // yourself is pointless, but reacting and moderating are not.
    var more = document.createElement('button');
    more.type = 'button';
    more.className = 'arena-chat__more';
    more.setAttribute('aria-haspopup', 'menu');
    more.setAttribute('aria-expanded', 'false');
    more.setAttribute('aria-label', 'Actions for ' + line.name);
    more.textContent = '⋮';                 // VERTICAL ELLIPSIS
    more.addEventListener('click', function (event) {
      event.stopPropagation();
      openActions(line, more);
    });
    meta.appendChild(more);
    who.appendChild(meta);

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
    var strip = reactionRow(line);
    if (strip) { item.appendChild(strip); }
    log.appendChild(item);
    if (line.id > lastId) { lastId = line.id; }
  }

  /* The reaction strip under a line - ONLY where there is something to show.
   *
   * It used to draw all three buttons under every message, greyed. Greying
   * does not give the vertical space back: six messages filled the Owner's
   * phone and he said so. A live chat is mostly lines nobody has reacted to,
   * so the strip is now the exception rather than the furniture, and reacting
   * is offered where every other per-line action already lives - the one
   * action menu. Returns null when the line has no reactions at all. */
  function reactionRow(line) {
    var counts = line.reactions || {};
    var shown = REACTIONS.filter(function (r) {
      return counts[r.key] && counts[r.key].count > 0;
    });
    if (!shown.length) { return null; }

    var row = document.createElement('span');
    row.className = 'arena-chat__reactions';
    row.setAttribute('data-for', line.id);
    shown.forEach(function (r) {
      var state = counts[r.key];
      var btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'arena-chat__react' + (state.mine ? ' is-mine' : '');
      btn.setAttribute('data-emoji', r.key);
      btn.setAttribute('aria-pressed', state.mine ? 'true' : 'false');
      btn.setAttribute('aria-label', r.label + ' (' + state.count + ')');
      btn.textContent = r.glyph + ' ' + state.count;
      btn.addEventListener('click', function () { react(line.id, r.key, row); });
      row.appendChild(btn);
    });
    return row;
  }

  /* Redraw one line's strip from the server's own counts. It may need to be
   * created (first reaction on this line) or removed (the last one taken
   * back), not only replaced - which is what the strip being conditional
   * costs, and it is worth the vertical space it gives back. */
  function react(messageId, emoji) {
    post(reactUrl, { message_id: messageId, emoji: emoji }).then(function (data) {
      if (!data || !data.ok) {
        notice(data && data.error === 'not_in_the_hall'
          ? 'Take a seat to react.'
          : 'That did not register.');
        return;
      }
      var item = log.querySelector('[data-id="' + messageId + '"]');
      if (!item) { return; }
      var old = item.querySelector('.arena-chat__reactions');
      var fresh = reactionRow({ id: messageId, reactions: data.reactions });
      if (old && fresh) { item.replaceChild(fresh, old); }
      else if (old) { item.removeChild(old); }
      else if (fresh) { item.appendChild(fresh); }
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
    // Reacting lives HERE now rather than as three permanent buttons under
    // every message. One row of glyphs inside the menu, not a panel.
    var reactRow = document.createElement('div');
    reactRow.className = 'arena-chat__sheet-reacts';
    REACTIONS.forEach(function (r) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'arena-chat__sheet-react';
      b.setAttribute('aria-label', r.label);
      b.textContent = r.glyph;
      b.addEventListener('click', function () {
        closeActions();
        react(line.id, r.key);
      });
      reactRow.appendChild(b);
    });
    sheet.appendChild(reactRow);
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

    /* MODERATOR ACTIONS, WHEN THE SERVER SAYS SO.
     *
     * canModerate is rendered from has_perm on the server, never inferred here
     * from a staff flag. And it only decides what is DRAWN: every endpoint
     * re-checks the permission, so a hand-made request from somebody who sees
     * no buttons is refused by the same rule that hid them. Hidden UI is not
     * the control. */
    if (canModerate) {
      sheet.appendChild(menuButton(
        line.hidden ? 'Restore message' : 'Hide message', 'danger',
        function () { moderate({ action: line.hidden ? 'restore' : 'hide',
                                 message_id: line.id }); }
      ));
    }
    if (canTimeout) {
      [['10 minutes', 10], ['1 hour', 60], ['24 hours', 1440]].forEach(function (pair) {
        sheet.appendChild(menuButton('Timeout ' + pair[0], 'danger', function () {
          if (window.confirm('Silence ' + line.name + ' for ' + pair[0] + '?')) {
            moderate({ action: 'timeout', slug: line.slug, minutes: pair[1] });
          }
        }));
      });
    }

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

  function moderate(fields) {
    post(root.getAttribute('data-moderate-url'), fields).then(function (data) {
      if (!data || !data.ok) {
        notice(data && data.error === 'not_permitted'
          ? 'You do not have that permission.'
          : 'That action failed.');
        return;
      }
      lastId = 0;
      log.innerHTML = '';
      poll();
      notice('Done.');
    });
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

  /* CHAT / PM / USERS / SETTINGS - Owner's desktop rebuild, 2026-08-25.
   *
   * Four ARIA tabs sharing one root. Only CHAT talks to the delta poll above;
   * PM and USERS each fetch their own list ON ACTIVATION from endpoints that
   * already existed (arena_chat_conversations, and the new arena_chat_users)
   * but had no caller until now - this is wiring, not new backend behaviour.
   * Opening a DM from the PM list reuses enterRoom(), the SAME primitive the
   * per-message "Message privately" action already calls, so a private room
   * opened either way behaves identically.
   */
  var tabs = document.querySelectorAll('.arena-chat__tab');
  var panels = {
    chat: document.getElementById('arena-chat-panel-chat'),
    pm: document.getElementById('arena-chat-panel-pm'),
    users: document.getElementById('arena-chat-panel-users'),
    settings: document.getElementById('arena-chat-panel-settings')
  };

  function activateTab(name) {
    for (var i = 0; i < tabs.length; i++) {
      var tab = tabs[i];
      var active = tab.getAttribute('data-tab') === name;
      tab.setAttribute('aria-selected', active ? 'true' : 'false');
      tab.tabIndex = active ? 0 : -1;
    }
    Object.keys(panels).forEach(function (key) {
      if (panels[key]) { panels[key].hidden = key !== name; }
    });
    if (name === 'pm') { loadConversations(); }
    else if (name === 'users') { loadUsers(); }
  }

  /* Opening a conversation from the PM list has to land the reader back on
   * the CHAT panel - that panel holds the one log/composer every room
   * shares - and THEN switch rooms, so nobody sees an empty tab flash by. */
  function openConversation(id, name) {
    activateTab('chat');
    enterRoom(id, name);
  }

  function loadConversations() {
    var list = document.getElementById('arena-chat-dm-list');
    var emptyRow = document.getElementById('arena-chat-dm-empty');
    var url = root.getAttribute('data-dm-list-url');
    if (!list || !url) { return; }
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var rooms = (data && data.conversations) || [];
        list.innerHTML = '';
        if (!rooms.length) {
          if (emptyRow) { list.appendChild(emptyRow); }
          else {
            var li = document.createElement('li');
            li.className = 'arena-panel__empty';
            li.textContent = 'No private conversations yet.';
            list.appendChild(li);
          }
          return;
        }
        rooms.forEach(function (room) {
          var li = document.createElement('li');
          li.className = 'arena-chat__dm-row';
          li.tabIndex = 0;
          li.setAttribute('role', 'button');
          li.textContent = room.name;
          li.addEventListener('click', function () { openConversation(room.id, room.name); });
          li.addEventListener('keydown', function (event) {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault();
              openConversation(room.id, room.name);
            }
          });
          list.appendChild(li);
        });
      })
      .catch(function () { /* one dropped list is not worth a notice */ });
  }

  function loadUsers() {
    var list = document.getElementById('arena-chat-users-list');
    var emptyRow = document.getElementById('arena-chat-users-empty');
    var url = root.getAttribute('data-users-url');
    if (!list || !url) { return; }
    fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        var users = (data && data.users) || [];
        list.innerHTML = '';
        if (!users.length) {
          if (emptyRow) { list.appendChild(emptyRow); }
          else {
            var li = document.createElement('li');
            li.className = 'arena-panel__empty';
            li.textContent = 'Nobody is in the hall right now.';
            list.appendChild(li);
          }
          return;
        }
        users.forEach(function (user) {
          var li = document.createElement('li');
          li.className = 'arena-chat__user-row';
          var alliance = tagBadge(user.alliance_tag, 'alliance');
          if (alliance) { li.appendChild(alliance); }
          var clan = tagBadge(user.clan_tag, 'clan');
          if (clan) { li.appendChild(clan); }
          var name = document.createElement('span');
          name.className = 'arena-chat__name';
          name.textContent = user.name;
          li.appendChild(name);
          if (user.role === 'admin') { li.appendChild(marker('Admin', 'admin')); }
          else if (user.role === 'moderator') { li.appendChild(marker('Mod', 'mod')); }
          list.appendChild(li);
        });
      })
      .catch(function () { /* one dropped list is not worth a notice */ });
  }

  var settingsForm = document.getElementById('arena-chat-settings-form');
  if (settingsForm) {
    // Server-rendered starting value (viewer_dm_policy), read once at load -
    // the endpoint re-validates whatever the form later posts regardless.
    var startingPolicy = root.getAttribute('data-dm-policy') || 'anyone';
    var radios = settingsForm.querySelectorAll('input[name="dm_policy"]');
    for (var r = 0; r < radios.length; r++) {
      radios[r].checked = radios[r].value === startingPolicy;
    }
    settingsForm.addEventListener('submit', function (event) {
      event.preventDefault();
      var checked = settingsForm.querySelector('input[name="dm_policy"]:checked');
      if (!checked) { return; }
      post(root.getAttribute('data-dm-policy-url'), { policy: checked.value })
        .then(function (data) {
          notice(data && data.ok ? 'Saved.' : 'That did not save.');
        });
    });
  }

  for (var t = 0; t < tabs.length; t++) {
    tabs[t].addEventListener('click', function (event) {
      activateTab(event.currentTarget.getAttribute('data-tab'));
    });
  }

  /* Pinned Rules - collapsed by default, remembered only for this tab's
   * session (sessionStorage), nothing server-side for a panel this small. */
  var rulesToggle = document.getElementById('arena-chat-rules-toggle');
  var rulesBody = document.getElementById('arena-chat-rules-body');
  if (rulesToggle && rulesBody) {
    var RULES_KEY = 'arena-chat-rules-open';
    function paintRules(open) {
      rulesToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      rulesBody.hidden = !open;
    }
    paintRules(window.sessionStorage && window.sessionStorage.getItem(RULES_KEY) === '1');
    rulesToggle.addEventListener('click', function () {
      var open = rulesToggle.getAttribute('aria-expanded') !== 'true';
      paintRules(open);
      if (window.sessionStorage) {
        window.sessionStorage.setItem(RULES_KEY, open ? '1' : '0');
      }
    });
  }

  poll();
  setInterval(poll, POLL_MS);
  // Once a minute is enough for an age measured in minutes, and it costs
  // nothing: no request, no repaint, just the text of the stamps already drawn.
  setInterval(refreshTimes, 60000);
})();
