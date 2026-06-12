/* global window, document */
window.CulinEireBattleVFX = (function () {
    'use strict';

    var DISSOLVE_AT  = 1300;
    var REMOVE_AFTER = 1800;

    function prefersReducedMotion() {
        return window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    }

    function buildCard(opts) {
        var card = document.createElement('div');
        card.className = 'ce-battle-vfx__card';

        if (opts.title) {
            var badge = document.createElement('div');
            badge.className = 'ce-battle-vfx__badge';
            badge.textContent = opts.title;
            card.appendChild(badge);
        }

        var title = document.createElement('p');
        title.className = 'ce-battle-vfx__title';
        title.textContent = opts.message || 'Battle Over';
        card.appendChild(title);

        if (opts.winner) {
            var winner = document.createElement('p');
            winner.className = 'ce-battle-vfx__winner';
            winner.textContent = opts.winner;
            card.appendChild(winner);
        }

        if (opts.score) {
            var score = document.createElement('p');
            score.className = 'ce-battle-vfx__score';
            score.textContent = opts.score;
            card.appendChild(score);
        }

        return card;
    }

    function showToast(opts) {
        var wrap = document.createElement('div');
        wrap.className = 'ce-battle-vfx ce-battle-vfx--toast';
        wrap.appendChild(buildCard(opts));
        document.body.appendChild(wrap);
        setTimeout(function () { wrap.remove(); }, 2700);
    }

    function showBattleResult(opts) {
        opts = opts || {};

        if (prefersReducedMotion()) {
            showToast(opts);
            return;
        }

        /* Body micro-impact */
        document.body.classList.add('ce-vfx-impact');
        document.body.addEventListener('animationend', function onImpactEnd() {
            document.body.classList.remove('ce-vfx-impact');
            document.body.removeEventListener('animationend', onImpactEnd);
        });

        /* Overlay */
        var wrap = document.createElement('div');
        wrap.className = 'ce-battle-vfx';

        for (var i = 1; i <= 4; i++) {
            var layer = document.createElement('div');
            layer.className = 'ce-battle-vfx__layer ce-battle-vfx__layer--' + i;
            wrap.appendChild(layer);
        }

        if (opts.showCard !== false) {
            wrap.appendChild(buildCard(opts));
        }

        document.body.appendChild(wrap);

        /* Dissolve then remove */
        setTimeout(function () {
            wrap.classList.add('ce-battle-vfx--dissolving');
        }, DISSOLVE_AT);

        setTimeout(function () {
            wrap.remove();
        }, REMOVE_AFTER);
    }

    function showWaveOnly() {
        showBattleResult({ showCard: false });
    }

    return {
        showBattleResult: showBattleResult,
        showWaveOnly: showWaveOnly,
    };
}());
