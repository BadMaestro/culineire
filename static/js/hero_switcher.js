/* Hero image switcher — homepage only
   Keyboard accessible (ArrowLeft/ArrowRight within dot group).
   Respects prefers-reduced-motion via CSS (no JS override needed). */
(function () {
  'use strict';

  var hero = document.querySelector('.hero--home');
  if (!hero) return;

  var slides = Array.from(hero.querySelectorAll('.hero__slide'));
  var dots   = Array.from(hero.querySelectorAll('.hero__dot'));
  if (slides.length < 2 || dots.length !== slides.length) return;

  var current = 0;

  function goTo(index) {
    if (index === current) return;
    slides[current].classList.remove('is-active');
    dots[current].classList.remove('is-active');
    dots[current].setAttribute('aria-pressed', 'false');
    current = index;
    slides[current].classList.add('is-active');
    dots[current].classList.add('is-active');
    dots[current].setAttribute('aria-pressed', 'true');
  }

  dots.forEach(function (dot, i) {
    dot.addEventListener('click', function () { goTo(i); });
    dot.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        goTo((current + 1) % slides.length);
        dots[(current) % slides.length].focus();
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goTo((current - 1 + slides.length) % slides.length);
        dots[(current) % slides.length].focus();
      }
    });
  });
}());
