document.addEventListener("DOMContentLoaded", function () {
  const toggle = document.querySelector(".nav-toggle");
  const nav = document.querySelector(".main-nav");

  if (!toggle || !nav) return;

  toggle.addEventListener("click", function () {
    const isOpen = nav.classList.toggle("main-nav--open");
    toggle.setAttribute("aria-expanded", isOpen ? "true" : "false");
  });
});
