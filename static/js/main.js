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
});
