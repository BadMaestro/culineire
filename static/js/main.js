document.addEventListener("DOMContentLoaded", () => {
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

    const getSingleRowHeight = () => {
      const firstItem = categoryNav.querySelector(".category-nav__item");
      const referenceElement = firstItem || categoryNav;
      const computed = window.getComputedStyle(referenceElement);
      const lineHeight = parseFloat(computed.lineHeight);

      if (!Number.isNaN(lineHeight) && lineHeight > 0) {
        return Math.ceil(lineHeight);
      }

      const fontSize = parseFloat(computed.fontSize);
      return Math.ceil((Number.isNaN(fontSize) ? 13 : fontSize) * 1.4);
    };

    const applyState = () => {
      wrap.style.height = "auto";

      const fullHeight = Math.ceil(categoryNav.scrollHeight);
      const collapsedHeight = getSingleRowHeight();
      const needsToggle = fullHeight > collapsedHeight + 4;

      if (!needsToggle) {
        wrap.style.height = "auto";
        wrap.classList.remove("category-nav-wrap--collapsed", "category-nav-wrap--expanded");
        button.hidden = true;
        button.setAttribute("aria-expanded", "false");
        buttonLabel.textContent = "View All";
        return;
      }

      button.hidden = false;

      if (expanded) {
        wrap.style.height = `${fullHeight}px`;
        wrap.classList.remove("category-nav-wrap--collapsed");
        wrap.classList.add("category-nav-wrap--expanded");
        button.setAttribute("aria-expanded", "true");
        button.setAttribute("aria-label", "Collapse recipe categories");
        buttonLabel.textContent = "View Less";
      } else {
        wrap.style.height = `${collapsedHeight}px`;
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

    requestAnimationFrame(() => {
      expanded = false;
      applyState();
    });

    let resizeTimer = null;
    window.addEventListener("resize", () => {
      clearTimeout(resizeTimer);
      resizeTimer = setTimeout(() => {
        applyState();
      }, 80);
    });
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

    requestAnimationFrame(updateControls);

    if ("ResizeObserver" in window) {
      const resizeObserver = new ResizeObserver(updateControls);
      resizeObserver.observe(track);
    } else {
      window.addEventListener("resize", updateControls);
    }
  });
});
