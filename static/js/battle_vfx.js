/* global window, document */
/* ==========================================================================
   CulinEire Battle VFX — window.CulinEireBattleVFX
   ==========================================================================

   PHASE 1 (current — production)
   --------------------------------
   CSS/SVG cinematic cloud shockwave overlay.
   Four layered blurred radial-gradient blobs expand from the viewport centre,
   warm culinary palette (copper, ivory, charcoal, gold dust), result card fades
   in at ~480 ms, entire overlay dissolves at ~1300 ms and is removed from the
   DOM at ~1800 ms. prefers-reduced-motion users get a simple bottom-right toast.

   Public API:
     window.CulinEireBattleVFX.showBattleResult(opts)
       opts.title   — badge text   (string, optional)
       opts.message — headline     (string, optional)
       opts.winner  — winner line  (string, optional)
       opts.score   — score line   (string, optional)
       opts.showCard — false to suppress the result card (default true)

     window.CulinEireBattleVFX.showWaveOnly()
       Convenience wrapper — cloud only, no result card.
       Used by the superuser dev-trigger avatar (removed after public launch).

   --------------------------------------------------------------------------
   PHASE 2 — Premium WebGL Shockwave Distortion  [NOT YET IMPLEMENTED]
   --------------------------------------------------------------------------
   Goal:
     After Phase 1 is stable in production, add an optional progressive WebGL
     enhancement. For a fraction of a second as the cloud passes over the
     viewport, the underlying page content subtly bends, ripples, and refracts —
     heat-haze / liquid-glass / cinematic pressure-wave feeling.

   Important:
     Phase 2 must NOT replace Phase 1. It is progressive enhancement only.
     Unsupported or low-power devices must fall back silently to Phase 1.

   Visual direction:
     - Subtle pressure-wave displacement of page content.
     - Organic, smoky, cloud-like distortion shape — NOT a ring or arcade ripple.
     - Optional tasteful blur, refraction, and very subtle chromatic aberration.
     - Short, non-invasive, premium 2026 cinematic feel.

   Technical options (evaluate at implementation time):
     - PixiJS displacement filter (lazy-loaded, small footprint).
     - Three.js post-processing pass with a custom GLSL fragment shader.
     - Lightweight custom WebGL canvas overlay + displacement map texture.
     - VFX-JS-style approach with a reused offscreen canvas.

   Integration sketch:
     function showBattleResult(opts) {
       if (prefersReducedMotion()) { showToast(opts); return; }
       showPhase1(opts);                        // always run Phase 1
       if (webGLCapable()) {
         loadWebGLModule().then(function (mod) {  // lazy-load, tree-shaken
           mod.fireDistortion({ duration: 800 }); // runs in parallel
         });
       }
     }

   Performance requirements:
     - Must not hurt Core Web Vitals (no layout shift, no blocking resources).
     - Must not block scrolling or interaction after the effect completes.
     - Must detect GPU/browser capability (WebGL2 + sufficient memory) before
       enabling — disable on low-end or mobile devices as needed.
     - Must remove the canvas and all WebGL objects after the effect ends.
     - Must produce no console errors and no memory leaks.
     - Must respect prefers-reduced-motion (skip entirely, not just tone down).

   Acceptance criteria:
     - Capable devices: short premium cinematic pressure-wave distortion over
       the Phase 1 cloud — the two effects compose naturally.
     - Incapable / low-power devices: Phase 1 CSS cloud only, no errors.
     - Reduced-motion users: simple fade-in toast, no animation.
     - Visual impression: "premium 2026 cinematic website effect", not a game.
   ========================================================================== */
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
