(function () {
    const copyButton = document.querySelector("[data-copy-url]");

    if (copyButton) {
        const copyUrl = copyButton.dataset.copyUrl || "";
        const copyLabel = copyButton.lastElementChild;
        const defaultLabel = copyLabel ? copyLabel.textContent : copyButton.textContent.trim();
        let copyTimer = null;

        copyButton.addEventListener("click", async () => {
            if (!copyUrl || !navigator.clipboard || typeof navigator.clipboard.writeText !== "function") {
                return;
            }

            try {
                await navigator.clipboard.writeText(copyUrl);

                if (copyLabel) {
                    copyLabel.textContent = "Copied";
                } else {
                    copyButton.textContent = "Copied";
                }

                window.clearTimeout(copyTimer);
                copyTimer = window.setTimeout(() => {
                    if (copyLabel) {
                        copyLabel.textContent = defaultLabel;
                    } else {
                        copyButton.textContent = defaultLabel;
                    }
                }, 2000);
            } catch (error) {
                // Leave the button unchanged when clipboard access is unavailable.
            }
        });
    }

    const gallery = document.querySelector("[data-gallery]");

    if (!gallery) {
        return;
    }

    const items = Array.from(gallery.querySelectorAll("[data-gallery-item]"));
    const prevButton = gallery.querySelector("[data-gallery-prev]");
    const nextButton = gallery.querySelector("[data-gallery-next]");

    if (!items.length || !prevButton || !nextButton) {
        return;
    }

    const totalItems = items.length;
    let currentIndex = 0;
    let isAnimating = false;
    let animationTimer = null;

    function clampIndex(index) {
        if (index < 0) {
            return 0;
        }

        if (index > totalItems - 1) {
            return totalItems - 1;
        }

        return index;
    }

    function resetItemClasses(item) {
        item.classList.remove(
            "is-current",
            "is-prev",
            "is-next",
            "is-hidden",
            "is-far-prev",
            "is-far-next"
        );
    }

    function pauseAllVideos() {
        items.forEach((item) => {
            const video = item.querySelector("video");

            if (video) {
                video.pause();
                video.controls = false;
            }
        });
    }

    function syncMediaState() {
        items.forEach((item, index) => {
            const video = item.querySelector("video");

            if (!video) {
                return;
            }

            const isCurrent = index === currentIndex;

            if (isCurrent) {
                video.controls = true;
                video.muted = false;
            } else {
                video.pause();
                video.currentTime = 0;
                video.controls = false;
                video.muted = true;
            }
        });
    }

    function updateArrows() {
        if (totalItems <= 1) {
            prevButton.hidden = true;
            nextButton.hidden = true;
            return;
        }

        prevButton.hidden = currentIndex === 0;
        nextButton.hidden = currentIndex === totalItems - 1;
    }

    function applyState() {
        items.forEach((item, index) => {
            resetItemClasses(item);

            if (index === currentIndex) {
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

            if (index < currentIndex - 1) {
                item.classList.add("is-far-prev");
                return;
            }

            if (index > currentIndex + 1) {
                item.classList.add("is-far-next");
                return;
            }

            item.classList.add("is-hidden");
        });

        updateArrows();
        syncMediaState();
    }

    function goTo(index) {
        const nextIndex = clampIndex(index);

        if (nextIndex === currentIndex || isAnimating) {
            return;
        }

        isAnimating = true;
        currentIndex = nextIndex;
        pauseAllVideos();
        applyState();

        window.clearTimeout(animationTimer);
        animationTimer = window.setTimeout(() => {
            isAnimating = false;
        }, 540);
    }

    prevButton.addEventListener("click", () => {
        goTo(currentIndex - 1);
    });

    nextButton.addEventListener("click", () => {
        goTo(currentIndex + 1);
    });

    items.forEach((item, index) => {
        item.addEventListener("click", () => {
            if (index === currentIndex - 1 || index === currentIndex + 1) {
                goTo(index);
            }
        });
    });

    applyState();
})();
