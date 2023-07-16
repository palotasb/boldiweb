function toggleFullscreen() {
    let elem = document.documentElement;

    if (!document.fullscreenElement) {
        elem.requestFullscreen().catch((err) => {}).then();
    } else {
        document.exitFullscreen();
    }
}

function getCurrentImageOrHeader() {
    return window.location.hash && document.querySelector(`article.image${window.location.hash}`) || document.querySelector("header");
}

function scrollCurrentImageIntoView() {
    const currentImage = getCurrentImageOrHeader();
    currentImage.scrollIntoView()
}

document.addEventListener("fullscreenchange", (event) => {
    scrollCurrentImageIntoView();
});

function getCandidateUrlHashTargets() {
    return document.querySelectorAll("header, article.image, #bottom");
}

function getFirstVisibleImage() {
    const viewport = window.visualViewport;
    const candidates = getCandidateUrlHashTargets();
    for (const candidate of candidates) {
        const image = candidate.querySelector("picture") || candidate;
        const rect = image.getBoundingClientRect();
        // Check if the candidate vertically overlaps with the viewport
        console.log(`${image.id}: rect.top=${rect.top} <= viewport.offsetTop=${viewport.offsetTop} + viewport.height=${viewport.height} && viewport.offsetTop=${viewport.offsetTop} < rect.bottom=${rect.bottom}`)
        if (rect.top <= viewport.offsetTop + viewport.height && viewport.offsetTop < rect.bottom - rect.height * 0.1875) {
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
    if (event.key === "ArrowDown" || event.key === "ArrowRight" || event.key === " " && !event.shiftKey) {
        const currentImage = getCurrentImageOrHeader();
        const images = getCandidateUrlHashTargets();
        for (let i = 0; i < images.length; i++) {
            if (images[i] === currentImage) {
                const nextSibling = images[i + 1];
                if (nextSibling) {
                    nextSibling.scrollIntoView({ behavior: "smooth" });
                }
                event.preventDefault();
                return;
            }
        }
        // If we get stuck, try to get unstuck
        window.scrollBy({"top": 10, "behavior": "smooth"});
        event.preventDefault();
        return;
    }
    if (event.key === "ArrowUp" || event.key === "ArrowLeft" || event.key === " " && event.shiftKey) {
        const currentImage = getCurrentImageOrHeader();
        const images = getCandidateUrlHashTargets();
        for (let i = 0; i < images.length; i++) {
            if (images[i] === currentImage) {
                const prevSibling = images[i - 1];
                if (prevSibling) {
                    prevSibling.scrollIntoView({ behavior: "smooth" });
                }
                event.preventDefault();
                return ;
            }
        }
        // If we get stuck, try to get unstuck
        window.scrollBy({"top": -10, "behavior": "smooth"});
        event.preventDefault();
        return;
    }
    if (event.key === "f" || event.key === "Enter") {
        toggleFullscreen();
    }
});
