(function () {
    'use strict';

    /* ── Internal ripple (clipped inside button) ── */
    var SELECTOR = [
        '.btn',
        '.btn-primary',
        '.btn-secondary',
        '.authoring-submit',
        '.detail-button',
        '.mod-btn',
        '.msg-action-btn',
        '.mod-tool-link',
        '.collection-btn',
        '.sponsors-contact-btn',
        '.tt-contact-btn',
        '.spm-buy-btn',
        '.spm-visit-btn',
        '.spm-admin-approve',
        '.spm-admin-reject',
        '.site-battle-widget__console-link',
        '.site-battle-widget .btn-primary',
    ].join(', ');

    document.addEventListener('click', function (e) {
        var btn = e.target.closest(SELECTOR);
        if (!btn) return;

        var ripple = document.createElement('span');
        ripple.className = 'btn-ripple';

        var rect = btn.getBoundingClientRect();
        var size = Math.max(rect.width, rect.height) * 2;
        ripple.style.width  = size + 'px';
        ripple.style.height = size + 'px';
        ripple.style.left   = (e.clientX - rect.left - size / 2) + 'px';
        ripple.style.top    = (e.clientY - rect.top  - size / 2) + 'px';

        btn.appendChild(ripple);
        ripple.addEventListener('animationend', function () { ripple.remove(); });
    });

    /* ── Floating ripple (expands beyond button, sponsors-style) ── */
    function fireFloatingRipple(x, y, color) {
        var el = document.createElement('div');
        el.className = 'ui-floating-ripple';
        el.style.left       = x + 'px';
        el.style.top        = y + 'px';
        el.style.background = color;
        document.body.appendChild(el);
        el.addEventListener('animationend', function () { el.remove(); });
    }

    /* ── Chef Battle rim-glint: vary speed + direction between cycles ── */
    (function () {
        var btn = document.querySelector('.ce-nav__link--battle');
        if (!btn) return;
        if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
        function cycle() {
            var dur = (2.0 + Math.random() * 2.4).toFixed(1);
            btn.style.setProperty('--ce-glint-dur', dur + 's');
            /* Wait two alternation passes (CW + CCW) plus a random rest */
            setTimeout(cycle, parseFloat(dur) * 2000 + 600 + Math.random() * 2200);
        }
        setTimeout(cycle, 400 + Math.random() * 800);
    }());

    document.addEventListener('click', function (e) {
        /* Enter Arena button — amber */
        if (e.target.closest('.hero-battle-panel__cta')) {
            fireFloatingRipple(e.clientX, e.clientY, 'rgba(248, 210, 138, 0.5)');
            return;
        }
        /* Header nav links — warm brown, skip Chef Battle */
        var navEl = e.target.closest(
            '.ce-nav__link:not(.ce-nav__link--battle), .ce-nav__button, .ce-nav__text, '
            + '.site-battle-widget__menu a, .site-battle-widget__toggle'
        );
        if (navEl) {
            fireFloatingRipple(e.clientX, e.clientY, 'rgba(139, 115, 85, 0.22)');
        }
    });
}());
