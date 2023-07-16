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

function getCandidateUrlHashTargets() {
    return document.querySelectorAll("header, article.image");
}

function getFirstVisibleImage() {
    const viewport = window.visualViewport;
    const candidates = getCandidateUrlHashTargets();
    for (const candidate of candidates) {
        const image = candidate.querySelector("picture") || candidate;
        const rect = image.getBoundingClientRect();
        // Check if the candidate vertically overlaps with the viewport
        if (rect.top <= viewport.offsetTop + viewport.height && viewport.offsetTop < rect.bottom) {
            return candidate;
        }
    }
}

function getTargetUrlForFirstVisibleImage() {
    const id = getFirstVisibleImage().id;
    return id && `#${id}` || window.location.origin + window.location.pathname + window.location.search;
}

let throttledPushState = null;

document.addEventListener("scroll", (event) => {
    const targetUrl = getTargetUrlForFirstVisibleImage();

    if (window.location.hash !== targetUrl) {
        clearTimeout(throttledPushState); // Clear any existing timeout

        if (!throttledPushState || throttledPushState.fired) {
            window.history.replaceState(null, null, targetUrl);
            throttledPushState = { fired: true }; // Mark the timeout as fired
        } else {
            throttledPushState = setTimeout(() => {
                const targetUrl = `#${getFirstVisibleImage().id}`;
                window.history.replaceState(null, null, targetUrl);
                throttledPushState.fired = true; // Mark the timeout as fired
            }, 1000); // 1000 milliseconds = 1 second
        }
    }
});

document.addEventListener("scrollend", (event) => {
    const targetUrl = getTargetUrlForFirstVisibleImage();
    window.history.replaceState(null, null, targetUrl);
});

document.addEventListener("keydown", (event) => {
    const currentImage = (
        window.location.hash && document.querySelector(`article.image${window.location.hash}`)
        || document.querySelector("header")
    );
    if (event.key === "ArrowDown" || event.key === "ArrowRight" || event.key === " " && !event.shiftKey) {
        const images = getCandidateUrlHashTargets();
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
        const images = getCandidateUrlHashTargets();
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
