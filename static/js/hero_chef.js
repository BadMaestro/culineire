(() => {
  "use strict";

  const hero = document.querySelector("main .hero");
  const desktop = window.matchMedia("(min-width: 1024px)");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!hero || !desktop.matches || sessionStorage.getItem("heroChefDismissed") === "1") {
    return;
  }

  const messages = [
    { text: "Hello!" },
    { text: "What's cooking?" },
    { text: "Welcome to CulinEire!" },
    { text: "Mind the hot pan!" },
    { text: "A sharp knife is a safe knife." },
    { text: "My favourite Chef is GreenBear." },
    { text: "You can't even make scrambled eggs?" },
    { text: "Think you can cook it better? Prove it!" },
    { text: "Some of Ireland's greatest stories were cooked, not written." },
    { text: "To understand Ireland, begin at its table." },
    { text: "Every Irish dish carries a piece of the island." },
    { text: "Ireland's history was not only written. It was served." },
    { text: "The soul of Ireland has always had a place at the table." },
    { text: "Irish food remembers what history forgets." },
    { text: "Behind every Irish recipe is a story worth keeping." },
    { text: "Ireland has preserved its memory through food for centuries." },
    { text: "A nation's culture can be tasted before it is understood." },
    { text: "Irish cuisine is history shared at the table." },
    { text: "Ireland remembers through food." },
    { text: "Every Irish table holds a piece of history." },
    { text: "The story of Ireland was also written in kitchens." },
    { text: "Some traditions survive because someone keeps cooking them." },
    { text: "Irish cuisine is memory made edible." },
    { text: "A recipe can carry a country." },
    { text: "Ireland's past still has a place at the table." },
    { text: "Food is one of Ireland's oldest storytellers." },
    { text: "Every generation adds something to the Irish table." },
    { text: "Ireland's culture was never only spoken. It was shared." },
    { text: "Some recipes are older than the stories told about them." },
    { text: "The Irish table has always been more than a place to eat." },
    { text: "A nation can lose many things. Its recipes remember." },
    { text: "Irish food carries the voices of those who came before us." },
    { text: "History tastes different when it is still alive." },
    { text: "The finest Irish stories were passed from hand to hand." },
    { text: "Ireland's heritage is not locked away. It is still being cooked." },
    { text: "Every dish is a small act of remembrance." },
    { text: "The table is where Ireland keeps its memory." },
    { text: "Irish cuisine is not the past. It is the past still living." },
    { text: "Before Ireland wrote its history, it cooked it." },
    { text: "What Ireland could not preserve in words, it preserved in food." },
    { text: "The island changed. The table remembered." },
    { text: "Some cultures are studied. Ireland's can be tasted." },
    { text: "Every Irish recipe is a story that refused to disappear." }
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
  let poseTimer;
  let speechTimer;
  let previousX = 72;
  const WALK_FRAMES = ["0 0", "33.333% 0", "66.666% 0", "100% 0"];

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

  chef.addEventListener("contextmenu", (e) => {
    e.preventDefault();
    openSearch();
  });
  document.addEventListener("click", (e) => {
    if (!searchPopup.hidden && !chef.contains(e.target)) closeSearch();
  });
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !searchPopup.hidden) closeSearch();
  });
  // ─────────────────────────────────────────────────────────────────

  const randomBetween = (min, max) => Math.random() * (max - min) + min;

  // Shuffled deck — every message plays once before any repeats
  let messageDeck = [];
  function nextMessage() {
    if (messageDeck.length === 0) {
      messageDeck = messages.slice().sort(() => Math.random() - 0.5);
    }
    return messageDeck.pop();
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
    window.clearTimeout(speechTimer);
    speechTimer = window.setTimeout(() => {
      chef.dataset.speaking = "false";
    }, Math.max(4600, message.text.length * 65));
  }

  function performTrick() {
    const pose = Math.random() < 0.5 ? "sharpen" : "egg";
    chef.dataset.walking = "false";
    chef.dataset.pose = pose;
    if (Math.random() < 0.48) {
      saySomething();
    }
    poseTimer = window.setTimeout(startWalk, randomBetween(3800, 6200));
  }

  function startWalk() {
    if (!desktop.matches || reducedMotion.matches) {
      chef.dataset.walking = "false";
      chef.dataset.pose = "walk-a";
      return;
    }

    const nextX = randomBetween(48, 90);
    const distance = Math.abs(nextX - previousX);
    const travelTime = Math.max(2.4, distance / 7.5);
    chef.style.setProperty("--chef-facing", nextX < previousX ? 1 : -1);
    chef.style.setProperty("--chef-travel-time", `${travelTime}s`);
    chef.style.left = `${nextX}%`;
    previousX = nextX;
    chef.dataset.walking = "true";

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
    window.clearTimeout(poseTimer);
    window.clearTimeout(speechTimer);
    sessionStorage.setItem("heroChefDismissed", "1");
    chef.remove();
  }

  close.addEventListener("click", dismiss);
  desktop.addEventListener("change", event => {
    if (!event.matches) {
      dismiss();
    }
  });

  if (reducedMotion.matches) {
    chef.dataset.pose = "walk-a";
    window.setTimeout(saySomething, 1400);
  } else {
    window.setTimeout(startWalk, 800);
  }
})();
