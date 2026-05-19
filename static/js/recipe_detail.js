document.addEventListener("DOMContentLoaded", () => {

    /* ── Print button ── */
    const printButton = document.querySelector("[data-print-page]");
    if (printButton) {
        printButton.addEventListener("click", () => {
            window.print();
        });
    }

    /* ── Category tag pairing ──
     *
     * Sorts tags by rendered width descending, then interleaves
     * longest + shortest, 2nd longest + 2nd shortest, etc.
     * Each pair sums to roughly the same total width → all rows
     * are visually balanced, no orphan single-tag rows.
     */
    function packCategoryTags() {
        const container = document.querySelector("[data-categories-pack]");
        if (!container || container.children.length < 2) return;

        if (container.offsetWidth === 0) return;

        // Measure actual rendered widths
        const measured = Array.from(container.children)
            .map(el => ({ el, w: el.offsetWidth }))
            .sort((a, b) => b.w - a.w);   // longest first

        // Interleave: longest + shortest, 2nd longest + 2nd shortest …
        const ordered = [];
        let lo = 0, hi = measured.length - 1;
        while (lo <= hi) {
            ordered.push(measured[lo].el);
            if (lo !== hi) ordered.push(measured[hi].el);
            lo++;
            hi--;
        }

        // Re-insert in paired order
        ordered.forEach(el => container.appendChild(el));
    }

    packCategoryTags();

    // Re-pack on resize (debounced)
    let resizeTimer;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(packCategoryTags, 120);
    });

});
