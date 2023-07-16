function toggleFullscreen() {
    let elem = document.documentElement;

    if (!document.fullscreenElement) {
        elem.requestFullscreen().catch((err) => {
            alert(
                `Error attempting to enable fullscreen mode: ${err.message} (${err.name})`,
            );
        });
    } else {
        document.exitFullscreen();
    }
}

function getFirstVisibleImage() {
    const viewport = window.visualViewport;
    const candidates = document.querySelectorAll("header, article.image");
    let elements = [];
    for (const candidate of candidates) {
        const image = candidate.querySelector("picture") || candidate;
        const rect = image.getBoundingClientRect();
        // Check if the candidate vertically overlaps with the viewport
        if (rect.top <= viewport.offsetTop + viewport.height && viewport.offsetTop <= rect.bottom) {
            return candidate;
        }
    }
}

let throttledPushState = null;

document.addEventListener("scroll", (event) => {
    const targetUrl = `#${getFirstVisibleImage().id}`;

    if (window.location.hash !== targetUrl) {
        clearTimeout(throttledPushState); // Clear any existing timeout

        if (!throttledPushState || throttledPushState.fired) {
            window.history.replaceState(null, null, targetUrl);
            throttledPushState = { fired: true }; // Mark the timeout as fired
        } else {
            throttledPushState = setTimeout(() => {
                window.history.replaceState(null, null, targetUrl);
                throttledPushState.fired = true; // Mark the timeout as fired
            }, 1000); // 1000 milliseconds = 1 second
        }
    }
});

document.addEventListener("keydown", (event) => {
    const currentImage = document.querySelector(`article.image${window.location.hash}`) || document.querySelector("article.image");
    if (event.key === "ArrowDown" || event.key === "ArrowRight" || event.key === " " && !event.shiftKey) {
        const images = document.querySelectorAll("article.image");
        for (let i = 0; i < images.length; i++) {
            if (images[i] === currentImage) {
                const nextSibling = images[i + 1];
                if (nextSibling) {
                    nextSibling.scrollIntoView({ behavior: "smooth" });
                }
                event.preventDefault();
                return false;
            }
        }
    }
    if (event.key === "ArrowUp" || event.key === "ArrowLeft" || event.key === " " && event.shiftKey) {
        const images = document.querySelectorAll("article.image");
        for (let i = 0; i < images.length; i++) {
            if (images[i] === currentImage) {
                const prevSibling = images[i - 1];
                if (prevSibling) {
                    prevSibling.scrollIntoView({ behavior: "smooth" });
                }
                event.preventDefault();
                return false;
            }
        }
    }
});
