document.addEventListener("DOMContentLoaded", () => {

    /* ── Print button ── */
    const printButton = document.querySelector("[data-print-page]");
    if (printButton) {
        printButton.addEventListener("click", () => {
            window.print();
        });
    }

    /* ── Category tag bin-packing ──
     *
     * Reorders tags so each row is packed as tightly as possible:
     * 1. For each row, greedily pick the widest tag that still fits.
     * 2. Repeat until no tag fits in the current row.
     * 3. Start a new row with the widest remaining tag.
     * This eliminates the orphan/scatter effect of plain flex-wrap.
     */
    function packCategoryTags() {
        const container = document.querySelector("[data-categories-pack]");
        if (!container || container.children.length < 2) return;

        const containerWidth = container.offsetWidth;
        if (containerWidth === 0) return;

        // Read the actual computed gap (px)
        const gap = parseFloat(getComputedStyle(container).gap) || 6;

        // Snapshot current tag widths before any reordering
        const measured = Array.from(container.children).map(el => ({
            el,
            w: el.offsetWidth,
        }));

        const remaining = measured.slice();
        const ordered = [];

        while (remaining.length > 0) {
            let rowUsed = 0;
            let placed;

            do {
                placed = false;
                const available = containerWidth - rowUsed - (rowUsed > 0 ? gap : 0);

                // Find the widest tag that fits in remaining space
                let bestIdx = -1;
                let bestW = -1;
                for (let i = 0; i < remaining.length; i++) {
                    const w = remaining[i].w;
                    if (w <= available && w > bestW) {
                        bestIdx = i;
                        bestW = w;
                    }
                }

                // Row is empty but nothing fits → force the widest remaining tag
                if (bestIdx === -1 && rowUsed === 0) {
                    let largestIdx = 0;
                    for (let i = 1; i < remaining.length; i++) {
                        if (remaining[i].w > remaining[largestIdx].w) largestIdx = i;
                    }
                    bestIdx = largestIdx;
                    bestW = remaining[largestIdx].w;
                }

                if (bestIdx >= 0) {
                    ordered.push(remaining[bestIdx].el);
                    rowUsed += (rowUsed > 0 ? gap : 0) + bestW;
                    remaining.splice(bestIdx, 1);
                    placed = true;
                }
            } while (placed && remaining.length > 0);
        }

        // Re-insert in packed order (appendChild moves existing elements)
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
