(() => {
  "use strict";

  const hero = document.querySelector("main .hero");
  const desktop = window.matchMedia("(min-width: 1024px)");
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

  if (!hero || !desktop.matches || sessionStorage.getItem("heroChefDismissed") === "1") {
    return;
  }

  const messages = [
    "Hello!",
    "What's cooking?",
    "Welcome to CulinEire!",
    "Mind the hot pan!",
    "A sharp knife is a safe knife."
  ];
  const chef = document.createElement("div");
  chef.className = "hero-chef";
  chef.dataset.pose = "walk-a";
  chef.setAttribute("aria-label", "Animated CulinEire chef");
  chef.innerHTML = `
    <span class="hero-chef__speech" role="status"></span>
    <span class="hero-chef__sprite" aria-hidden="true"></span>
    <button class="hero-chef__close" type="button" aria-label="Hide animated chef" title="Hide animated chef">
      <svg aria-hidden="true" viewBox="0 0 16 16" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round">
        <path d="M3 3l10 10M13 3L3 13" />
      </svg>
    </button>`;
  hero.appendChild(chef);

  const speech = chef.querySelector(".hero-chef__speech");
  const close = chef.querySelector(".hero-chef__close");
  let walkTimer;
  let poseTimer;
  let speechTimer;
  let walkingFrame;
  let previousX = 72;

  const randomBetween = (min, max) => Math.random() * (max - min) + min;

  function saySomething() {
    speech.textContent = messages[Math.floor(Math.random() * messages.length)];
    chef.dataset.speaking = "true";
    window.clearTimeout(speechTimer);
    speechTimer = window.setTimeout(() => {
      chef.dataset.speaking = "false";
    }, 3600);
  }

  function performTrick() {
    const pose = Math.random() < 0.5 ? "sharpen" : "egg";
    chef.dataset.pose = pose;
    if (Math.random() < 0.48) {
      saySomething();
    }
    poseTimer = window.setTimeout(startWalk, randomBetween(3800, 6200));
  }

  function startWalk() {
    if (!desktop.matches || reducedMotion.matches) {
      chef.dataset.pose = "walk-a";
      return;
    }

    const nextX = randomBetween(48, 90);
    const distance = Math.abs(nextX - previousX);
    const travelTime = Math.max(2.4, distance / 7.5);
    chef.style.setProperty("--chef-facing", nextX < previousX ? -1 : 1);
    chef.style.setProperty("--chef-travel-time", `${travelTime}s`);
    chef.style.left = `${nextX}%`;
    previousX = nextX;

    window.clearInterval(walkingFrame);
    let alternate = false;
    walkingFrame = window.setInterval(() => {
      alternate = !alternate;
      chef.dataset.pose = alternate ? "walk-b" : "walk-a";
    }, 260);

    walkTimer = window.setTimeout(() => {
      window.clearInterval(walkingFrame);
      chef.dataset.pose = "walk-a";
      poseTimer = window.setTimeout(performTrick, randomBetween(900, 2200));
    }, travelTime * 1000);
  }

  function dismiss() {
    window.clearTimeout(walkTimer);
    window.clearTimeout(poseTimer);
    window.clearTimeout(speechTimer);
    window.clearInterval(walkingFrame);
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
