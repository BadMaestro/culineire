/* Hero image switcher — homepage only
   Keyboard accessible (ArrowLeft/ArrowRight within dot group).
   Respects prefers-reduced-motion via CSS (no JS override needed). */
(function () {
  'use strict';

  var SWIPE_THRESHOLD_PX = 48;

  var hero = document.querySelector('.hero--home');
  if (!hero) return;

  var slides = Array.from(hero.querySelectorAll('.hero__slide'));
  var dots   = Array.from(hero.querySelectorAll('.hero__dot'));
  if (slides.length < 2 || dots.length !== slides.length) return;

  var current = 0;
  var touchStartX = 0;
  var touchStartY = 0;

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

  function goNext() {
    goTo((current + 1) % slides.length);
  }

  function goPrevious() {
    goTo((current - 1 + slides.length) % slides.length);
  }

  dots.forEach(function (dot, i) {
    dot.addEventListener('click', function () { goTo(i); });
    dot.addEventListener('keydown', function (e) {
      if (e.key === 'ArrowRight') {
        e.preventDefault();
        goNext();
        dots[current].focus();
      }
      if (e.key === 'ArrowLeft') {
        e.preventDefault();
        goPrevious();
        dots[current].focus();
      }
    });
  });

  hero.addEventListener(
    'touchstart',
    function (event) {
      if (!event.touches || event.touches.length !== 1) return;
      touchStartX = event.touches[0].clientX;
      touchStartY = event.touches[0].clientY;
    },
    { passive: true }
  );

  hero.addEventListener(
    'touchend',
    function (event) {
      if (!event.changedTouches || event.changedTouches.length !== 1) return;

      var touchEndX = event.changedTouches[0].clientX;
      var touchEndY = event.changedTouches[0].clientY;
      var deltaX = touchStartX - touchEndX;
      var deltaY = touchStartY - touchEndY;

      if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX || Math.abs(deltaY) > Math.abs(deltaX)) {
        return;
      }

      if (deltaX > 0) {
        goNext();
      } else {
        goPrevious();
      }
    },
    { passive: true }
  );
}());
