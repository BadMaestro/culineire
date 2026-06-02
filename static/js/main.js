// Disable browser scroll restoration so iOS PWA does not open pages
// scrolled to a remembered position after a no-cache reload.
if ("scrollRestoration" in history) {
  history.scrollRestoration = "manual";
}

document.addEventListener("DOMContentLoaded", () => {
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

    navButton.addEventListener("click", () => {
      const isOpen = nav.classList.toggle(openClass);
      navButton.setAttribute("aria-expanded", String(isOpen));
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
      const card = track.querySelector(".recipe-card");

      if (!card) {
        return Math.max(track.clientWidth * 0.85, 1);
      }

      const styles = window.getComputedStyle(track);
      const gap = parseFloat(styles.columnGap || styles.gap || "0");
      const cardWidth = card.getBoundingClientRect().width;

      return Math.max(cardWidth + (Number.isNaN(gap) ? 0 : gap), 1);
    };

    const updateControls = () => {
      track.style.marginInline = "0";
      const maxScrollLeft = Math.max(track.scrollWidth - track.clientWidth, 0);
      const canScroll = maxScrollLeft > 2;
      const atStart = track.scrollLeft <= 1;
      const atEnd = track.scrollLeft >= maxScrollLeft - 1;

      if (canScroll) {
        track.style.marginInline = "";
        track.style.justifyContent = "";
      } else {
        track.style.justifyContent = "center";
      }

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

    requestAnimationFrame(updateControls);

    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(updateControls);
      resizeObserver.observe(track);
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
      const img = bg && bg.querySelector("img[src]");
      if (!img) return;

      const btn = document.createElement("button");
      btn.className = "hero-peek-btn";
      btn.type = "button";
      btn.setAttribute("aria-label", "View full image");
      btn.innerHTML = eyeSvg + " Photo";
      hero.appendChild(btn);

      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        lightboxImg.src = img.currentSrc || img.src;
        lightboxImg.alt = img.alt || "";
        lightbox.classList.add("hero-lightbox--open");
        document.body.style.overflow = "hidden";
        requestAnimationFrame(() => lightboxClose.focus());
      });
    });

    const closeLightbox = () => {
      lightbox.classList.remove("hero-lightbox--open");
      lightbox.addEventListener(
        "transitionend",
        () => {
          if (!lightbox.classList.contains("hero-lightbox--open")) {
            lightboxImg.src = "";
            document.body.style.overflow = "";
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

  // ==== Amuse-Bouche 3-dot menus ====
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

  // ==== Amuse-Bouche share buttons ====
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

  // ==== Amuse-Bouche bottom sheet (slide-up) ====
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

  // ==== AB hero actions burger (mobile) ====
  document.addEventListener("click", (e) => {
    const toggle = e.target.closest(".ab-hero-toggle");
    if (!toggle) return;
    const actions = toggle.closest(".ab-hero-actions");
    if (!actions) return;
    const isOpen = actions.classList.toggle("is-open");
    toggle.setAttribute("aria-expanded", String(isOpen));
  });

  // ==== Amuse-Bouche like / save — AJAX toggle (no page reload, no scroll reset) ====
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
});
