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

  /* THE REACTION SET, and it is not free-form. Every key here must also exist
   * in ArenaChatReaction.Emoji on the server - arena_chat_react validates
   * against Emoji.values, so a key added here and nowhere else is refused with
   * bad_emoji rather than silently stored. Widened from the Owner's original
   * three to seven on 2026-08-25 (migration 0104), which is additive: rows
   * already carrying fire/clap/star are untouched.
   *
   * Everything that reads this array - reactionRow(), sumReactions(), the
   * action sheet's glyph row, the hover strip - iterates it rather than
   * indexing it, so the length is not structural anywhere. */
  var REACTIONS = [
    { key: 'fire',  glyph: '🔥', label: 'Fire' },
    { key: 'clap',  glyph: '👏', label: 'Clap' },
    { key: 'star',  glyph: '⭐', label: 'Star' },
    { key: 'smile', glyph: '😀', label: 'Smile' },
    { key: 'laugh', glyph: '😂', label: 'Laugh' },
    { key: 'heart', glyph: '❤️', label: 'Heart' },
    { key: 'wow',   glyph: '😮', label: 'Wow' }
  ];

  /* CUSTOM CulinEire EMOJI - stored in a message as a SEMANTIC TOKEN, never as
   * a path. ":golden_knife:" survives the drawing being redrawn, restyled or
   * moved, and a token whose drawing is missing degrades to readable text
   * rather than to a broken image. The drawings live in the sprite partial
   * templates/chef_battle/_arena_chat_emoji_sprite.html under "ace-" ids. */
  var CUSTOM_EMOJI = [
    { token: 'golden_knife',   label: 'Golden Knife' },
    { token: 'flaming_pan',    label: 'Flaming Pan' },
    { token: 'chef_hat',       label: 'Chef Hat' },
    { token: 'arena_crown',    label: 'Arena Crown' },
    { token: 'burned_toast',   label: 'Burned Toast' },
    { token: 'perfect_sear',   label: 'Perfect Sear' },
    { token: 'bear_mascot',    label: 'Bear Mascot' },
    { token: 'culinary_master', label: 'Culinary Master' },
    { token: 'sauce_splash',   label: 'Sauce Splash' },
    { token: 'battle_shield',  label: 'Battle Shield' }
  ];

  /* A lookup, built once, so rendering a body does not scan an array per token. */
  var CUSTOM_EMOJI_BY_TOKEN = {};
  CUSTOM_EMOJI.forEach(function (e) { CUSTOM_EMOJI_BY_TOKEN[e.token] = e; });

  /* The hover strip shows FIVE, not all seven. It sits on every row of a
   * dense log, so its width is the message's width; the full set is one tap
   * further on, in the action menu, which is where it has always been. */
  var QUICK_REACTIONS = REACTIONS.slice(0, 5);

  /* THE PICKER'S CONTENTS. Hand-curated rather than pulled from a library:
   * this project has no bundler (see any static/js file - they are served as
   * written), so an emoji dataset would have to be vendored as a blob nobody
   * here can audit. A few hundred of the ones people actually reach for beats
   * a megabyte of every codepoint, and the Cooking and Battle groups are the
   * point of a CULINARY arena's picker anyway. */
  var EMOJI_CATEGORIES = [
    { key: 'culineire', label: 'CulinÉire', custom: true },
    { key: 'cooking', label: 'Cooking', glyphs: (
      '👨‍🍳 👩‍🍳 🔪 🍳 🥘 🍲 🥣 🍜 🍝 🥩 🍗 🍖 🥓 🌶️ 🧂 🧄 🧅 🥕 🥔 🍅 '
      + '🥦 🥬 🌽 🍄 🥑 🍋 🍎 🍞 🥐 🥖 🧀 🥚 🍰 🧁 🍫 🍯 🔥 ♨️ 🍽️ 🥄'
    ).split(' ') },
    { key: 'battle', label: 'Battle', glyphs: (
      '⚔️ 🛡️ 👑 💥 🎯 🏆 🚩 🥇 🥈 🥉 ⭐ 🌟 💫 ⚡ 🔱 🎖️ 🏅 ⏱️ 📣 🎬'
    ).split(' ') },
    { key: 'smileys', label: 'Smileys', glyphs: (
      '😀 😃 😄 😁 😆 😅 😂 🤣 🙂 🙃 😉 😊 😇 🥰 😍 🤩 😘 😗 😚 😙 '
      + '😋 😛 😜 🤪 😝 🤑 🤗 🤭 🤫 🤔 🤐 🤨 😐 😑 😶 😏 😒 🙄 😬 😮‍💨 '
      + '😌 😔 😪 🤤 😴 😷 🤒 🤕 🤢 🤮 🥵 🥶 😵 🤯 🤠 🥳 😎 🤓 🧐 😕 '
      + '😟 🙁 😮 😯 😲 😳 🥺 😦 😧 😨 😰 😥 😢 😭 😱 😖 😣 😞 😓 😩 '
      + '😫 🥱 😤 😡 😠 🤬 😈 💀 👻 🤖'
    ).split(' ') },
    { key: 'people', label: 'People', glyphs: (
      '👋 🤚 ✋ 🖖 👌 🤌 🤏 ✌️ 🤞 🤟 🤘 🤙 👈 👉 👆 👇 ☝️ 👍 👎 ✊ '
      + '👊 🤛 🤜 👏 🙌 👐 🤲 🤝 🙏 💪 🦾 👀 👁️ 👅 👄 🧠 🫀 👶 🧑 👨 '
      + '👩 🧓 🕺 💃 🧑‍🤝‍🧑 👥 🫂 💅'
    ).split(' ') },
    { key: 'objects', label: 'Objects', glyphs: (
      '📱 💻 ⌨️ 🖥️ 🖨️ 📷 📸 🎥 📺 📻 ⏰ ⌚ 📡 🔋 💡 🔦 🕯️ 🧯 🛒 🎁 '
      + '🎈 🎉 🎊 🎀 🔑 🔒 🔓 🔨 🪓 ⚙️ 🧰 🧲 🧪 🧫 🌡️ 🧹 🧺 🧻 🧼 🪣 '
      + '📦 📬 📝 📖 📚 🗓️ 📌 📎 ✂️ 📏'
    ).split(' ') },
    { key: 'symbols', label: 'Symbols', glyphs: (
      '❤️ 🧡 💛 💚 💙 💜 🖤 🤍 🤎 💔 ❣️ 💕 💞 💓 💗 💖 💘 💝 ✅ ❌ '
      + '❗ ❓ ⚠️ 🚫 ♻️ 🔔 🔕 💬 💭 🗯️ ➕ ➖ ✖️ ➗ 🟢 🔴 🟡 🔵 ⚫ ⚪ '
      + '🔺 🔻 🔶 🔷 ⏳ ⌛ 🆗 🆕 🔝 💯'
    ).split(' ') }
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

  /* WHO IS IN THE HALL, cached for the mention dropdown.
   *
   * Deliberately the SAME data the USERS tab already fetches - one endpoint,
   * one shape, one refresh path. loadUsers() fills this as a side effect, so
   * a reader who has never opened the USERS tab still gets one fetch the
   * first time they type "@" and nothing more after that. */
  var roster = [];
  var rosterFetched = false;

  /* PERSONALISATION lives in localStorage and NOT on the server, on purpose.
   *
   * dm_policy is a profile field because it is a PERMISSION - the server
   * enforces it when somebody tries to open a conversation. None of these
   * are: no endpoint reads them, no other person is affected by them, and
   * they describe this browser's view of the log. A column the server never
   * reads is a column that drifts, so these stay where the decision lives. */
  var PREFS_KEY = 'arena-chat-prefs';
  var PREF_DEFAULTS = {
    density: 'compact',
    fontSize: 'normal',
    showTags: true,
    showTimestamps: true,
    reactionAnimations: true,
    // The brief's "Animated GIFs ON / OFF". Off does not mean paused - it
    // means the animated file is never requested; see mediaNode().
    animatedMedia: true,
    // One of four curated palettes. "ivory" is the absence of a theme, so it
    // is the Arena's own colours and cannot drift from them.
    theme: 'ivory'
  };
  var prefs = readPrefs();

  function readPrefs() {
    var out = {};
    Object.keys(PREF_DEFAULTS).forEach(function (k) { out[k] = PREF_DEFAULTS[k]; });
    try {
      var raw = window.localStorage && window.localStorage.getItem(PREFS_KEY);
      if (raw) {
        var saved = JSON.parse(raw);
        Object.keys(PREF_DEFAULTS).forEach(function (k) {
          if (saved && typeof saved[k] === typeof PREF_DEFAULTS[k]) { out[k] = saved[k]; }
        });
      }
    } catch (e) { /* a corrupt or blocked store is just the defaults */ }
    return out;
  }

  function writePrefs() {
    try {
      if (window.localStorage) {
        window.localStorage.setItem(PREFS_KEY, JSON.stringify(prefs));
      }
    } catch (e) { /* private mode; the session still works, it just forgets */ }
  }

  /* Applied as classes and one custom property on the root, so the stylesheet
   * owns every actual value and this only says WHICH. */
  function applyPersonalisation() {
    root.classList.toggle('is-comfortable', prefs.density === 'comfortable');
    root.classList.toggle('is-hiding-tags', !prefs.showTags);
    root.classList.toggle('is-hiding-times', !prefs.showTimestamps);
    root.classList.toggle('is-still', !prefs.reactionAnimations);
    root.setAttribute('data-font-size', prefs.fontSize);
    // Ivory declares nothing in the stylesheet, so it is expressed by the
    // attribute being absent rather than by a fourth palette that repeats the
    // Arena's own colours and could fall out of step with them.
    if (prefs.theme && prefs.theme !== 'ivory') {
      root.setAttribute('data-theme', prefs.theme);
    } else {
      root.removeAttribute('data-theme');
    }
  }

  function csrf() {
    var field = form && form.querySelector('[name=csrfmiddlewaretoken]');
    return field ? field.value : '';
  }

  /* "22:18" - the actual clock, not an age.
   *
   * A live Arena feed reads like a transcript, not a social timeline: "10h"
   * tells a reader nothing about when in the evening a line was said next to
   * lines from five minutes ago. HH:mm in the reader's own locale, forced to
   * 24-hour so it stays a fixed width regardless of locale. Absolute time
   * never goes stale, so unlike the age it once was, nothing here needs a
   * refresh interval - the full instant is still one hover away, on the
   * element's title. */
  function formatTime(iso) {
    var then = new Date(iso);
    if (isNaN(then.getTime())) { return ''; }
    return then.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', hour12: false });
  }

  /* Every place the log is thrown away and refetched (room switch,
   * moderation, mute/block) must also clear the reaction summary - it is
   * computed FROM the log's own DOM, so a stale summary would otherwise
   * survive until the next batch of messages happened to arrive. */
  function clearLog() {
    log.innerHTML = '';
    var summary = document.getElementById('arena-chat-reaction-summary');
    if (summary) { summary.hidden = true; summary.innerHTML = ''; }
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

  /* THE MESSAGE BODY, WITH CUSTOM EMOJI AND MENTIONS - AND NOT ONE LINE OF
   * innerHTML ANYWHERE IN IT.
   *
   * This is the one function in the file that turns a stranger's text into
   * more than a single text node, so it is the one place an XSS could ever
   * enter. It cannot: every branch below either sets .textContent or calls
   * createElement/createTextNode, so the body's characters can only ever
   * BECOME text, never markup. Anyone editing this function keeps that
   * property or breaks the whole component's safety story.
   *
   * What it recognises, in one pass over the text:
   *   :golden_knife:  ->  the sprite drawing, IF that exact token is one of
   *                       ours. An unknown :word: stays literal text, so a
   *                       recipe that mentions a ratio like 1:2: is untouched.
   *   @Name           ->  a highlight, IF Name is somebody the roster
   *                       actually returned. An arbitrary @word is left
   *                       alone - a mention that highlights strangers is a
   *                       spoofing surface, not a feature. */
  /* The candidate after an "@" is deliberately GENEROUS - up to 40 characters
   * that could belong to a display name, spaces included, because a chef may
   * be called "Green Bear". How much of that run is actually a name is not
   * the pattern's decision and cannot be: resolveMention() asks the roster,
   * and only what the roster confirms is consumed. Letting the pattern decide
   * was the first version's bug - greedy with a space in the class, it
   * swallowed "@GreenBearDev nice sear" whole, matched nobody, and silently
   * rendered every mention as plain text. */
  var BODY_TOKEN = /:([a-z0-9_]{2,32}):|@([\p{L}\p{N}_][\p{L}\p{N}_ '.-]{0,39})/gu;

  function paintBody(target, text) {
    var body = String(text == null ? '' : text);
    var at = 0;
    var match;
    BODY_TOKEN.lastIndex = 0;
    while ((match = BODY_TOKEN.exec(body)) !== null) {
      var node = null;
      var consumed = match[0].length;
      if (match[1] !== undefined) {
        node = customEmojiNode(match[1]);
      } else if (match[2] !== undefined) {
        var hit = resolveMention(match[2]);
        if (hit) {
          node = mentionNode(hit.user);
          consumed = 1 + hit.length;    // the "@" plus the name the roster owns
        }
      }
      if (!node) { continue; }          // not ours: leave it as plain text
      if (match.index > at) {
        target.appendChild(document.createTextNode(body.slice(at, match.index)));
      }
      target.appendChild(node);
      at = match.index + consumed;
      // The run may have reached past the name; carry on from where the name
      // actually ended, not from where the pattern stopped looking.
      BODY_TOKEN.lastIndex = at;
    }
    if (at < body.length) {
      target.appendChild(document.createTextNode(body.slice(at)));
    }
  }

  /* WHICH ROSTER NAME THIS RUN STARTS WITH, if any - longest first, so a hall
   * holding both "Green" and "Green Bear" resolves "@Green Bear" to the
   * longer of the two rather than to the first one found.
   *
   * The name has to end at a word boundary inside the run, or "@Green" would
   * light up the first six letters of "@Greenhouse". */
  function resolveMention(run) {
    var lower = run.toLowerCase();
    var best = null;
    for (var i = 0; i < roster.length; i++) {
      var name = String(roster[i].name || '');
      if (!name) { continue; }
      if (lower.indexOf(name.toLowerCase()) !== 0) { continue; }
      var next = run.charAt(name.length);
      if (next && /[\p{L}\p{N}_]/u.test(next)) { continue; }
      if (!best || name.length > best.length) {
        best = { user: roster[i], length: name.length };
      }
    }
    return best;
  }

  function customEmojiNode(token) {
    var known = CUSTOM_EMOJI_BY_TOKEN[token];
    if (!known) { return null; }
    var svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('class', 'arena-chat__emoji');
    svg.setAttribute('role', 'img');
    // The label travels with the drawing, so a screen reader hears the emoji's
    // name rather than skipping a decorative blank.
    svg.setAttribute('aria-label', known.label);
    var use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
    // Built from OUR OWN token table, never from the message text - the value
    // here can only be a string this file shipped.
    use.setAttribute('href', '#ace-' + known.token);
    svg.appendChild(use);
    return svg;
  }

  /* The highlight itself. resolveMention() above has already decided that
   * this person is real; this only draws them, from the ROSTER's spelling of
   * the name rather than the typist's, so "@greenbeardev" renders as the
   * chef actually writes it. */
  function mentionNode(found) {
    if (!found) { return null; }
    var el = document.createElement('span');
    el.className = 'arena-chat__mention';
    if (mySlug && found.slug === mySlug) { el.className += ' is-me'; }
    el.textContent = '@' + found.name;
    return el;
  }

  /* HOW A LINE BECOMES DOM, and the seam a later pass extends.
   *
   * Every message the server sends today is a person talking, so there is
   * exactly one renderer registered and `kind` is absent from every row on
   * the wire. The registry exists anyway because the Owner's brief asks for
   * rich Arena event cards - a challenge issued, an ingredient attacked, a
   * battle won - rendered inside this same log later. When that arrives it
   * registers its own renderer here and touches nothing else: not absorb(),
   * not poll(), not the scroll behaviour, not this dispatch.
   *
   * DELIBERATELY NO `kind` COLUMN YET. Nothing in the codebase produces a
   * non-message row, so a database field for it would be a column that only
   * ever holds one value - dead weight that still has to be migrated,
   * indexed and reasoned about. The seam is free; the column is not, so the
   * column waits for the feature that needs it. */
  var MESSAGE_RENDERERS = {};

  function renderMessageLine(line) {
    var render = MESSAGE_RENDERERS[line.kind || 'message'] || MESSAGE_RENDERERS.message;
    return render(line);
  }

  /* ONE LINE PER MESSAGE, not a header row followed by a body row.
   *
   * The Owner's visual brief, 2026-08-25: a live Arena feed reads as
   * `22:18 [IRL][GOD]GreenBear ADMIN hello` on one row, wrapping only when
   * the words genuinely need two. `.arena-chat__row` holds every inline
   * piece - time, identity, the words themselves, the action trigger - as
   * flex children of ONE wrapping line; the stylesheet decides how much of
   * that stays inline. On the wide (desktop) container query `said` flexes
   * to fill the remaining width, so short messages truly are one line. On
   * the narrow (mobile) query `said` is forced onto its own line by
   * `flex-basis: 100%` and the pieces are re-ordered by CSS `order` back
   * into the original "header, then words" shape - SAME DOM, so this is a
   * presentation split, not two implementations. The reply quote (its own
   * block, when present) sits above the row; reactions (their own block,
   * when present) sit below it - exactly where they already lived, just
   * outside the new single-line row rather than outside a two-row grid. */
  function renderTextMessage(line) {
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

    var row = document.createElement('span');
    row.className = 'arena-chat__row';

    if (line.at) {
      var when = document.createElement('time');
      when.className = 'arena-chat__time';
      when.setAttribute('datetime', line.at);
      when.textContent = formatTime(line.at);
      // The exact moment stays available to anyone who wants it, without
      // spending a pixel on it.
      when.title = new Date(line.at).toLocaleString();
      row.appendChild(when);
    }

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
    row.appendChild(who);

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
        said.textContent = '';
        paintBody(said, line.heard ? line.body : 'Talking Something');
      });
      said.appendChild(show);
    } else if (line.heard) {
      said.className = 'arena-chat__said';
      paintBody(said, line.body);
    } else {
      // Out of earshot. The person is visibly talking and that is all anyone
      // this far away is entitled to know.
      said.className = 'arena-chat__said arena-chat__said--muffled';
      said.textContent = 'Talking Something';
    }
    row.appendChild(said);

    // One menu component, built on demand - not one menu per message sitting
    // in the DOM waiting to be opened. Own lines get it too: replying to
    // yourself is pointless, but reacting and moderating are not. Last in
    // the row so it settles at the trailing edge (margin-left:auto, wide
    // query) and stays the hover/focus-revealed control it already was.
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

    // THE QUICK-REACT STRIP, revealed the same way the trigger beside it is:
    // hidden until the row is hovered or something inside it takes focus. It
    // is the pointer's shortcut past the action menu, and it exists ONLY
    // where a pointer does - the stylesheet gates it on @media (hover: hover),
    // so a touch reader is never shown five tiny targets they cannot hover
    // to reveal. On touch, reacting stays in the action sheet, where it
    // already lived and where the targets are finger-sized.
    var quick = document.createElement('span');
    quick.className = 'arena-chat__quick-react';
    QUICK_REACTIONS.forEach(function (r) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'arena-chat__quick-react-btn';
      b.setAttribute('aria-label', 'React ' + r.label);
      b.textContent = r.glyph;
      b.addEventListener('click', function (event) {
        event.stopPropagation();
        burst(b);
        react(line.id, r.key);
      });
      quick.appendChild(b);
    });
    row.appendChild(quick);
    row.appendChild(more);

    item.appendChild(row);

    // An attachment sits on its own line UNDER the words, never inline: it is
    // the one part of a message with real height, and threading it through the
    // flex row would fight the density every other rule here defends. A block
    // has already withheld the URL server-side; this is belt and braces.
    if (line.media && !line.blocked) {
      var media = mediaNode(line);
      if (media) { item.appendChild(media); }
    }

    var strip = reactionRow(line);
    if (strip) { item.appendChild(strip); }
    return item;
  }

  /* AN ATTACHMENT, WITH THE BOX RESERVED BEFORE THE BYTES ARRIVE.
   *
   * The server sends the stored file's real width and height, so the figure is
   * given an aspect-ratio up front and the log does not jump under somebody
   * mid-sentence when an image finally decodes. That is the whole reason those
   * two columns exist.
   *
   * ANIMATION IS OPT-OUT, NOT OPT-IN-BY-ACCIDENT. When the reader has turned
   * animated attachments off, the animated file is never requested at all -
   * they are sent the poster frame, which is its own still file, and a play
   * control that swaps in the animation only if they ask for it. Loading the
   * animation and pausing it in CSS would have downloaded every byte they
   * asked not to receive. */
  function mediaNode(line) {
    var m = line.media;
    if (!m || !m.url) { return null; }

    var figure = document.createElement('figure');
    figure.className = 'arena-chat__media arena-chat__media--' + (m.kind || 'image');
    if (m.width && m.height) {
      figure.style.setProperty('--media-ratio', m.width + ' / ' + m.height);
    }

    var img = document.createElement('img');
    img.className = 'arena-chat__media-img';
    img.loading = 'lazy';
    img.decoding = 'async';
    if (m.width) { img.width = m.width; }
    if (m.height) { img.height = m.height; }
    img.alt = m.kind === 'animation'
      ? 'Animation shared by ' + line.name
      : 'Picture shared by ' + line.name;

    var animated = m.kind === 'animation';
    var wantsAnimation = prefs.animatedMedia;
    img.src = (animated && !wantsAnimation && m.poster) ? m.poster : m.url;
    figure.appendChild(img);

    if (animated) {
      var badge = document.createElement('span');
      badge.className = 'arena-chat__media-badge';
      badge.textContent = 'GIF';
      figure.appendChild(badge);
      if (!wantsAnimation && m.poster) {
        // The still is showing; one tap fetches the animation. The badge stops
        // being a label and becomes the control that explains itself.
        figure.classList.add('is-still');
        var play = document.createElement('button');
        play.type = 'button';
        play.className = 'arena-chat__media-play';
        play.setAttribute('aria-label', 'Play this animation');
        play.textContent = '▶';
        play.addEventListener('click', function (event) {
          event.stopPropagation();
          img.src = m.url;
          figure.classList.remove('is-still');
          play.remove();
        });
        figure.appendChild(play);
      }
    }

    // Full size opens in the viewer the whole site already has - one lightbox,
    // not a second one written for this panel. It is a global component from
    // base.html, so it is only used if it is actually present.
    var lightbox = document.getElementById('hero-lightbox');
    if (lightbox) {
      img.classList.add('is-openable');
      img.addEventListener('click', function () { openLightbox(m.url, img.alt); });
    }
    return figure;
  }

  /* The site's own lightbox (templates/base.html:487, static/js/main.js:370),
   * reused rather than reimplemented - a fifth hand-rolled modal in this
   * codebase would be four too many.
   *
   * main.js binds it to HERO images only, and it owns closing it: the close
   * button, Escape and the backdrop are all wired there and work on whatever
   * the element is currently showing. So this opens it the way that file
   * opens it - the same class, the same scroll lock, the same focus move -
   * and deliberately adds no closing logic of its own to compete with. */
  function openLightbox(url, alt) {
    var box = document.getElementById('hero-lightbox');
    var img = document.getElementById('hero-lightbox-img');
    var close = document.getElementById('hero-lightbox-close');
    if (!box || !img) { return; }
    img.src = url;
    img.alt = alt || '';
    box.classList.add('hero-lightbox--open');
    document.body.style.overflow = 'hidden';
    if (close) {
      window.requestAnimationFrame(function () { close.focus(); });
    }
  }

  MESSAGE_RENDERERS.message = renderTextMessage;

  /* ===================================================================
   * P3: THE FIGHT'S OWN MOMENTS, AS CARDS. Owner 2026-08-26.
   *
   * A card is a row in the same log with the same id, so it arrives on the
   * same poll, sits in the same order and scrolls with everything else. What
   * makes it a card is `kind`, decided on the SERVER from a BattleEvent the
   * game recorded for its own reasons - the browser is never the thing that
   * says a challenge was issued.
   *
   * EVERY FIELD PRINTED HERE COMES FROM line.card, which the server built out
   * of the battle. There is no default text for a missing name and no "vs" for
   * a card whose two chefs are unknown: if the payload has nothing to say, the
   * card does not render it. That is the brief's rule - a card renders from
   * real battle state or it does not render.
   * =================================================================== */
  /* Literal characters, like every other mark in this file. The first
     draft wrote them as backslash-u escapes and two of the three came out
     wrong: that escape takes FOUR hex digits, so a codepoint above U+FFFF
     written as one five-digit escape is read as the first four digits plus
     a stray character - it printed a Greek letter and a 3. */
  var CARD_MARKS = {
    challenge_issued: '⚔️',
    voting_open: '🗳️',
    battle_result: '👑',
    ingredient_attack: '🎯',
    defence: '🛡️',
    chef_entered: '👨‍🍳',
    artifact_attack: '🔥',
    artifact_defence: '🛡️'
  };
  var CARD_TITLES = {
    challenge_issued: 'Challenge issued',
    voting_open: 'Voting is open',
    battle_result: 'Result',
    ingredient_attack: 'Struck off',
    defence: 'Blocked',
    chef_entered: 'Entered the Arena',
    artifact_attack: 'Attack lands',
    artifact_defence: 'Defence holds'
  };

  function cardChef(name, slug) {
    /* A chef's name links to the chef when the server sent a slug and is plain
       text when it did not. Building the URL here from a template kept in one
       place - the gift list's own data-profile-template - rather than guessing
       a path this file has no business knowing. */
    var holder = document.createElement(slug ? 'a' : 'b');
    holder.className = 'arena-chat__card-chef';
    holder.textContent = name;
    if (slug) {
      var list = document.getElementById('arena-recent-gifts');
      var template = list && list.getAttribute('data-profile-template');
      holder.href = template
        ? template.replace('arena-chef-slug', encodeURIComponent(slug))
        : '#';
    }
    return holder;
  }

  function renderEventCard(line) {
    var card = line.card || {};
    var kind = line.kind || '';
    var item = document.createElement('li');
    item.className = 'arena-chat__line arena-chat__card arena-chat__card--' + kind;
    item.setAttribute('data-id', line.id);
    item.setAttribute('data-kind', kind);

    var head = document.createElement('span');
    head.className = 'arena-chat__card-head';

    var mark = document.createElement('span');
    mark.className = 'arena-chat__card-mark';
    mark.setAttribute('aria-hidden', 'true');
    mark.textContent = CARD_MARKS[kind] || '';
    head.appendChild(mark);

    var title = document.createElement('b');
    title.className = 'arena-chat__card-title';
    title.textContent = CARD_TITLES[kind] || '';
    head.appendChild(title);

    if (line.at) {
      var when = document.createElement('time');
      when.className = 'arena-chat__time';
      when.setAttribute('datetime', line.at);
      when.textContent = formatTime(line.at);
      when.title = new Date(line.at).toLocaleString();
      head.appendChild(when);
    }
    item.appendChild(head);

    /* THE TWO CHEFS, when the server knows them. A result card names the
       winner first and says so; the other two cards read left to right in the
       order the battle itself is written. */
    if (card.challenger && card.opponent) {
      var pair = document.createElement('span');
      pair.className = 'arena-chat__card-pair';
      if (kind === 'battle_result' && card.winner) {
        pair.appendChild(cardChef(card.winner, card.winner_slug));
        var beat = document.createElement('span');
        beat.className = 'arena-chat__card-vs';
        beat.textContent = 'beat';
        pair.appendChild(beat);
        pair.appendChild(cardChef(
          card.winner === card.challenger ? card.opponent : card.challenger,
          ''
        ));
      } else if (kind === 'ingredient_attack' || kind === 'defence') {
        /* A SHOT IS NOT THE BATTLE'S PAIRING. Only the winner of the first
           round shoots, and he shoots at ONE named chef's menu, so the line
           that matters is shooter to defender - "challenger vs opponent"
           would be true and would say nothing about what just happened. */
        pair.appendChild(cardChef(card.actor, card.actor_slug));
        var at = document.createElement('span');
        at.className = 'arena-chat__card-vs';
        at.textContent = kind === 'defence' ? 'blocked by' : 'hit';
        pair.appendChild(at);
        pair.appendChild(cardChef((card.event || {}).defender || '', ''));
      } else {
        pair.appendChild(cardChef(card.challenger, ''));
        var vs = document.createElement('span');
        vs.className = 'arena-chat__card-vs';
        vs.textContent = 'vs';
        pair.appendChild(vs);
        pair.appendChild(cardChef(card.opponent, ''));
      }
      item.appendChild(pair);
    }

    /* THE BIATHLON'S OWN LINE: which ingredient, off whose menu, and which of
       the three shots this was. Printed from the event's payload rather than
       parsed out of the sentence - the sentence is English and the card is
       not, so a card that read it would break the day the wording changes. */
    /* An arrival names the chef and the rank they walked in wearing. It has
       no battle and therefore no pair, no sentence beyond its own and nowhere
       to send the reader but the chef. */
    if (kind === 'chef_entered') {
      var arrival = document.createElement('span');
      arrival.className = 'arena-chat__card-pair';
      arrival.appendChild(cardChef(card.actor, card.actor_slug));
      if (card.rank) {
        var rank = document.createElement('span');
        rank.className = 'arena-chat__card-vs';
        rank.textContent = card.rank;
        arrival.appendChild(rank);
      }
      item.appendChild(arrival);
      return item;
    }

    /* ROUND ONE: THE ARTIFACT DUEL. Its card is built from the round rather
       than from an event, because combat rounds write no events - BattleRound
       already carries the attacker, the defender, both powers and the outcome,
       and the two actions beside it carry the artifacts. It reads as a line
       about weapons, which is what the round is, with the ingredient that fell
       as the consequence rather than the headline. */
    if (kind === 'artifact_attack' || kind === 'artifact_defence') {
      var duel = document.createElement('span');
      duel.className = 'arena-chat__card-pair';
      duel.appendChild(cardChef(card.attacker, card.attacker_slug));
      var verb = document.createElement('span');
      verb.className = 'arena-chat__card-vs';
      verb.textContent = card.outcome + ' on';
      duel.appendChild(verb);
      duel.appendChild(cardChef(card.defender, ''));
      item.appendChild(duel);

      /* The weapons, each named only if it was actually played - a chef may
         fight on Move points alone and the card says nothing rather than
         inventing a bare hand. */
      [['attack_artifact', 'attacked with'], ['defence_artifact', 'defended with']]
        .forEach(function (pair) {
          var art = card[pair[0]];
          if (!art) { return; }
          var row = document.createElement('span');
          row.className = 'arena-chat__card-shot';
          var role = document.createElement('span');
          role.className = 'arena-chat__card-vs';
          role.textContent = pair[1];
          row.appendChild(role);
          var named = document.createElement('b');
          named.textContent = art.name;
          row.appendChild(named);
          if (art.rarity) {
            var rarity = document.createElement('span');
            rarity.className = 'arena-chat__card-count';
            rarity.textContent = art.rarity;
            row.appendChild(rarity);
          }
          item.appendChild(row);
        });

      var tally = document.createElement('span');
      tally.className = 'arena-chat__card-shot';
      var power = document.createElement('span');
      power.className = 'arena-chat__card-count';
      power.textContent = 'round ' + card.round + ' · ' +
        card.attack_power + ' vs ' + card.defence_power;
      tally.appendChild(power);
      if (card.struck) {
        var fell = document.createElement('b');
        fell.textContent = card.struck + ' struck off';
        tally.appendChild(fell);
      }
      item.appendChild(tally);

      if (card.battle_url) {
        var watch = document.createElement('a');
        watch.className = 'arena-chat__card-go';
        watch.href = card.battle_url;
        watch.textContent = 'Watch the fight';
        item.appendChild(watch);
      }
      return item;
    }

    var ev = card.event || {};
    if (ev.ingredient) {
      var shot = document.createElement('span');
      shot.className = 'arena-chat__card-shot';
      var what = document.createElement('b');
      what.textContent = ev.ingredient;
      shot.appendChild(what);
      if (ev.shot_number && ev.shots_total) {
        var count = document.createElement('span');
        count.className = 'arena-chat__card-count';
        count.textContent = 'shot ' + ev.shot_number + ' of ' + ev.shots_total;
        shot.appendChild(count);
      }
      item.appendChild(shot);
    }

    /* THE SENTENCE IS SKIPPED WHERE THE CARD ALREADY SAYS IT. A shot card
       carries the title, the two chefs and the ingredient; the event's English
       ("Aoife's shot hit 'Wild garlic'.") then repeats all three in prose, and
       measured, that is a third of the card's height spent saying nothing new.
       The other kinds keep it - their sentence carries the theme and the
       margin, which nothing else on the card states. */
    var repeats = (kind === 'ingredient_attack' || kind === 'defence');

    /* The event's own sentence, which is what the game wrote when it happened.
       textContent and never innerHTML: this string is a chef's name inside a
       server-formatted message, and a name is user input wherever it came
       from. */
    if (card.headline && !repeats) {
      var said = document.createElement('span');
      said.className = 'arena-chat__card-said';
      said.textContent = card.headline;
      item.appendChild(said);
    }

    /* NO LIVE VOTE NUMBERS ON THE VOTING CARD, and the reason is that a chat
       line is a moment rather than a dashboard: it is written once and never
       re-rendered, so a tally printed here would be wrong within seconds and
       would look authoritative while it was. The card invites the reader to
       the battle page, which carries the counts and keeps them current. (The
       rules were checked rather than assumed: tz_main 8.5 sets no
       hidden-until-close rule, and battle_detail.html has always shown live
       counts during VOTING - so this is a staleness decision, not a secrecy
       one.) */
    if (card.battle_url) {
      var go = document.createElement('a');
      go.className = 'arena-chat__card-go';
      go.href = card.battle_url;
      go.textContent = kind === 'voting_open' ? 'Go and vote' : 'Open the battle';
      item.appendChild(go);
    }
    return item;
  }

  MESSAGE_RENDERERS.challenge_issued = renderEventCard;
  MESSAGE_RENDERERS.voting_open = renderEventCard;
  MESSAGE_RENDERERS.battle_result = renderEventCard;
  MESSAGE_RENDERERS.ingredient_attack = renderEventCard;
  MESSAGE_RENDERERS.defence = renderEventCard;
  MESSAGE_RENDERERS.chef_entered = renderEventCard;
  MESSAGE_RENDERERS.artifact_attack = renderEventCard;
  MESSAGE_RENDERERS.artifact_defence = renderEventCard;


  function append(line) {
    var item = renderMessageLine(line);
    if (!item) { return; }
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
      // The reaction SUMMARY strip above the composer sums this attribute
      // across every currently-loaded message rather than keeping a second
      // running total in JS - the DOM already holds the real counts and
      // stays the one source of truth for "what's currently loaded".
      btn.setAttribute('data-count', state.count);
      btn.setAttribute('aria-pressed', state.mine ? 'true' : 'false');
      btn.setAttribute('aria-label', r.label + ' (' + state.count + ')');
      btn.textContent = r.glyph + ' ' + state.count;
      btn.addEventListener('click', function () { burst(btn); react(line.id, r.key); });
      row.appendChild(btn);
    });
    return row;
  }

  /* A short lift-and-fade on the glyph that was tapped, so a reaction lands
   * with some feedback instead of a silent number change.
   *
   * THREE THINGS CAN SWITCH IT OFF, and all three are honoured: the reader's
   * own "Reaction animations" preference, the OS-level prefers-reduced-motion
   * (enforced in the stylesheet, which is where it belongs - this function
   * only adds a class, and the keyframes it names simply do not exist under
   * that query), and the absence of the element itself. */
  function burst(el) {
    if (!el || !prefs.reactionAnimations) { return; }
    el.classList.remove('is-bursting');
    // Reading offsetWidth restarts the animation when the same glyph is
    // tapped twice quickly - without it the class is already there and
    // nothing replays.
    void el.offsetWidth;
    el.classList.add('is-bursting');
    window.setTimeout(function () { el.classList.remove('is-bursting'); }, 700);
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
      renderReactionSummary();
    });
  }

  /* THE HALL'S REACTION SUMMARY - real counts, summed from what is actually
   * loaded, never a second store to keep in sync. Read straight off the
   * data-count attribute reactionRow() already writes on every visible
   * reaction button, so a message scrolled out of the loaded window (there
   * is no such window today, but if paging arrives later) or one whose
   * strip just changed under react() is picked up on the next recompute
   * with no extra bookkeeping. Passive - a display, not a second place to
   * react from: a tap here would have no single message to land on. */
  function sumReactions() {
    var totals = {};
    REACTIONS.forEach(function (r) { totals[r.key] = 0; });
    var buttons = log.querySelectorAll('.arena-chat__react');
    for (var i = 0; i < buttons.length; i++) {
      var key = buttons[i].getAttribute('data-emoji');
      var count = parseInt(buttons[i].getAttribute('data-count'), 10) || 0;
      if (key in totals) { totals[key] += count; }
    }
    return totals;
  }

  function renderReactionSummary() {
    var el = document.getElementById('arena-chat-reaction-summary');
    if (!el) { return; }
    var totals = sumReactions();
    var shown = REACTIONS.filter(function (r) { return totals[r.key] > 0; });
    el.innerHTML = '';
    if (!shown.length) { el.hidden = true; return; }
    el.hidden = false;
    shown.forEach(function (r) {
      var chip = document.createElement('span');
      chip.className = 'arena-chat__reaction-total';
      chip.setAttribute('aria-label', r.label + ': ' + totals[r.key]);
      chip.textContent = r.glyph + ' ' + totals[r.key];
      el.appendChild(chip);
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
      openChefCard(line.slug, trigger);
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

  /* THE CHEF CARD - who this is, before deciding whether to answer them.
   *
   * The brief asks for a hover card on a desktop and a bottom sheet on a
   * phone. That is the split .arena-chat__sheet already makes from the
   * panel's own width, so this is that sheet again rather than a third
   * presentation, and it opens on a CLICK on both: a card that appears on
   * hover in a dense log is a card that appears constantly.
   *
   * "View profile" now opens this instead of navigating away. Leaving the
   * arena to read three numbers - and losing your place in a live
   * conversation to do it - was the wrong trade; the full page is still one
   * click further on, from the card's own link. */
  function openChefCard(slug, trigger) {
    if (!slug) { return; }
    var url = root.getAttribute('data-profile-url-template');
    if (!url) { return; }
    fetch(url.replace('__slug__', encodeURIComponent(slug)), { credentials: 'same-origin' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) { notice('That chef could not be found.'); return; }
        closeActions();
        var sheet = document.createElement('div');
        sheet.className = 'arena-chat__sheet arena-chat__sheet--chef';
        sheet.setAttribute('role', 'dialog');
        sheet.setAttribute('aria-label', 'Chef ' + data.name);

        var head = document.createElement('p');
        head.className = 'arena-chat__chef-name';
        var alliance = tagBadge(data.alliance_tag, 'alliance');
        if (alliance) { head.appendChild(alliance); }
        var clan = tagBadge(data.clan_tag, 'clan');
        if (clan) { head.appendChild(clan); }
        var nm = document.createElement('span');
        nm.textContent = data.name;
        head.appendChild(nm);
        if (data.role === 'admin') { head.appendChild(marker('Admin', 'admin')); }
        else if (data.role === 'moderator') { head.appendChild(marker('Mod', 'mod')); }
        sheet.appendChild(head);

        if (!data.enrolled) {
          // A spectator has no record, and zeroes would read as one.
          var none = document.createElement('p');
          none.className = 'arena-chat__chef-none';
          none.textContent = 'Watching from the stands - not enrolled as a chef.';
          sheet.appendChild(none);
        } else {
          var rank = document.createElement('p');
          rank.className = 'arena-chat__chef-rank';
          rank.textContent = data.rank;
          if (data.wears_crown) {
            var crown = document.createElement('span');
            crown.className = 'arena-chat__chef-crown';
            crown.title = 'Wearing the crown right now';
            crown.textContent = '👑';
            rank.appendChild(crown);
          }
          sheet.appendChild(rank);

          var stats = document.createElement('dl');
          stats.className = 'arena-chat__chef-stats';
          [['Wins', data.wins], ['Losses', data.losses],
           ['Streak', data.streak], ['Crowns', data.crowns]].forEach(function (pair) {
            var dt = document.createElement('dt');
            dt.textContent = pair[0];
            var dd = document.createElement('dd');
            dd.textContent = String(pair[1]);
            stats.appendChild(dt);
            stats.appendChild(dd);
          });
          sheet.appendChild(stats);

          var link = document.createElement('a');
          link.className = 'arena-chat__chef-link';
          link.href = data.profile_url;
          link.textContent = 'View full profile';
          sheet.appendChild(link);
        }

        root.appendChild(sheet);
        openMenu = sheet;
        anchorSheet(sheet, trigger);
      })
      .catch(function () { notice('That chef could not be found.'); });
  }

  /* THE EMOJI PICKER, built on the SAME sheet the action menu uses.
   *
   * Not a second popover system: it takes .arena-chat__sheet's class family,
   * so it is an anchored popover on a wide panel and a real bottom sheet on
   * a narrow one, for free, from the container query already in the
   * stylesheet. openMenu holds it too, so the existing outside-click and
   * Escape handlers close it without knowing it exists. */
  var emojiCategory = EMOJI_CATEGORIES[0].key;

  function openEmojiPicker(trigger) {
    if (openMenu && openMenu.classList.contains('arena-chat__sheet--emoji')) {
      closeActions();
      return;                                     // a second tap closes it
    }
    closeActions();
    var sheet = document.createElement('div');
    sheet.className = 'arena-chat__sheet arena-chat__sheet--emoji';
    sheet.setAttribute('role', 'dialog');
    sheet.setAttribute('aria-label', 'Choose an emoji');

    var tabs = document.createElement('div');
    tabs.className = 'arena-chat__emoji-tabs';
    var grid = document.createElement('div');
    grid.className = 'arena-chat__emoji-grid';

    function paintGrid() {
      grid.textContent = '';
      var cat = null;
      EMOJI_CATEGORIES.forEach(function (c) { if (c.key === emojiCategory) { cat = c; } });
      if (!cat) { return; }
      if (cat.custom) {
        CUSTOM_EMOJI.forEach(function (e) {
          var b = document.createElement('button');
          b.type = 'button';
          b.className = 'arena-chat__emoji-btn arena-chat__emoji-btn--custom';
          b.setAttribute('aria-label', e.label);
          b.title = e.label;
          var node = customEmojiNode(e.token);
          if (node) { b.appendChild(node); }
          b.addEventListener('click', function () {
            // The TOKEN goes into the message, never the drawing - see
            // CUSTOM_EMOJI's own note on why.
            insertAtCursor(':' + e.token + ':');
          });
          grid.appendChild(b);
        });
        return;
      }
      cat.glyphs.forEach(function (glyph) {
        if (!glyph) { return; }
        var b = document.createElement('button');
        b.type = 'button';
        b.className = 'arena-chat__emoji-btn';
        b.setAttribute('aria-label', glyph);
        b.textContent = glyph;
        b.addEventListener('click', function () { insertAtCursor(glyph); });
        grid.appendChild(b);
      });
    }

    EMOJI_CATEGORIES.forEach(function (cat) {
      var t = document.createElement('button');
      t.type = 'button';
      t.className = 'arena-chat__emoji-tab';
      t.textContent = cat.label;
      t.setAttribute('aria-pressed', cat.key === emojiCategory ? 'true' : 'false');
      t.addEventListener('click', function () {
        emojiCategory = cat.key;
        Array.prototype.forEach.call(
          tabs.querySelectorAll('.arena-chat__emoji-tab'),
          function (other) { other.setAttribute('aria-pressed', 'false'); }
        );
        t.setAttribute('aria-pressed', 'true');
        paintGrid();
      });
      tabs.appendChild(t);
    });

    paintGrid();
    sheet.appendChild(tabs);
    sheet.appendChild(grid);
    root.appendChild(sheet);
    openMenu = sheet;
    anchorSheet(sheet, trigger);
  }

  /* Where a sheet opens, when it was opened by a control rather than a line.
   * Same custom properties the action menu writes, so the same stylesheet
   * rules place it - and the same rules ignore them on a narrow panel. */
  function anchorSheet(sheet, trigger) {
    if (!trigger) { return; }
    var box = trigger.getBoundingClientRect();
    var mine = root.getBoundingClientRect();
    // Above the trigger, because the composer sits at the panel's foot and
    // there is nothing below it to open into.
    sheet.style.setProperty('--sheet-top', Math.max(0, box.top - mine.top - 232) + 'px');
    sheet.style.setProperty('--sheet-left', Math.max(0, box.left - mine.left - 120) + 'px');
  }

  /* Insert at the CARET, not at the end. Typing a sentence, moving back to
   * fix a word and adding an emoji there is ordinary behaviour; appending to
   * the end regardless would be a small daily annoyance. */
  function insertAtCursor(text) {
    if (!input) { return; }
    var start = typeof input.selectionStart === 'number' ? input.selectionStart : input.value.length;
    var end = typeof input.selectionEnd === 'number' ? input.selectionEnd : input.value.length;
    var before = input.value.slice(0, start);
    var after = input.value.slice(end);
    input.value = before + text + after;
    var caret = start + text.length;
    input.focus();
    try { input.setSelectionRange(caret, caret); } catch (e) { /* older engines */ }
    // Programmatic value changes fire no 'input' event, and the send button's
    // disabled state listens for exactly that.
    if (typeof syncSendButton === 'function') { syncSendButton(); }
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
      clearLog();
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
      clearLog();
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
    clearLog();
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
    renderReactionSummary();
  }

  function seatMe(seated) {
    if (form) { form.hidden = !seated; }
    // The placeholder agrees with whether the composer is actually usable.
    // It shipped saying "Take a seat to join the conversation" to EVERYONE,
    // so a chef - who holds a place in the octagon and needs no seat - read
    // an instruction he could not follow.
    if (empty && empty.parentNode) {
      empty.textContent = seated
        ? 'Nobody has spoken yet.'
        : 'Take a seat to join the conversation.';
    }
  }

  /* The hall's headcount, written into the USERS tab label as "Users (n)".
   *
   * Owner's visual brief, 2026-08-25: a separate "LIVE n" badge duplicated
   * this exact number and competed with the tabs for attention. There is
   * one count now, living where a reader would look for it - the same
   * number the arena_chat_users list itself would enumerate, since both
   * ultimately read _arena_hall_headcount()'s definition of who is present. */
  function setUsersCount(count) {
    var el = document.getElementById('arena-chat-tab-users-count');
    if (!el) { return; }
    el.textContent = (typeof count === 'number' && count >= 0) ? '(' + count + ')' : '';
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
        setUsersCount(room === null ? data.listening : null);
        absorb(data.messages);
      })
      .catch(function () { /* one dropped tick is not a failure; try the next */ })
      .then(function () { busy = false; });
  }

  function send() {
    var text = input.value.trim();
    // A picture on its own is a message. The server agrees - it refuses only
    // when BOTH are missing - so the two checks say the same thing.
    if (!text && !pendingMedia) { return; }
    var body = new FormData();
    body.append('body', text);
    if (pendingMedia) { body.append('media', pendingMedia); }
    if (replyingTo) { body.append('reply_to', replyingTo.id); }
    if (room !== null) { body.append('conversation', room); }
    body.append('csrfmiddlewaretoken', csrf());
    var sentMedia = pendingMedia;
    clearPendingMedia();
    input.value = '';
    input.focus();
    // Setting .value programmatically fires no 'input' event, so the
    // disabled state - which listens for that event - is nudged by hand
    // here and everywhere else the box is filled or emptied in code.
    if (typeof syncSendButton === 'function') { syncSendButton(); }
    cancelReply();
    fetch(sendUrl, { method: 'POST', credentials: 'same-origin', body: body })
      .then(function (response) { return response.json(); })
      .then(function (data) {
        if (data && data.ok) {
          absorb(data.messages);
        } else {
          input.value = text;
          // The attachment comes back too - it was refused or lost, and
          // making somebody find the file again is the rudest possible way
          // to report that.
          if (sentMedia) { setPendingMedia(sentMedia); }
          if (typeof syncSendButton === 'function') { syncSendButton(); }
          // The server's own words when it refused the FILE: "too many
          // frames" and "not an image" are different problems and the reader
          // can act on the difference.
          notice(
            (data && data.error === 'bad_media' && data.detail) ? data.detail
              : (data && data.error === 'rate_limited') ? 'Slow down a moment.'
              : 'That did not send.'
          );
        }
      })
      .catch(function () {
        input.value = text;                          // put it back, lose nothing
        if (sentMedia) { setPendingMedia(sentMedia); }
        if (typeof syncSendButton === 'function') { syncSendButton(); }
        notice('That did not send.');
      });
  }

  /* THE ATTACHMENT WAITING TO GO. Held here rather than left in the file
   * input, because the input is cleared on every pick so that choosing the
   * same file twice in a row still fires a change event. */
  var pendingMedia = null;

  function setPendingMedia(file) {
    pendingMedia = file || null;
    var bar = document.getElementById('arena-chat-attachment');
    var name = document.getElementById('arena-chat-attachment-name');
    var preview = document.getElementById('arena-chat-attachment-preview');
    if (!bar) { return; }
    bar.hidden = !pendingMedia;
    if (!pendingMedia) {
      if (preview && preview.src) { URL.revokeObjectURL(preview.src); preview.removeAttribute('src'); }
      if (typeof syncSendButton === 'function') { syncSendButton(); }
      return;
    }
    if (name) { name.textContent = pendingMedia.name; }
    if (preview) {
      // A local preview, so nothing is uploaded until Send is pressed.
      if (preview.src) { URL.revokeObjectURL(preview.src); }
      preview.src = URL.createObjectURL(pendingMedia);
    }
    if (typeof syncSendButton === 'function') { syncSendButton(); }
  }

  function clearPendingMedia() { setPendingMedia(null); }

  if (form) {
    form.addEventListener('submit', function (event) {
      event.preventDefault();
      send();
    });
  }

  // The send button's disabled state, kept live: an empty box has nothing
  // to send, so the gold control says so rather than accepting a click that
  // send() would have thrown away anyway.
  var sendButton = form && form.querySelector('button[type="submit"]');
  if (input && sendButton) {
    var syncSendButton = function () {
      sendButton.disabled = !input.value.trim() && !pendingMedia;
    };
    input.addEventListener('input', syncSendButton);
    syncSendButton();
  }

  /* PHOTO / GIF. The composer's action row was built for exactly this - see
   * arena.html's note there - so this is a second button beside the emoji one
   * rather than a "+" menu. Nothing is uploaded on picking: the file waits in
   * pendingMedia and travels with the message when Send is pressed, so
   * abandoning a half-written line leaves no orphan on disk. */
  var mediaInput = document.getElementById('arena-chat-media-input');
  var mediaButton = document.getElementById('arena-chat-media');
  if (mediaButton && mediaInput) {
    mediaButton.addEventListener('click', function () { mediaInput.click(); });
    mediaInput.addEventListener('change', function () {
      var file = mediaInput.files && mediaInput.files[0];
      // Cleared straight away so picking the SAME file twice still fires.
      mediaInput.value = '';
      if (!file) { return; }
      // A courtesy check only - the ceiling that counts is enforced in
      // normalise_uploaded_chat_media, where the browser cannot reach it.
      if (file.size > 5 * 1024 * 1024) {
        notice('Attachments must be 5 MB or smaller.');
        return;
      }
      setPendingMedia(file);
      input.focus();
    });
  }
  var dropAttachment = document.getElementById('arena-chat-attachment-remove');
  if (dropAttachment) { dropAttachment.addEventListener('click', clearPendingMedia); }

  var emojiButton = document.getElementById('arena-chat-emoji');
  if (emojiButton) {
    emojiButton.addEventListener('click', function (event) {
      event.stopPropagation();
      openEmojiPicker(emojiButton);
    });
  }

  /* @MENTION AUTOCOMPLETE.
   *
   * The candidates are the roster arena_chat_users already returns for the
   * USERS tab - one endpoint, fetched once per session, shared by both. A
   * mention that offered names nobody in the hall recognises would be a
   * worse feature than none.
   *
   * The dropdown reuses the sheet family for the same reason the emoji
   * picker does, and registers in openMenu so Escape and outside-click
   * already close it. */
  var mentionOpen = false;
  var mentionFrom = -1;
  var mentionIndex = 0;
  var mentionMatches = [];

  function ensureRoster() {
    if (rosterFetched) { return Promise.resolve(roster); }
    var url = root.getAttribute('data-users-url');
    if (!url) { return Promise.resolve(roster); }
    return fetch(url, { credentials: 'same-origin' })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        roster = (data && data.users) || [];
        rosterFetched = true;
        return roster;
      })
      .catch(function () { return roster; });
  }

  /* The "@word" the caret is currently sitting inside, or null. Anchored to a
   * word boundary so an email address never opens the dropdown. */
  function mentionQueryAtCaret() {
    if (!input) { return null; }
    var caret = typeof input.selectionStart === 'number' ? input.selectionStart : input.value.length;
    var upto = input.value.slice(0, caret);
    var at = upto.lastIndexOf('@');
    if (at < 0) { return null; }
    if (at > 0 && !/\s/.test(upto.charAt(at - 1))) { return null; }
    var typed = upto.slice(at + 1);
    if (/\s/.test(typed)) { return null; }        // the mention ended already
    return { from: at, text: typed };
  }

  function closeMentions() {
    if (openMenu && openMenu.classList.contains('arena-chat__sheet--mentions')) {
      closeActions();
    }
    mentionOpen = false;
    mentionMatches = [];
    mentionIndex = 0;
  }

  function paintMentions() {
    closeActions();
    if (!mentionMatches.length) { mentionOpen = false; return; }
    var sheet = document.createElement('div');
    sheet.className = 'arena-chat__sheet arena-chat__sheet--mentions';
    sheet.setAttribute('role', 'listbox');
    sheet.setAttribute('aria-label', 'Mention a chef');
    mentionMatches.forEach(function (user, i) {
      var b = document.createElement('button');
      b.type = 'button';
      b.className = 'arena-chat__mention-option' + (i === mentionIndex ? ' is-active' : '');
      b.setAttribute('role', 'option');
      b.setAttribute('aria-selected', i === mentionIndex ? 'true' : 'false');
      var alliance = tagBadge(user.alliance_tag, 'alliance');
      if (alliance) { b.appendChild(alliance); }
      var clan = tagBadge(user.clan_tag, 'clan');
      if (clan) { b.appendChild(clan); }
      var nm = document.createElement('span');
      nm.className = 'arena-chat__name';
      nm.textContent = user.name;
      b.appendChild(nm);
      b.addEventListener('click', function () { chooseMention(user); });
      sheet.appendChild(b);
    });
    root.appendChild(sheet);
    openMenu = sheet;
    mentionOpen = true;
    anchorSheet(sheet, input);
  }

  function chooseMention(user) {
    if (!input || mentionFrom < 0) { return; }
    var caret = typeof input.selectionStart === 'number' ? input.selectionStart : input.value.length;
    var before = input.value.slice(0, mentionFrom);
    var after = input.value.slice(caret);
    var insert = '@' + user.name + ' ';
    input.value = before + insert + after;
    var pos = before.length + insert.length;
    input.focus();
    try { input.setSelectionRange(pos, pos); } catch (e) { /* older engines */ }
    if (typeof syncSendButton === 'function') { syncSendButton(); }
    closeMentions();
  }

  function refreshMentions() {
    var q = mentionQueryAtCaret();
    if (!q) { closeMentions(); return; }
    mentionFrom = q.from;
    ensureRoster().then(function (list) {
      // Still the same word after the fetch? A slow network must not reopen
      // a dropdown for something the reader has already finished typing.
      var still = mentionQueryAtCaret();
      if (!still || still.from !== mentionFrom) { return; }
      var needle = still.text.toLowerCase();
      mentionMatches = list.filter(function (u) {
        return String(u.name).toLowerCase().indexOf(needle) === 0;
      }).slice(0, 6);
      mentionIndex = 0;
      paintMentions();
    });
  }

  if (input) {
    input.addEventListener('input', refreshMentions);
    input.addEventListener('keydown', function (event) {
      if (!mentionOpen || !mentionMatches.length) { return; }
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        mentionIndex = (mentionIndex + (event.key === 'ArrowDown' ? 1 : -1) + mentionMatches.length)
                        % mentionMatches.length;
        paintMentions();
      } else if (event.key === 'Enter' || event.key === 'Tab') {
        // Enter completes the mention rather than sending the line - the
        // dropdown is open, so that is plainly what Enter means right now.
        event.preventDefault();
        chooseMention(mentionMatches[mentionIndex]);
      } else if (event.key === 'Escape') {
        event.preventDefault();
        closeMentions();
      }
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
        // ONE ROSTER, TWO READERS. The mention dropdown wants exactly this
        // list, so opening the USERS tab warms it and vice versa - neither
        // feature fetches a second time for what the other already has.
        roster = users;
        rosterFetched = true;
        list.innerHTML = '';
        // The tab's own label is authoritative the moment this list has
        // actually loaded - it may briefly disagree with the poll's
        // listening count between one 4s tick and the next, never for long.
        setUsersCount(users.length);
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

  /* APPEARANCE, which saves ITSELF and posts nothing.
   *
   * No Save button on purpose: there is no round trip to wait for and no
   * failure to report, so a control that changes the log the instant it is
   * touched is the honest UI. dm_policy above keeps its button because that
   * one really does travel to the server and really can be refused. */
  var appearanceForm = document.getElementById('arena-chat-appearance-form');
  if (appearanceForm) {
    var paintAppearance = function () {
      appearanceForm.querySelectorAll('input[type="radio"]').forEach(function (el) {
        el.checked = String(prefs[el.name]) === el.value;
      });
      appearanceForm.querySelectorAll('input[type="checkbox"]').forEach(function (el) {
        el.checked = !!prefs[el.name];
      });
    };
    appearanceForm.addEventListener('change', function (event) {
      var el = event.target;
      if (!el || !el.name || !(el.name in PREF_DEFAULTS)) { return; }
      prefs[el.name] = (el.type === 'checkbox') ? el.checked : el.value;
      writePrefs();
      applyPersonalisation();
    });
    paintAppearance();
  }
  applyPersonalisation();

  for (var t = 0; t < tabs.length; t++) {
    tabs[t].addEventListener('click', function (event) {
      activateTab(event.currentTarget.getAttribute('data-tab'));
    });
  }

  /* Pinned Rules - EXPANDED by default (Owner's visual brief, 2026-08-25),
   * unless this tab's own session explicitly remembers the reader closed
   * it. sessionStorage carries three states, not two: never touched (open),
   * '1' (reader opened it - already open, a no-op), '0' (reader closed it -
   * stay closed). A missing key must read as "never decided", not as
   * "decided closed", or the default could never actually take effect. */
  var rulesToggle = document.getElementById('arena-chat-rules-toggle');
  var rulesBody = document.getElementById('arena-chat-rules-body');
  if (rulesToggle && rulesBody) {
    var RULES_KEY = 'arena-chat-rules-open';
    function paintRules(open) {
      rulesToggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      rulesBody.hidden = !open;
    }
    var storedRulesState = window.sessionStorage && window.sessionStorage.getItem(RULES_KEY);
    paintRules(storedRulesState === null || storedRulesState === undefined
      ? true
      : storedRulesState === '1');
    rulesToggle.addEventListener('click', function () {
      var open = rulesToggle.getAttribute('aria-expanded') !== 'true';
      paintRules(open);
      if (window.sessionStorage) {
        window.sessionStorage.setItem(RULES_KEY, open ? '1' : '0');
      }
    });
  }

  /* THE ROSTER IS FETCHED BEFORE THE FIRST PAINT, not lazily on the first
   * "@" typed, and that ordering is the whole point: a mention only
   * highlights for somebody resolveMention() can find, so a log painted
   * while the roster is still empty renders every mention in it as plain
   * text and never revisits them. Chaining the first poll behind the fetch
   * costs one request at startup - the same request the USERS tab would
   * have made anyway, cached for both - and is the difference between
   * mentions working on arrival and working only after you type one.
   *
   * The interval is NOT chained: poll()'s own `busy` guard already stops a
   * second tick from overlapping the first. */
  ensureRoster().then(poll, poll);
  setInterval(poll, POLL_MS);
})();
