(() => {
  "use strict";

  const hero = document.querySelector("main .hero");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!hero || sessionStorage.getItem("heroChefDismissed") === "1") {
    return;
  }

  // Pinch's phrase pool — weighted; higher weight = appears more often in deck
  const messages = [
    // search hints
    { text: "Tap me to open the search box!", weight: 6 },
    { text: "Ask me what you’re looking for!", weight: 5 },
    // intro / guide
    { text: "Hello! My name is Pinch — and I’m a bear!", weight: 4 },
    { text: "I’m not just a green bear — I’m your guide around the site!", weight: 5 },
    { text: "There is a whole Pinch section on this site — and it’s brilliant!", weight: 4 },
    // welcome
    { text: "Welcome to CulinEire!", weight: 3 },
    { text: "Hello!", weight: 2 },
    { text: "What’s cooking?", weight: 2 },
    // support / sponsors
    { text: "I can’t take tips — but you can buy me a coffee! ☕", weight: 2, url: "https://buymeacoffee.com/bearcave" },
    { text: "I don’t accept tips. Buy me a coffee instead! ☕", weight: 1, url: "https://buymeacoffee.com/bearcave" },
    { text: "Visit our Sponsors page and help keep CulinEire growing!", weight: 4, url: "/sponsors/" },
    { text: "Even a small bit of support helps keep Bearcave growing.", weight: 2 },
    // bearcave story
    { text: "Did you know I live in Bearcave?", weight: 4 },
    { text: "Bearcave is not just a name — it is a whole story I want to share with you!", weight: 5 },
    { text: "Bearcave is not just a name. It is a place, a story, and a beginning.", weight: 5 },
    // about
    { text: "CulinEire is a one-person project, built with heart.", weight: 4 },
    { text: "Bearcave is built by one chef, one trailer, and a lot of late nights.", weight: 4 },
    { text: "Every recipe, every story, and every line of code here comes from one person.", weight: 4 },
    // culineire
    { text: "CulinEire bridges technology and gastronomy.", weight: 4 },
    { text: "CulinEire is where Irish food, stories, and technology meet.", weight: 5 },
    { text: "Cooking knowledge should be useful, but it should never be boring.", weight: 5 },
    { text: "Chef Battles, Fridge Raids, recipes, stories — there is always something cooking here.", weight: 4 },
    // brand voice
    { text: "Real food deserves real knowledge.", weight: 5 },
    { text: "CulinEire stands on real culinary knowledge, not just passion.", weight: 4 },
    { text: "No shortcuts. Not in the kitchen, not on the site.", weight: 5 },
    { text: "Built slowly. Built properly. Built with heart.", weight: 5 },
    { text: "This site is built the same way good food is cooked: carefully, properly, and with no shortcuts.", weight: 4 },
    { text: "Between the trailer and the code, something tasty is always happening.", weight: 4 },
    { text: "We are building CulinEire for you — to bring a little warmth to your table.", weight: 5 },
    // trailer story
    { text: "Bearcave began as a black trailer with its own character.", weight: 3 },
    { text: "The Bearcave trailer took three years to build by hand.", weight: 3 },
    { text: "This trailer had a past — now it has a new story.", weight: 3 },
    { text: "Once, this trailer taught fire safety. Now, it serves food with soul.", weight: 4 },
    { text: "From fire safety to food heritage — that is the Bearcave story.", weight: 4 },
    // cooking tips
    { text: "Mind the hot pan!", weight: 2 },
    { text: "A sharp knife is safer than a dull one.", weight: 2 },
    { text: "Sharp knife, steady hand.", weight: 2 },
    // fun
    { text: "My favourite chef is whoever feeds me.", weight: 2 },
    { text: "I never pick favourites. Unless there is cake.", weight: 2 },
    { text: "Scrambled eggs still count as training.", weight: 2 },
    // battle
    { text: "Think you can cook it better? Prove it!", weight: 3 },
    { text: "You can’t even make scrambled eggs?", weight: 1 },
    // irish heritage
    { text: "Some of Ireland’s greatest stories were cooked, not written.", weight: 3 },
    { text: "To understand Ireland, begin at its table.", weight: 3 },
    { text: "Every Irish dish carries a piece of the island.", weight: 2 },
    { text: "Ireland’s history was not only written. It was served.", weight: 3 },
    { text: "The soul of Ireland has always had a place at the table.", weight: 3 },
    { text: "Irish food remembers what history forgets.", weight: 4 },
    { text: "Behind every Irish recipe is a story worth keeping.", weight: 4 },
    { text: "Ireland has preserved its memory through food for centuries.", weight: 2 },
    { text: "A nation’s culture can be tasted before it is understood.", weight: 3 },
    { text: "Irish cuisine is history shared at the table.", weight: 3 },
    { text: "Ireland remembers through food.", weight: 2 },
    { text: "Every Irish table holds a piece of history.", weight: 2 },
    { text: "The story of Ireland was also written in kitchens.", weight: 3 },
    { text: "Some traditions survive because someone keeps cooking them.", weight: 3 },
    { text: "Irish cuisine is memory made edible.", weight: 3 },
    { text: "A recipe can carry a country.", weight: 4 },
    { text: "Ireland’s past still has a place at the table.", weight: 2 },
    { text: "Food is one of Ireland’s oldest storytellers.", weight: 4 },
    { text: "Every generation adds something to the Irish table.", weight: 2 },
    { text: "Ireland’s culture was never only spoken. It was shared.", weight: 3 },
    { text: "Some recipes are older than the stories told about them.", weight: 3 },
    { text: "The Irish table has always been more than a place to eat.", weight: 3 },
    { text: "A nation can lose many things. Its recipes remember.", weight: 3 },
    { text: "Irish food carries the voices of those who came before us.", weight: 3 },
    { text: "History tastes different when it is still alive.", weight: 2 },
    { text: "The finest Irish stories were passed from hand to hand.", weight: 2 },
    { text: "Ireland’s heritage is not locked away. It is still being cooked.", weight: 3 },
    { text: "Every dish is a small act of remembrance.", weight: 3 },
    { text: "The table is where Ireland keeps its memory.", weight: 3 },
    { text: "Irish cuisine is not the past. It is the past still living.", weight: 2 },
    { text: "Before Ireland wrote its history, it cooked it.", weight: 2 },
    { text: "What Ireland could not preserve in words, it preserved in food.", weight: 2 },
    { text: "The island changed. The table remembered.", weight: 2 },
    { text: "Some cultures are studied. Ireland’s can be tasted.", weight: 2 },
    { text: "Every Irish recipe is a story that refused to disappear.", weight: 3 }
  ];

  const promotionsNode = document.getElementById("hero-chef-promotions");
  if (promotionsNode) {
    try {
      const promotions = JSON.parse(promotionsNode.textContent);
      if (Array.isArray(promotions)) {
        messages.push(...promotions.filter(item => item && item.text));
      }
    } catch (error) {
      // Keep the built-in messages when promotional data is unavailable.
    }
  }
  const chef = document.createElement("div");
  chef.className = "hero-chef";
  chef.dataset.pose = "walk-a";
  chef.dataset.direction = "right";
  chef.setAttribute("aria-label", "Animated CulinEire chef");
  chef.innerHTML = `
    <a class="hero-chef__speech" role="status" aria-live="polite"></a>
    <span class="hero-chef__sprite" aria-hidden="true"></span>
    <button class="hero-chef__close" type="button" aria-label="Hide animated chef" title="Hide animated chef">
      <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M3 3l10 10M13 3L3 13" />
      </svg>
    </button>`;
  hero.appendChild(chef);

  const speech = chef.querySelector(".hero-chef__speech");
  const close  = chef.querySelector(".hero-chef__close");
  let walkTimer;
  let walkFrameTimer;
  let trickFrameTimer;
  let poseTimer;
  let speechTimer;
  let previousPose = null;
  const WALK_FRAMES = ["0 0", "33.333% 0", "66.666% 0", "100% 0"];
  const BOOK_FRAMES = ["0 0", "20% 0", "40% 0", "60% 0", "80% 0", "100% 0"];
  const TRICK_POSES = ["sharpen", "egg", "book"];

  // ── Right-click quick-search ──────────────────────────────────────
  const searchAction = (() => {
    const f = document.querySelector(".ce-header-search");
    return f ? f.getAttribute("action") : "/recipes/";
  })();
  const searchPopup = document.createElement("div");
  searchPopup.className = "hero-chef__search-popup";
  searchPopup.setAttribute("role", "search");
  searchPopup.setAttribute("aria-label", "Quick search");
  searchPopup.hidden = true;
  searchPopup.innerHTML = `
    <form class="hero-chef__search-form" action="${searchAction}" method="get">
      <input class="hero-chef__search-input" type="search" name="q"
             placeholder="Search recipes…" aria-label="Search recipes"
             autocomplete="off" maxlength="100">
      <button class="hero-chef__search-btn" type="submit" aria-label="Search">
        <svg viewBox="0 0 16 16" width="14" height="14" fill="none"
             stroke="currentColor" stroke-width="2" stroke-linecap="round">
          <circle cx="6.5" cy="6.5" r="4.5"/>
          <line x1="10.5" y1="10.5" x2="14" y2="14"/>
        </svg>
      </button>
    </form>`;
  chef.appendChild(searchPopup);
  const searchInput = searchPopup.querySelector(".hero-chef__search-input");

  function openSearch() {
    searchPopup.hidden = false;
    searchInput.focus();
  }
  function closeSearch() {
    searchPopup.hidden = true;
    searchInput.value = "";
  }

  const isTouch = window.matchMedia("(pointer: coarse)").matches;
  if (isTouch) {
    chef.addEventListener("click", (e) => {
      if (e.target.closest(".hero-chef__close") || e.target.closest(".hero-chef__speech")) return;
      openSearch();
    });
  } else {
    chef.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      openSearch();
    });
  }
  document.addEventListener("click", (e) => {
    if (!searchPopup.hidden && !chef.contains(e.target)) closeSearch();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !searchPopup.hidden) closeSearch();
  });
  // ─────────────────────────────────────────────────────────────────

  const randomBetween = (min, max) => Math.random() * (max - min) + min;

  // Weighted shuffle deck — expand each message by its weight, shuffle, drain.
  const shuffle = arr => arr.slice().sort(() => Math.random() - 0.5);
  let deck = [];

  function buildDeck() {
    const expanded = [];
    for (const m of messages) {
      const n = m.weight || 1;
      for (let i = 0; i < n; i++) expanded.push(m);
    }
    return shuffle(expanded);
  }

  function nextMessage() {
    if (deck.length === 0) deck = buildDeck();
    return deck.pop();
  }

  function saySomething() {
    const message = nextMessage();
    speech.textContent = message.text;
    if (message.url) {
      speech.href = message.url;
      speech.dataset.linked = "true";
      if (/^https?:\/\//.test(message.url)) {
        speech.target = "_blank";
        speech.rel = "noopener noreferrer";
      } else {
        speech.removeAttribute("target");
        speech.removeAttribute("rel");
      }
    } else {
      speech.removeAttribute("href");
      speech.removeAttribute("target");
      speech.removeAttribute("rel");
      speech.dataset.linked = "false";
    }
    chef.dataset.speaking = "true";
    // Keep the bubble inside the horizon: measure after render and shift it
    // back inside the viewport (the tail stays anchored to the bear via CSS).
    speech.style.setProperty("--speech-shift", "0px");
    window.requestAnimationFrame(() => {
      const pad = 8;
      const rect = speech.getBoundingClientRect();
      let shift = 0;
      if (rect.right > window.innerWidth - pad) {
        shift = (window.innerWidth - pad) - rect.right;
      } else if (rect.left < pad) {
        shift = pad - rect.left;
      }
      if (shift !== 0) speech.style.setProperty("--speech-shift", shift.toFixed(1) + "px");
    });
    window.clearTimeout(speechTimer);
    speechTimer = window.setTimeout(() => {
      chef.dataset.speaking = "false";
    }, Math.max(4600, message.text.length * 65));
  }

  function performTrick() {
    const availablePoses = TRICK_POSES.filter(poseName => poseName !== previousPose);
    const pose = availablePoses[Math.floor(Math.random() * availablePoses.length)];
    previousPose = pose;
    const frames = pose === "book" ? BOOK_FRAMES : WALK_FRAMES;
    chef.dataset.walking = "false";
    chef.dataset.pose = pose;

    // Animate trick frames (slower than walk)
    window.clearInterval(trickFrameTimer);
    let trickIdx = 0;
    chef.style.setProperty("--trick-frame", frames[0]);
    trickFrameTimer = window.setInterval(() => {
      trickIdx = (trickIdx + 1) % frames.length;
      chef.style.setProperty("--trick-frame", frames[trickIdx]);
    }, 220);

    saySomething();
    poseTimer = window.setTimeout(() => {
      window.clearInterval(trickFrameTimer);
      chef.style.removeProperty("--trick-frame");
      startWalk();
    }, randomBetween(3800, 6200));
  }

  function startWalk() {
    if (reducedMotion.matches) {
      chef.dataset.walking = "false";
      chef.dataset.pose = "walk-a";
      return;
    }

    const currentX = (chef.offsetLeft / hero.clientWidth) * 100;
    let nextX = randomBetween(62, 88);
    while (Math.abs(nextX - currentX) < 4) {
      nextX = randomBetween(62, 88);
    }
    const movingRight = nextX > currentX;
    const distance = Math.abs(nextX - currentX);
    const travelTime = Math.max(2.4, distance / 7.5);
    chef.dataset.direction = movingRight ? "right" : "left";
    chef.style.setProperty("--chef-travel-time", `${travelTime}s`);
    chef.dataset.pose = "walk-a";
    chef.dataset.walking = "true";
    void chef.offsetWidth;
    chef.style.left = `${nextX}%`;

    // JS frame cycling — CSS steps() is unreliable in Chrome for background-position
    window.clearInterval(walkFrameTimer);
    let frameIdx = 0;
    chef.style.setProperty("--walk-frame", WALK_FRAMES[0]);
    walkFrameTimer = window.setInterval(() => {
      frameIdx = (frameIdx + 1) % WALK_FRAMES.length;
      chef.style.setProperty("--walk-frame", WALK_FRAMES[frameIdx]);
    }, 250);

    walkTimer = window.setTimeout(() => {
      window.clearInterval(walkFrameTimer);
      chef.style.removeProperty("--walk-frame");
      chef.dataset.walking = "false";
      poseTimer = window.setTimeout(performTrick, randomBetween(900, 2200));
    }, travelTime * 1000);
  }

  function dismiss() {
    window.clearTimeout(walkTimer);
    window.clearInterval(walkFrameTimer);
    window.clearInterval(trickFrameTimer);
    window.clearTimeout(poseTimer);
    window.clearTimeout(speechTimer);
    sessionStorage.setItem("heroChefDismissed", "1");
    chef.remove();
  }

  close.addEventListener("click", dismiss);

  if (reducedMotion.matches) {
    chef.dataset.pose = "walk-a";
    window.setTimeout(saySomething, 1400);
  } else {
    window.setTimeout(startWalk, 800);
  }
})();
