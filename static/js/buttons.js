(function () {
    'use strict';

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
}());
