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

    document.addEventListener('click', function (e) {
        /* Enter Arena button — amber */
        if (e.target.closest('.hero-battle-panel__cta')) {
            fireFloatingRipple(e.clientX, e.clientY, 'rgba(248, 210, 138, 0.5)');
            return;
        }
        /* Header nav links — warm brown, skip Chef Battle */
        var navEl = e.target.closest(
            '.ce-nav__link:not(.ce-nav__link--battle), .ce-nav__button, .ce-nav__text'
        );
        if (navEl) {
            fireFloatingRipple(e.clientX, e.clientY, 'rgba(139, 115, 85, 0.22)');
        }
    });
}());
