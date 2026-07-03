// Disable browser scroll restoration so iOS PWA does not open pages
// scrolled to a remembered position after a no-cache reload.
if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}

document.addEventListener("DOMContentLoaded", () => {
  // Track sticky header + filter bar heights so snap feed and sticky nav
  // always know how much room to leave at the top of the viewport.
  const ceHeader = document.querySelector(".ce-header");
  const setHeaderH = () => {
    const hh = ceHeader ? ceHeader.getBoundingClientRect().height : 0;
    document.documentElement.style.setProperty("--header-h", hh + "px");
    // --sticky-offset = header + sticky filter bar (if present on this page)
    const filterBar = document.querySelector(".recipe-list-page .category-nav-block");
    const fh = filterBar ? filterBar.getBoundingClientRect().height : 0;
    document.documentElement.style.setProperty("--sticky-offset", (hh + fh) + "px");
  };
  setHeaderH();
  if ("ResizeObserver" in window) {
    const ro = new ResizeObserver(setHeaderH);
    ro.observe(document.documentElement);
    // Root resize alone misses header/filter height changes from late font
    // loads or collapse toggles — watch the elements themselves too.
    if (ceHeader) ro.observe(ceHeader);
    const fb = document.querySelector(".recipe-list-page .category-nav-block");
    if (fb) ro.observe(fb);
  }
  // RO callbacks ride the render pipeline and freeze in occluded windows
  // (same failure class as the v2.5.70 rAF bug). A plain resize listener
  // is the deterministic backstop — the Pinch header drawer dispatches a
  // synthetic resize after each toggle precisely so this re-runs.
  window.addEventListener("resize", setHeaderH);

  // Set --ab-snap-top so the snap feed knows how much header to leave room for
  const snapPage = document.querySelector(".ab-snap-page");
  if (snapPage) {
    const setSnapTop = () => {
      const header = document.querySelector(".ce-header") || document.querySelector("header");
      const h = header ? header.getBoundingClientRect().height : 62;
      snapPage.style.setProperty("--ab-snap-top", h + "px");
    };
    setSnapTop();
    if ("ResizeObserver" in window) {
      new ResizeObserver(setSnapTop).observe(document.documentElement);
    }
  }

  const nav = document.querySelector(".ce-nav") || document.querySelector(".main-nav");
  const navButton = document.querySelector(".ce-nav__toggle") || document.querySelector(".nav-toggle");

  if (nav && navButton) {
    const openClass = nav.classList.contains("ce-nav") ? "ce-nav--open" : "main-nav--open";
    const backdrop = document.querySelector(".ce-nav__backdrop");

    let _scrollY = 0;
    const lockScroll = () => {
      _scrollY = window.scrollY;
      document.body.style.position = "fixed";
      document.body.style.top      = -_scrollY + "px";
      document.body.style.left     = "0";
      document.body.style.right    = "0";
    };
    const unlockScroll = () => {
      document.body.style.position = "";
      document.body.style.top      = "";
      document.body.style.left     = "";
      document.body.style.right    = "";
      // Restore unconditionally: on mobile Pinch the document IS the snap
      // feed, so this returns the user to the card they were on (_scrollY
      // was captured at a resting snap position, so no snap correction).
      window.scrollTo(0, _scrollY);
    };

    const closeNav = () => {
      nav.classList.remove(openClass);
      navButton.setAttribute("aria-expanded", "false");
      unlockScroll();
    };

    const positionNav = () => {
      const r = navButton.getBoundingClientRect();
      nav.style.top   = Math.max(4, r.top) + "px";
      nav.style.right = Math.max(4, window.innerWidth - r.right) + "px";
    };

    navButton.addEventListener("click", () => {
      const isOpen = nav.classList.toggle(openClass);
      navButton.setAttribute("aria-expanded", String(isOpen));
      if (isOpen) {
        positionNav();
        lockScroll();
      } else {
        unlockScroll();
      }
    });

    const navCloseBtn = nav.querySelector(".ce-nav__close");
    if (navCloseBtn) navCloseBtn.addEventListener("click", closeNav);

    /* iOS hover-stick fix: add/remove a transient class so :hover unsticks
       when the finger lifts and moves to a different nav item */
    nav.addEventListener("touchstart", e => {
      const item = e.target.closest("a, button");
      nav.querySelectorAll(".ce-nav-touch-active").forEach(el => el.classList.remove("ce-nav-touch-active"));
      if (item) item.classList.add("ce-nav-touch-active");
    }, { passive: true });
    nav.addEventListener("touchend", () => {
      setTimeout(() => nav.querySelectorAll(".ce-nav-touch-active").forEach(el => el.classList.remove("ce-nav-touch-active")), 200);
    }, { passive: true });

    if (backdrop) {
      backdrop.addEventListener("click", closeNav);
    }

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && nav.classList.contains(openClass)) closeNav();
    });
  }

  const authorPanels = document.querySelectorAll(".ce-author-panel");

  if (authorPanels.length) {
    const closeAuthorPanels = (exceptPanel = null) => {
      authorPanels.forEach((panel) => {
        if (panel !== exceptPanel) {
          panel.open = false;
        }
      });
    };

    authorPanels.forEach((panel) => {
      panel.addEventListener("toggle", () => {
        if (panel.open) {
          closeAuthorPanels(panel);
        }
      });
    });

    document.addEventListener("click", (event) => {
      const clickedPanel = event.target.closest(".ce-author-panel");

      if (!clickedPanel) {
        closeAuthorPanels();
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        closeAuthorPanels();
      }
    });
  }

  const categoryBlocks = document.querySelectorAll("[data-category-toggle]");

  categoryBlocks.forEach((block) => {
    const wrap = block.querySelector("[data-category-wrap]");
    const button = block.querySelector("[data-category-button]");
    const buttonLabel = block.querySelector("[data-category-button-label]");
    const categoryNav = block.querySelector("[data-category-nav]");

    if (!wrap || !button || !buttonLabel || !categoryNav) {
      return;
    }

    let expanded = false;
    let lastLayoutWidth = 0;

    const isWrapped = () => {
      const items = Array.from(categoryNav.querySelectorAll(".category-nav__item, .category-nav__link"));
      if (items.length < 2) return false;

      const firstTop = Math.round(items[0].getBoundingClientRect().top);
      return items.some((item) => Math.round(item.getBoundingClientRect().top) > firstTop + 2);
    };

    const getFirstRowHeight = () => {
      const items = Array.from(categoryNav.querySelectorAll(".category-nav__item, .category-nav__link"));
      if (!items.length) return 24;

      const firstTop = Math.round(items[0].getBoundingClientRect().top);
      const firstRowBottom = items.reduce((bottom, item) => {
        const rect = item.getBoundingClientRect();
        if (Math.round(rect.top) <= firstTop + 2) {
          return Math.max(bottom, rect.bottom);
        }
        return bottom;
      }, items[0].getBoundingClientRect().bottom);

      return Math.max(24, Math.ceil(firstRowBottom - firstTop));
    };

    const getLayoutWidth = () => Math.round(wrap.getBoundingClientRect().width);

    const applyResponsiveState = () => {
      const width = getLayoutWidth();
      if (lastLayoutWidth && Math.abs(width - lastLayoutWidth) <= 1) {
        return;
      }
      if (lastLayoutWidth) expanded = false;
      lastLayoutWidth = width;
      applyState();
    };

    const applyState = () => {
      wrap.style.height = "auto";
      void wrap.offsetHeight;

      const needsToggle = isWrapped();

      if (!needsToggle) {
        wrap.classList.remove("category-nav-wrap--collapsed", "category-nav-wrap--expanded");
        button.hidden = true;
        button.setAttribute("aria-expanded", "false");
        buttonLabel.textContent = "View All";
        return;
      }

      button.hidden = false;

      if (expanded) {
        wrap.style.height = `${Math.ceil(categoryNav.scrollHeight)}px`;
        wrap.classList.remove("category-nav-wrap--collapsed");
        wrap.classList.add("category-nav-wrap--expanded");
        button.setAttribute("aria-expanded", "true");
        button.setAttribute("aria-label", "Collapse recipe categories");
        buttonLabel.textContent = "View Less";
      } else {
        wrap.style.height = `${getFirstRowHeight()}px`;
        wrap.classList.remove("category-nav-wrap--expanded");
        wrap.classList.add("category-nav-wrap--collapsed");
        button.setAttribute("aria-expanded", "false");
        button.setAttribute("aria-label", "View all recipe categories");
        buttonLabel.textContent = "View All";
      }
    };

    button.addEventListener("click", () => {
      expanded = !expanded;
      applyState();
    });

    document.fonts.ready.then(() => {
      requestAnimationFrame(() => {
        expanded = false;
        lastLayoutWidth = getLayoutWidth();
        applyState();
      });
    });

    if ("ResizeObserver" in window) {
      new ResizeObserver(() => {
        applyResponsiveState();
      }).observe(wrap);
    } else {
      let resizeTimer = null;
      window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(() => {
          expanded = false;
          lastLayoutWidth = getLayoutWidth();
          applyState();
        }, 80);
      });
    }
  });

  const carousels = document.querySelectorAll("[data-card-carousel]");

  carousels.forEach((carousel) => {
    const track = carousel.querySelector("[data-carousel-track]");
    const previousButton = carousel.querySelector("[data-carousel-prev]");
    const nextButton = carousel.querySelector("[data-carousel-next]");

    if (!track || !previousButton || !nextButton) {
      return;
    }

    let scrollFrame = null;

    const getScrollStep = () => {
      const card = track.querySelector(".recipe-card, .ab-home-card, [data-carousel-item]");

      if (!card) {
        return Math.max(track.clientWidth * 0.85, 1);
      }

      const styles = window.getComputedStyle(track);
      const gap = parseFloat(styles.columnGap || styles.gap || "0");
      const cardWidth = card.getBoundingClientRect().width;

      return Math.max(cardWidth + (Number.isNaN(gap) ? 0 : gap), 1);
    };

    const updateControls = () => {
      const maxScrollLeft = Math.max(track.scrollWidth - track.clientWidth, 0);
      const canScroll = maxScrollLeft > 2;
      const atStart = track.scrollLeft <= 1;
      const atEnd = track.scrollLeft >= maxScrollLeft - 1;

      carousel.classList.toggle("content-showcase--scrollable", canScroll);
      carousel.classList.toggle("content-showcase--at-start", !canScroll || atStart);
      carousel.classList.toggle("content-showcase--at-end", !canScroll || atEnd);
      previousButton.disabled = !canScroll || atStart;
      nextButton.disabled = !canScroll || atEnd;
    };

    const scheduleUpdate = () => {
      if (scrollFrame !== null) {
        return;
      }

      scrollFrame = window.requestAnimationFrame(() => {
        scrollFrame = null;
        updateControls();
      });
    };

    previousButton.addEventListener("click", () => {
      track.scrollBy({
        left: -getScrollStep(),
        behavior: "smooth",
      });
    });

    nextButton.addEventListener("click", () => {
      track.scrollBy({
        left: getScrollStep(),
        behavior: "smooth",
      });
    });

    track.addEventListener("scroll", scheduleUpdate, { passive: true });
    // rAF is frozen in occluded windows and a pending frame blocks all later
    // updates — settle the controls directly once scrolling stops.
    track.addEventListener("scrollend", updateControls);

    requestAnimationFrame(updateControls);
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(updateControls);
    }

    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(updateControls);
      resizeObserver.observe(track);
      // track itself is width-stable (flex: 1) — watch the content too,
      // otherwise late font loads never re-enable the buttons
      if (track.firstElementChild) resizeObserver.observe(track.firstElementChild);
    } else {
      window.addEventListener("resize", updateControls);
    }
  });

  // ==== Content image watermarks ====
  (function () {
    const targets = document.querySelectorAll(
      ".recipe-gallery__image-shell, .detail-page__header",
    );
    targets.forEach((el) => {
      if (el.querySelector(".culineire-watermark")) return;
      const wm = document.createElement("span");
      wm.setAttribute("aria-hidden", "true");
      wm.className = "culineire-watermark";
      wm.textContent = "www.culineire.ie";
      el.appendChild(wm);
    });
  })();

  // ==== Hero peek lightbox ====
  const lightbox = document.getElementById("hero-lightbox");
  const lightboxImg = document.getElementById("hero-lightbox-img");
  const lightboxClose = document.getElementById("hero-lightbox-close");

  if (lightbox && lightboxImg && lightboxClose) {
    const eyeSvg =
      '<svg aria-hidden="true" fill="none" height="14" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round" stroke-width="1.8" viewBox="0 0 24 24" width="14"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>';

    document.querySelectorAll(".hero").forEach((hero) => {
      const bg = hero.querySelector(".hero__background");
      if (!bg) return;

      const btn = document.createElement("button");
      btn.className = "hero-peek-btn";
      btn.type = "button";
      btn.setAttribute("aria-label", "View full image");
      btn.innerHTML = eyeSvg + " Photo";
      hero.appendChild(btn);

      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        // Always read the currently active slide so the lightbox shows
        // the right image when the hero switcher has been used.
        const activeSlide = bg.querySelector(".hero__slide.is-active") || bg;
        const activeImg = activeSlide.querySelector("img");
        if (!activeImg) return;
        lightboxImg.src = activeImg.currentSrc || activeImg.src;
        lightboxImg.alt = activeImg.alt || "";
        lightbox.classList.add("hero-lightbox--open");
        document.body.style.overflow = "hidden";
        requestAnimationFrame(() => lightboxClose.focus());
      });
    });

    const closeLightbox = () => {
      lightbox.classList.remove("hero-lightbox--open");
      // Restore scroll immediately — do NOT rely on transitionend for this.
      // transitionend can fire from a child element first (the img has its own
      // transition: transform) or not fire at all under prefers-reduced-motion,
      // which would leave body overflow stuck at "hidden" permanently.
      document.body.style.overflow = "";
      // Clear the img src after the fade-out finishes (memory optimisation).
      // Guard with e.target === lightbox so the child img's transitionend
      // bubbling up does not trigger the clear prematurely.
      lightbox.addEventListener(
        "transitionend",
        (e) => {
          if (e.target === lightbox && !lightbox.classList.contains("hero-lightbox--open")) {
            lightboxImg.src = "";
          }
        },
        { once: true },
      );
    };

    lightboxImg.addEventListener("contextmenu", (e) => e.preventDefault());
    lightboxImg.addEventListener("dragstart", (e) => e.preventDefault());

    lightboxClose.addEventListener("click", closeLightbox);

    lightbox.addEventListener("click", (e) => {
      if (e.target === lightbox) closeLightbox();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape" && lightbox.classList.contains("hero-lightbox--open")) {
        closeLightbox();
      }
    });
  }

  // ==== Pinch 3-dot menus ====
  document.querySelectorAll("[data-ab-menu]").forEach((menu) => {
    const trigger = menu.querySelector(".ab-menu__trigger");
    const list = menu.querySelector(".ab-menu__list");
    if (!trigger || !list) return;

    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = !list.hidden;
      // Close all other open menus first
      document.querySelectorAll("[data-ab-menu] .ab-menu__list").forEach((l) => {
        l.hidden = true;
        l.closest("[data-ab-menu]").querySelector(".ab-menu__trigger").setAttribute("aria-expanded", "false");
      });
      list.hidden = isOpen;
      trigger.setAttribute("aria-expanded", String(!isOpen));
    });

    // Copy-link items inside the menu
    list.querySelectorAll("[data-ab-copy-link]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const url = btn.dataset.abCopyLink;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url).catch(() => {});
        }
        list.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
      });
    });
  });

  // Close all ab-menus on outside click / Escape
  document.addEventListener("click", () => {
    document.querySelectorAll("[data-ab-menu] .ab-menu__list").forEach((l) => {
      l.hidden = true;
      l.closest("[data-ab-menu]").querySelector(".ab-menu__trigger").setAttribute("aria-expanded", "false");
    });
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      document.querySelectorAll("[data-ab-menu] .ab-menu__list").forEach((l) => {
        l.hidden = true;
        l.closest("[data-ab-menu]").querySelector(".ab-menu__trigger").setAttribute("aria-expanded", "false");
      });
    }
  });

  // ==== Pinch share buttons ====
  document.querySelectorAll("[data-ab-share]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const url = btn.dataset.abShare;
      if (navigator.share) {
        navigator.share({ url }).catch(() => {});
      } else if (navigator.clipboard) {
        navigator.clipboard.writeText(url).then(() => {
          const orig = btn.title;
          btn.title = "Link copied!";
          setTimeout(() => { btn.title = orig; }, 2000);
        }).catch(() => {});
      }
    });
  });

  // ==== Pinch bottom sheet (slide-up) ====
  const closeAllSheets = () => {
    document.querySelectorAll(".ab-card__sheet.is-open").forEach((s) => {
      s.classList.remove("is-open");
      s.setAttribute("aria-hidden", "true");
    });
    document.querySelectorAll("[data-ab-more]").forEach((b) => {
      b.setAttribute("aria-expanded", "false");
    });
  };

  document.addEventListener("click", (e) => {
    const moreBtn = e.target.closest("[data-ab-more]");
    if (moreBtn) {
      e.stopPropagation();
      const pk = moreBtn.dataset.abMore;
      const sheet = document.getElementById("ab-sheet-" + pk);
      if (!sheet) return;
      const wasOpen = sheet.classList.contains("is-open");
      closeAllSheets();
      if (!wasOpen) {
        sheet.classList.add("is-open");
        sheet.setAttribute("aria-hidden", "false");
        moreBtn.setAttribute("aria-expanded", "true");
      }
      return;
    }

    const closeBtn = e.target.closest("[data-ab-close]");
    if (closeBtn) {
      const pk = closeBtn.dataset.abClose;
      const sheet = document.getElementById("ab-sheet-" + pk);
      if (sheet) {
        sheet.classList.remove("is-open");
        sheet.setAttribute("aria-hidden", "true");
        const moreBtn2 = document.querySelector("[data-ab-more='" + pk + "']");
        if (moreBtn2) moreBtn2.setAttribute("aria-expanded", "false");
      }
      return;
    }

    // Click outside sheet or more-btn closes all sheets
    if (!e.target.closest(".ab-card__sheet") && !e.target.closest("[data-ab-more]")) {
      closeAllSheets();
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAllSheets();
  });

  // ==== Hero actions burger (all pages with .hero__burger) ====
  document.addEventListener("click", (e) => {
    const btn = e.target.closest(".hero__burger");
    if (!btn) return;
    const actions = btn.closest(".hero__actions") || btn.closest(".battle-home__nav-row");
    if (!actions) return;
    const open = actions.classList.toggle("is-open");
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    btn.setAttribute("aria-label", open ? "Hide navigation" : "Show navigation");
  });

  // ==== Pinch like / save — AJAX toggle (no page reload, no scroll reset) ====
  document.addEventListener("submit", (e) => {
    const form = e.target.closest(".ab-action-form");
    if (!form) return;
    const csrfInput = form.querySelector("[name=csrfmiddlewaretoken]");
    if (!csrfInput) return;
    e.preventDefault();

    const btn = form.querySelector(".ab-btn");
    if (!btn) return;

    // Optimistic: disable while in flight
    btn.disabled = true;

    fetch(form.action, {
      method: "POST",
      headers: {
        "X-CSRFToken": csrfInput.value,
        "X-AB-Fetch": "1",
      },
      body: new FormData(form),
    })
      .then((r) => r.json())
      .then((data) => {
        if (!data.ok) return;

        // Like button
        if ("liked" in data) {
          btn.classList.toggle("ab-btn--liked", data.liked);
          btn.setAttribute("aria-label", data.liked ? "Unlike" : "Like");
          // Update count badge
          let countEl = btn.querySelector(".ab-btn__count");
          if (data.count > 0) {
            if (!countEl) {
              countEl = document.createElement("span");
              countEl.className = "ab-btn__count";
              btn.appendChild(countEl);
            }
            countEl.textContent = data.count;
          } else if (countEl) {
            countEl.remove();
          }
        }

        // Save / bookmark button
        if ("saved" in data) {
          btn.classList.toggle("ab-btn--saved", data.saved);
          btn.setAttribute("aria-label", data.saved ? "Remove bookmark" : "Bookmark");
        }
      })
      .catch(() => {
        // Network error — fall back to normal form submit
        form.submit();
      })
      .finally(() => {
        btn.disabled = false;
      });
  });

  // ==== AB grid: fixed 3×3 (desktop) / 2×2 (mobile) with internal scroll ====
  function sizeAbGrid() {
    const wrapper = document.querySelector(".ab-grid-scroll");
    if (!wrapper) return;
    // On mobile Pinch feed we use full-screen CSS snap — skip JS sizing
    if (window.innerWidth <= 640 && document.querySelector(".hero--pinch")) return;
    const firstCard = wrapper.querySelector(".ab-card");
    if (!firstCard) return;
    const gridEl = wrapper.querySelector(".ab-grid");
    const isMobile = window.innerWidth <= 640;
    const rows = isMobile ? 2 : 3;
    const gap = gridEl
      ? (parseFloat(getComputedStyle(gridEl).rowGap) || 16)
      : 16;
    wrapper.style.maxHeight = firstCard.offsetHeight * rows + gap * (rows - 1) + "px";
  }
  window.addEventListener("load", sizeAbGrid);
  let _abResizeTimer;
  window.addEventListener("resize", function () {
    clearTimeout(_abResizeTimer);
    _abResizeTimer = setTimeout(sizeAbGrid, 100);
  });

  // ==== AB ripple: action buttons, MORE, CLOSE, category badges ====
  document.addEventListener("click", function (e) {
    const btn = e.target.closest(
      ".ab-btn, [data-ab-more], [data-ab-close], .ab-card__badge, .ab-home-card__badge, .ab-home-card__close"
    );
    if (!btn) return;
    btn.querySelectorAll(".ab-ripple").forEach(function (r) { r.remove(); });
    const ripple = document.createElement("span");
    ripple.className = "ab-ripple";
    btn.appendChild(ripple);
    ripple.addEventListener("animationend", function () { ripple.remove(); }, { once: true });
  });

  // ==== AB comments panel (card-anchored popup, AJAX) ====
  (function () {
    var panel = null;
    var scrim = null;
    var activeSlug = null;

    function buildPanel() {
      if (panel) return;

      // Separate full-screen scrim
      scrim = document.createElement("div");
      scrim.className = "ab-cmt-scrim";
      scrim.dataset.abCmtClose = "";
      document.body.appendChild(scrim);

      // Popup panel (no internal scrim)
      panel = document.createElement("div");
      panel.className = "ab-cmt-panel";
      panel.setAttribute("aria-hidden", "true");
      panel.setAttribute("role", "dialog");
      panel.setAttribute("aria-label", "Comments");
      document.body.appendChild(panel);
    }

    function positionPanel(cardEl) {
      if (!panel || !cardEl || window.innerWidth < 640) return;
      var rect = cardEl.getBoundingClientRect();
      panel.style.top    = rect.top    + "px";
      panel.style.left   = rect.left   + "px";
      panel.style.width  = rect.width  + "px";
      panel.style.height = rect.height + "px";
    }

    function openPanel(slug, cardEl) {
      buildPanel();
      activeSlug = slug;
      // No anchor card (e.g. homepage announcement): open as a centered modal.
      panel.classList.toggle("ab-cmt-panel--modal", !cardEl);
      if (!cardEl) {
        panel.style.top = "";
        panel.style.left = "";
        panel.style.width = "";
        panel.style.height = "";
      }
      panel.innerHTML =
        '<div style="padding:2rem;text-align:center;color:#9a8a78;font-size:.9rem;">Loading&hellip;</div>';
      positionPanel(cardEl);
      scrim.classList.add("is-open");
      panel.setAttribute("aria-hidden", "false");
      // Lock BOTH: iOS ignores overflow:hidden on body alone for document
      // touch scrolling — html must be locked too (preserves scrollY).
      document.body.style.overflow = "hidden";
      document.documentElement.style.overflow = "hidden";
      requestAnimationFrame(function () { panel.classList.add("is-open"); });

      fetch("/pinch/" + slug + "/comments/", {
        headers: { "X-AB-Fetch": "1" },
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.ok) {
            panel.innerHTML = data.html;
            updateFeedCount(slug, data.count);
          }
        })
        .catch(function () {
          panel.innerHTML =
            '<div style="padding:2rem;text-align:center;color:#9a8a78;font-size:.9rem;">Could not load comments.</div>';
        });
    }

    function closePanel() {
      if (!panel) return;
      panel.classList.remove("is-open");
      scrim.classList.remove("is-open");
      document.body.style.overflow = "";
      document.documentElement.style.overflow = "";
      panel.addEventListener(
        "transitionend",
        function () {
          panel.setAttribute("aria-hidden", "true");
          activeSlug = null;
        },
        { once: true }
      );
    }

    function updateFeedCount(slug, count) {
      var feedBtn = document.querySelector('[data-ab-cmt="' + slug + '"]');
      if (!feedBtn) return;
      var countEl = feedBtn.querySelector(".ab-btn__count");
      if (count > 0) {
        if (!countEl) {
          countEl = document.createElement("span");
          countEl.className = "ab-btn__count";
          feedBtn.appendChild(countEl);
        }
        countEl.textContent = count;
      } else if (countEl) {
        countEl.remove();
      }
    }

    function updatePanelCount(count) {
      if (!panel) return;
      var countEl = panel.querySelector(".ab-cmt-panel__count");
      var titleEl = panel.querySelector(".ab-cmt-panel__title");
      if (count > 0) {
        if (!countEl && titleEl) {
          countEl = document.createElement("span");
          countEl.className = "ab-cmt-panel__count";
          titleEl.appendChild(countEl);
        }
        if (countEl) countEl.textContent = count;
      } else if (countEl) {
        countEl.remove();
      }
    }

    // Click delegation
    document.addEventListener("click", function (e) {
      // Open panel from feed card button
      var cmtBtn = e.target.closest("[data-ab-cmt]");
      if (cmtBtn && !e.target.closest(".ab-cmt-panel")) {
        openPanel(cmtBtn.dataset.abCmt, cmtBtn.closest(".ab-card"));
        return;
      }

      // Close panel
      if (e.target.closest("[data-ab-cmt-close]")) {
        closePanel();
        return;
      }

      if (!panel) return;

      // Reply toggle
      var replyBtn = e.target.closest("[data-ab-cmt-reply]");
      if (replyBtn) {
        var pk = replyBtn.dataset.abCmtReply;
        var form = panel.querySelector('[data-reply-to="' + pk + '"]');
        if (form) {
          form.hidden = !form.hidden;
          if (!form.hidden) {
            var ta = form.querySelector("textarea");
            if (ta) ta.focus();
          }
        }
        return;
      }

      // Reply cancel
      var cancelBtn = e.target.closest(".ab-cmt__reply-cancel");
      if (cancelBtn) {
        var rForm = cancelBtn.closest(".ab-cmt__reply-form");
        if (rForm) rForm.hidden = true;
        return;
      }

      // Delete comment
      var delBtn = e.target.closest("[data-ab-cmt-delete]");
      if (delBtn) {
        var commentId = delBtn.dataset.abCmtDelete;
        var dSlug = delBtn.dataset.slug;
        var csrfEl = panel.querySelector("[name=csrfmiddlewaretoken]");
        if (!csrfEl) return;
        fetch("/pinch/" + dSlug + "/comment/" + commentId + "/delete/", {
          method: "POST",
          headers: { "X-CSRFToken": csrfEl.value, "X-AB-Fetch": "1" },
          body: new FormData(),
        })
          .then(function (r) { return r.json(); })
          .then(function (data) {
            if (!data.ok) return;
            var el = panel.querySelector("#ab-cmt-" + commentId);
            if (el) el.remove();
            updateFeedCount(activeSlug, data.count);
            updatePanelCount(data.count);
          })
          .catch(function () {});
        return;
      }
    });

    // Submit new comment or reply
    document.addEventListener("submit", function (e) {
      var form = e.target.closest("[data-ab-cmt-form]");
      if (!form) return;
      e.preventDefault();
      var slug = form.dataset.abCmtForm;
      var csrfEl = form.querySelector("[name=csrfmiddlewaretoken]");
      if (!csrfEl) return;
      var bodyInput = form.querySelector("[name=body]");
      if (!bodyInput || !bodyInput.value.trim()) return;
      var submitBtn = form.querySelector("[type=submit]");
      if (submitBtn) submitBtn.disabled = true;

      var fd = new FormData(form);
      fetch("/pinch/" + slug + "/comment/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfEl.value, "X-AB-Fetch": "1" },
        body: fd,
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          var oldErr = form.querySelector(".ab-cmt-panel__error");
          if (oldErr) oldErr.remove();
          if (!data.ok) {
            var err = document.createElement("p");
            err.className = "ab-cmt-panel__error";
            err.textContent = data.message || "Could not post your comment. Please try again.";
            form.appendChild(err);
            return;
          }
          bodyInput.value = "";
          // Hide reply form after posting
          if (form.dataset.replyTo) form.hidden = true;

          var list = panel ? panel.querySelector("[data-ab-cmt-list]") : null;
          if (!list) return;

          var tmp = document.createElement("div");
          tmp.innerHTML = data.comment_html;
          var newEl = tmp.firstElementChild;
          if (!newEl) return;

          if (data.parent_id) {
            // Insert into replies container
            var repliesDiv = panel.querySelector("#ab-cmt-replies-" + data.parent_id);
            if (repliesDiv) repliesDiv.appendChild(newEl);
          } else {
            // Append to top-level list
            var emptyEl = list.querySelector(".ab-cmt-panel__empty");
            if (emptyEl) emptyEl.remove();
            list.appendChild(newEl);
          }
          newEl.scrollIntoView({ behavior: "smooth", block: "nearest" });
          updateFeedCount(slug, data.count);
          updatePanelCount(data.count);
        })
        .catch(function () {})
        .finally(function () {
          if (submitBtn) submitBtn.disabled = false;
        });
    });

    // Escape key closes panel
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && panel && panel.classList.contains("is-open")) {
        closePanel();
      }
    });
  })();

  // ==== Pinch footer drawer (mobile snap mode) ====
  // iOS-style bottom sheet: tap toggles; Pointer Events drag on the handle
  // follows the finger; swipe down on the open sheet body closes it. No
  // document-wide gesture — feed swipes can never open it.
  (function () {
    var handle = document.getElementById("pinch-footer-handle");
    var scrim  = document.getElementById("pinch-footer-scrim");
    if (!handle) return;

    var footer = document.querySelector("footer");
    if (!footer) return;

    var OPEN_CLASS = "pinch-footer--open";

    // Class on the footer is the single source of truth for open state
    var isOpen = function () { return footer.classList.contains(OPEN_CLASS); };

    // max-height:82vh already caps offsetHeight; min() kept as a guard
    var sheetHeight = function () {
      return Math.min(footer.offsetHeight, window.innerHeight * 0.82);
    };

    // publish the sheet height so CSS can park the handle on its top edge
    var publishHeight = function () {
      document.documentElement.style.setProperty("--pinch-footer-h", sheetHeight() + "px");
    };

    var setAria = function (open) {
      handle.setAttribute("aria-expanded", open ? "true" : "false");
      handle.setAttribute("aria-label", open ? "Close footer" : "Open footer");
    };

    var open = function () {
      publishHeight();
      footer.classList.add(OPEN_CLASS);
      if (scrim) { scrim.classList.add("is-open"); scrim.setAttribute("aria-hidden", "false"); }
      setAria(true);
    };

    var close = function () {
      footer.classList.remove(OPEN_CLASS);
      if (scrim) { scrim.classList.remove("is-open"); scrim.setAttribute("aria-hidden", "true"); }
      setAria(false);
    };

    var swipeGuard = false;
    handle.addEventListener("click", function () {
      if (swipeGuard) { swipeGuard = false; return; }
      if (isOpen()) { close(); } else { open(); }
    });

    if (scrim) {
      scrim.addEventListener("click", close);
      // belt-and-braces with CSS touch-action:none — a drag on the scrim
      // must never scroll the feed behind the open sheet
      scrim.addEventListener("touchmove", function (e) { e.preventDefault(); }, { passive: false });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen()) close();
    });

    // Pointer Events drag on the handle — finger-follow with momentum-aware snap.
    // Only the handle acts as pointer target (handle rides to the footer top edge
    // when open, so it's reachable for close swipes without touching the scroll body).
    var SWIPE_MIN = 28;    // px min vertical travel
    var DRIFT_MAX = 35;    // px max horizontal drift
    var VELOCITY  = 0.25;  // px/ms velocity shortcut
    var drag      = null;

    function snapFooter(toOpen) {
      // Commit the current drag translateY, restore transition, then snap.
      var mat  = new DOMMatrix(getComputedStyle(footer).transform);
      var curY = mat.m42;
      footer.style.transition = "none";
      footer.style.transform  = "translateY(" + curY + "px)";
      footer.getBoundingClientRect(); // flush layout — commits curY as the before-value
      requestAnimationFrame(function () {
        footer.style.transition = "";
        footer.style.transform  = "";
        if (toOpen) { open(); } else { close(); }
      });
    }

    handle.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      drag = { id: e.pointerId, y0: e.clientY, x0: e.clientX, t0: Date.now(), moved: false };
      handle.setPointerCapture(e.pointerId);
    }, { passive: true });

    handle.addEventListener("pointermove", function (e) {
      if (!drag || drag.id !== e.pointerId) return;
      var dy = e.clientY - drag.y0;
      if (Math.abs(dy) > 8) {
        drag.moved = true;
        e.preventDefault();
      }
      if (!drag.moved) return;
      if (!isOpen() && dy < -8) {
        footer.style.transition = "none";
        footer.style.transform  = "translateY(" + Math.max(0, 100 + dy / window.innerHeight * 100) + "%)";
      } else if (isOpen() && dy > 8 && footer.scrollTop <= 0) {
        footer.style.transition = "none";
        footer.style.transform  = "translateY(" + Math.max(0, dy) + "px)";
      }
    }, { passive: false });

    handle.addEventListener("pointerup", function (e) {
      if (!drag || drag.id !== e.pointerId) return;
      var d = drag; drag = null;
      var dy  = e.clientY - d.y0;
      var dx  = Math.abs(e.clientX - d.x0);
      var vel = (Date.now() - d.t0) > 0 ? Math.abs(dy) / (Date.now() - d.t0) : 0;
      var ok  = d.moved && dx <= DRIFT_MAX && (Math.abs(dy) >= SWIPE_MIN || vel >= VELOCITY);
      if (ok && !isOpen() && dy < 0) {
        swipeGuard = true;
        snapFooter(true);
      } else if (ok && isOpen() && dy > 0 && footer.scrollTop <= 0) {
        swipeGuard = true;
        snapFooter(false);
      } else if (d.moved) {
        snapFooter(isOpen()); // incomplete swipe — snap back to current state
      }
      // else: was a tap → let the click event fire normally
    });

    handle.addEventListener("pointercancel", function () {
      if (!drag) return;
      footer.style.transition = "";
      footer.style.transform  = "";
      drag = null;
    });

    // Footer body: simple touch swipe-down-to-close (no pointer capture — preserves scroll)
    var fts = null;
    footer.addEventListener("touchstart", function (e) {
      if (!isOpen() || footer.scrollTop > 0) return;
      fts = { y: e.touches[0].clientY, x: e.touches[0].clientX };
    }, { passive: true });
    footer.addEventListener("touchend", function (e) {
      if (!fts) return;
      var dy = e.changedTouches[0].clientY - fts.y;
      var dx = Math.abs(e.changedTouches[0].clientX - fts.x);
      fts = null;
      if (dy >= SWIPE_MIN && dx <= DRIFT_MAX && isOpen() && footer.scrollTop <= 0) close();
    }, { passive: true });

    // keep --pinch-footer-h honest across rotation / address-bar resize
    window.addEventListener("resize", function () { if (isOpen()) publishHeight(); });
  })();

  // ==== Pinch header drawer (mobile snap mode) ====
  // Top counterpart of the footer sheet: the logo row + filter bar are
  // collapsed by default (cards get the whole screen below the social
  // strip); the arch handle pulls them down. Tap toggles; swipe down on
  // the handle opens, swipe up closes. body.pinch-header-open is the
  // single source of truth; --sticky-offset shrinks/grows automatically
  // via setHeaderH's ResizeObservers, so card height and snap padding
  // follow the drawer in both states.
  (function () {
    var handle = document.getElementById("pinch-header-handle");
    var scrim  = document.getElementById("pinch-header-scrim");
    if (!handle) return;

    var OPEN_CLASS = "pinch-header-open";
    var isOpen = function () { return document.body.classList.contains(OPEN_CLASS); };

    // After the 0.38s slide settles, let the filter carousel re-measure
    // itself against the new geometry (its modules listen for resize).
    var kick = function () {
      setTimeout(function () { window.dispatchEvent(new Event("resize")); }, 320);
    };

    var open = function () {
      document.body.classList.add(OPEN_CLASS);
      if (scrim) { scrim.classList.add("is-open"); scrim.setAttribute("aria-hidden", "false"); }
      handle.setAttribute("aria-expanded", "true");
      handle.setAttribute("aria-label", "Hide menu");
      kick();
    };

    var close = function () {
      document.body.classList.remove(OPEN_CLASS);
      if (scrim) { scrim.classList.remove("is-open"); scrim.setAttribute("aria-hidden", "true"); }
      handle.setAttribute("aria-expanded", "false");
      handle.setAttribute("aria-label", "Show menu");
      kick();
    };

    var swipeGuard = false;
    handle.addEventListener("click", function () {
      if (swipeGuard) { swipeGuard = false; return; }
      if (isOpen()) { close(); } else { open(); }
    });

    if (scrim) {
      scrim.addEventListener("click", close);
      scrim.addEventListener("touchmove", function (e) { e.preventDefault(); }, { passive: false });
    }

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape" && isOpen()) close();
    });

    // Swipe on the handle: down opens the drawer, up closes it.
    // Same thresholds as the footer drag (no live finger-follow here —
    // the drawer is a max-height slide across two DOM subtrees).
    var SWIPE_MIN = 28;    // px min vertical travel
    var DRIFT_MAX = 35;    // px max horizontal drift
    var VELOCITY  = 0.25;  // px/ms velocity shortcut
    var drag = null;

    handle.addEventListener("pointerdown", function (e) {
      if (e.pointerType === "mouse") return;
      drag = { id: e.pointerId, y0: e.clientY, x0: e.clientX, t0: Date.now(), moved: false };
      handle.setPointerCapture(e.pointerId);
    });

    handle.addEventListener("pointermove", function (e) {
      if (!drag || drag.id !== e.pointerId) return;
      if (Math.abs(e.clientY - drag.y0) > 8) {
        drag.moved = true;
        e.preventDefault();
      }
    }, { passive: false });

    handle.addEventListener("pointerup", function (e) {
      if (!drag || drag.id !== e.pointerId) return;
      var d = drag; drag = null;
      var dy  = e.clientY - d.y0;
      var dx  = Math.abs(e.clientX - d.x0);
      var vel = (Date.now() - d.t0) > 0 ? Math.abs(dy) / (Date.now() - d.t0) : 0;
      var ok  = d.moved && dx <= DRIFT_MAX && (Math.abs(dy) >= SWIPE_MIN || vel >= VELOCITY);
      if (ok && !isOpen() && dy > 0) {
        swipeGuard = true;
        open();
      } else if (ok && isOpen() && dy < 0) {
        swipeGuard = true;
        close();
      }
      // else: tap → click handler owns it
    });

    handle.addEventListener("pointercancel", function () { drag = null; });
  })();

  // ==== Pinch filter: whole-item visibility + resting centering ====
  // A category never shows half-clipped under the carousel arrows — it is
  // either fully inside the visible track or hidden entirely until the
  // arrows scroll it fully into view. When scrolling settles, the group of
  // fully visible items is centered between the arrows via a transform so
  // the leftover blank space splits evenly instead of piling up on one side.
  (function () {
    var carousel = document.querySelector(".pinch-filter-carousel");
    if (!carousel) return;
    var wrap = carousel.querySelector(".category-nav-wrap");
    var nav = carousel.querySelector(".category-nav");
    if (!wrap || !nav) return;

    var settleTimer = null;

    var snapMode = function () {
      return window.innerWidth <= 640 && !!document.querySelector(".hero--pinch");
    };

    // No rAF gating — occluded windows freeze rAF and a pending frame would
    // block every later update. The work is ~20 rect reads; cheap enough raw.
    // All positions are computed in CONTENT coordinates (item rect relative
    // to the nav rect): the centering translateX moves both by the same
    // amount, so it cancels out — no race with the transform transition.
    var update = function (recenter) {
      var children = nav.children;
      var i;
      if (!snapMode()) {
        for (i = 0; i < children.length; i++) children[i].style.visibility = "";
        nav.style.transform = "";
        return;
      }
      var navLeft = nav.getBoundingClientRect().left;
      var viewL = wrap.scrollLeft;
      var viewR = viewL + wrap.clientWidth;
      var firstFull = null;
      var lastFull = null;
      for (i = 0; i < children.length; i++) {
        var r = children[i].getBoundingClientRect();
        var left = r.left - navLeft;
        var right = r.right - navLeft;
        var overlaps = right > viewL && left < viewR;
        var fully = left >= viewL - 2 && right <= viewR + 2;
        children[i].style.visibility = overlaps && !fully ? "hidden" : "";
        if (overlaps && fully) {
          if (firstFull === null) firstFull = left;
          lastFull = right;
        }
      }
      if (recenter && firstFull !== null) {
        var blankLeft = firstFull - viewL;
        var blankRight = viewR - lastFull;
        var shift = Math.round((blankRight - blankLeft) / 2);
        nav.style.transform = shift ? "translateX(" + shift + "px)" : "";
      }
    };

    var lastScrollTs = 0;
    var onScroll = function () {
      lastScrollTs = Date.now();
      update(false);
      // debounce as a scrollend substitute (iOS Safari lacks the event)
      clearTimeout(settleTimer);
      settleTimer = setTimeout(function () { update(true); }, 120);
    };

    wrap.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", function () { update(true); });
    if ("ResizeObserver" in window) {
      new ResizeObserver(function () { update(true); }).observe(nav);
    }
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () { update(true); });
    }
    // Self-heal: iOS Safari restores pages from bfcache with stale
    // transform/visibility and can move scrollLeft without firing any of
    // the events above — the row then sits frozen with items half-clipped
    // under the arrows. update(true) recomputes everything from scratch
    // and is idempotent, so an idle watchdog repairs any missed state
    // within ~600ms at negligible cost (~20 rect reads).
    window.addEventListener("pageshow", function (e) {
      if (e.persisted) update(true);
    });
    setInterval(function () {
      if (!snapMode()) return;
      if (document.visibilityState !== "visible") return;
      if (Date.now() - lastScrollTs < 400) return; // mid-scroll: events drive
      update(true);
    }, 600);
    update(true);
  })();
});

// ── Chef Battle live notification polling ────────────────────────────────────
(function () {
  var pollUrl = document.documentElement.dataset.battlePollUrl;
  if (!pollUrl) return;

  var lastCount = 0;

  function showBattleToast(items) {
    var existing = document.getElementById("battle-toast");
    if (existing) existing.remove();

    var toast = document.createElement("div");
    toast.id = "battle-toast";
    toast.className = "battle-toast";
    var html = '<div class="battle-toast__inner">';
    items.forEach(function (item) {
      html += '<a class="battle-toast__item" href="' + item.url + '">' + item.text + '</a>';
    });
    html += '<button class="battle-toast__close" aria-label="Dismiss">&times;</button></div>';
    toast.innerHTML = html;
    document.body.appendChild(toast);

    toast.querySelector(".battle-toast__close").addEventListener("click", function () {
      toast.remove();
    });
    setTimeout(function () { if (toast.parentNode) toast.remove(); }, 12000);
  }

  function poll() {
    fetch(pollUrl, { credentials: "same-origin" })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (data.count > lastCount && data.items && data.items.length) {
          showBattleToast(data.items);
        }
        lastCount = data.count;
      })
      .catch(function () {});
  }

  poll();
  setInterval(poll, 45000);
})();

// ── Chef Battle combat action form ──────────────────────────────────────────
(function () {
  var form = document.getElementById("combat-action-form");
  if (!form) return;
  var panel = document.getElementById("battle-combat-panel");
  var url = panel ? panel.dataset.combatUrl : null;
  if (!url) return;

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    var btn = document.getElementById("combat-submit-btn");
    var errEl = document.getElementById("combat-error");
    var okEl = document.getElementById("combat-success");
    if (btn) btn.disabled = true;
    errEl.hidden = true;
    okEl.hidden = true;

    var data = new FormData(form);
    fetch(url, { method: "POST", credentials: "same-origin", body: data })
      .then(function (r) { return r.json(); })
      .then(function (d) {
        if (!d.ok) {
          errEl.textContent = d.error || "Something went wrong.";
          errEl.hidden = false;
          return;
        }
        // Update hit counts
        var ch = document.getElementById("combat-hits-challenger");
        var op = document.getElementById("combat-hits-opponent");
        var rn = document.getElementById("combat-round-num");
        var mv = document.getElementById("combat-moves-left");
        if (ch) ch.textContent = d.challenger_hits;
        if (op) op.textContent = d.opponent_hits;
        if (rn) rn.textContent = d.current_round;

        // Append new log entries
        var log = document.getElementById("combat-log");
        if (log && d.rounds && d.rounds.length) {
          var latest = d.rounds[d.rounds.length - 1];
          var li = document.createElement("li");
          li.innerHTML = "<span>Round " + latest.round_number + "</span><span>" + latest.log_message + "</span>";
          log.appendChild(li);
          li.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        // Update moves remaining
        if (mv) {
          var cur = parseInt(mv.textContent, 10) || 0;
          var invested = parseInt(data.get("moves_invested"), 10) || 0;
          mv.textContent = Math.max(0, cur - invested);
        }

        okEl.textContent = "Move submitted! Waiting for opponent...";
        okEl.hidden = false;
        form.reset();
        // Re-check default
        var firstRadio = form.querySelector('input[name="action_type"]');
        if (firstRadio) firstRadio.checked = true;
      })
      .catch(function () {
        errEl.textContent = "Network error. Please try again.";
        errEl.hidden = false;
      })
      .finally(function () {
        if (btn) btn.disabled = false;
      });
  });
})();
