document.addEventListener("DOMContentLoaded", () => {

    /* ── Print button ── */
    const printButton = document.querySelector("[data-print-page]");
    if (printButton) {
        printButton.addEventListener("click", () => {
            window.print();
        });
    }

    /* ── Category tag two-column split ──
     *
     * Sorts tags by rendered width descending, splits in half:
     * - Left column  → longer names, left-aligned
     * - Right column → shorter names, right-aligned
     * Re-runs on resize so columns stay correct at any viewport.
     */
    function packCategoryTags() {
        const container = document.querySelector("[data-categories-pack]");
        if (!container) return;

        // Collect all tag links from wherever they currently are
        const allTags = Array.from(
            container.querySelectorAll("a.detail-page__source-link")
        );
        if (allTags.length < 2) return;

        // Temporarily move all tags back to container for measurement
        allTags.forEach(el => container.appendChild(el));
        container.querySelectorAll(".source-col").forEach(el => el.remove());

        if (container.offsetWidth === 0) return;

        // Sort by rendered width, longest first
        const sorted = allTags
            .map(el => ({ el, w: el.offsetWidth }))
            .sort((a, b) => b.w - a.w);

        const half = Math.ceil(sorted.length / 2);

        // Build two column divs
        const leftCol  = document.createElement("div");
        const rightCol = document.createElement("div");
        leftCol.className  = "source-col source-col--left";
        rightCol.className = "source-col source-col--right";

        sorted.slice(0, half).forEach(item => leftCol.appendChild(item.el));
        sorted.slice(half).forEach(item => rightCol.appendChild(item.el));

        container.innerHTML = "";
        container.appendChild(leftCol);
        container.appendChild(rightCol);
    }

    packCategoryTags();

    // Re-pack on resize (debounced)
    let resizeTimer;
    window.addEventListener("resize", () => {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(packCategoryTags, 120);
    });

});
