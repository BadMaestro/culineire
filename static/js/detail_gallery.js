(function () {
    const ANIMATION_DURATION_MS = 540;
    const SWIPE_THRESHOLD_PX = 50;

    const gallery = document.querySelector("[data-gallery]");
    if (!gallery) {
        return;
    }

    const items = Array.from(gallery.querySelectorAll("[data-gallery-item]"));
    const prevButton = gallery.querySelector("[data-gallery-prev]");
    const nextButton = gallery.querySelector("[data-gallery-next]");

    if (items.length <= 1 || !prevButton || !nextButton) {
        return;
    }

    const totalItems = items.length;
    let currentIndex = 0;
    let isAnimating = false;
    let animationTimer = null;
    let pendingIndex = null;
    let touchStartX = 0;

    function clampIndex(index) {
        return Math.min(Math.max(index, 0), totalItems - 1);
    }

    function resetItemClasses(item) {
        item.classList.remove(
            "is-current",
            "is-prev",
            "is-next",
            "is-far-prev",
            "is-far-next"
        );
    }

    function updateArrows() {
        prevButton.hidden = currentIndex === 0;
        nextButton.hidden = currentIndex === totalItems - 1;
        prevButton.setAttribute("aria-disabled", currentIndex === 0 ? "true" : "false");
        nextButton.setAttribute("aria-disabled", currentIndex === totalItems - 1 ? "true" : "false");
    }

    function applyState() {
        items.forEach(function (item, index) {
            const isCurrent = index === currentIndex;

            resetItemClasses(item);
            item.setAttribute("aria-hidden", isCurrent ? "false" : "true");

            if (isCurrent) {
                item.classList.add("is-current");
                return;
            }

            if (index === currentIndex - 1) {
                item.classList.add("is-prev");
                return;
            }

            if (index === currentIndex + 1) {
                item.classList.add("is-next");
                return;
            }

            if (index < currentIndex) {
                item.classList.add("is-far-prev");
                return;
            }

            item.classList.add("is-far-next");
        });

        updateArrows();
    }

    function goTo(index) {
        const nextIndex = clampIndex(index);

        if (nextIndex === currentIndex) {
            return;
        }

        if (isAnimating) {
            pendingIndex = nextIndex;
            return;
        }

        isAnimating = true;
        currentIndex = nextIndex;
        applyState();

        window.clearTimeout(animationTimer);
        animationTimer = window.setTimeout(function () {
            isAnimating = false;

            if (pendingIndex !== null) {
                const queuedIndex = pendingIndex;
                pendingIndex = null;
                goTo(queuedIndex);
            }
        }, ANIMATION_DURATION_MS);
    }

    prevButton.addEventListener("click", function () {
        goTo(currentIndex - 1);
    });

    nextButton.addEventListener("click", function () {
        goTo(currentIndex + 1);
    });

    items.forEach(function (item, index) {
        item.addEventListener("click", function () {
            if (index === currentIndex - 1 || index === currentIndex + 1) {
                goTo(index);
            }
        });
    });

    gallery.addEventListener("keydown", function (event) {
        if (event.key === "ArrowLeft") {
            event.preventDefault();
            goTo(currentIndex - 1);
        }

        if (event.key === "ArrowRight") {
            event.preventDefault();
            goTo(currentIndex + 1);
        }
    });

    gallery.addEventListener(
        "touchstart",
        function (event) {
            touchStartX = event.touches[0].clientX;
        },
        { passive: true }
    );

    gallery.addEventListener(
        "touchend",
        function (event) {
            const touchEndX = event.changedTouches[0].clientX;
            const deltaX = touchStartX - touchEndX;

            if (Math.abs(deltaX) < SWIPE_THRESHOLD_PX) {
                return;
            }

            goTo(currentIndex + (deltaX > 0 ? 1 : -1));
        },
        { passive: true }
    );

    applyState();
})();