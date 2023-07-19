function toggleFullscreen() {
    overrideUrlHashTarget = getCurrentUrlHashTarget();
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen().catch((err) => {}).then();
    } else {
        document.exitFullscreen();
    }
}

function defaultHashTarget() {
    return document.querySelector("header");
}

function getCandidateUrlHashTargets() {
    return document.querySelectorAll("header, #subfolders, article.image, footer");
}

function getCurrentUrlHashTarget() {
    return window.location.hash && document.querySelector(window.location.hash) || defaultHashTarget();
}

function isElementVisible(element) {
    const viewport = window.visualViewport;
    const rect = element.getBoundingClientRect();
    return (rect.top <= viewport.offsetTop + viewport.height &&
        viewport.offsetTop < rect.bottom - rect.height * 0.1875
    );
}

function getFirstVisibleUrlHashTarget() {
    const candidates = getCandidateUrlHashTargets();
    lastElement = candidates[candidates.length - 1];
    if (isElementVisible(lastElement)) {
        return lastElement;
    }
    for (const candidate of candidates) {
        if (isElementVisible(candidate)) {
            return candidate;
        }
    }
    return defaultHashTarget();
}

function getTargetUrlFirFirstVisibleUrlHashTarget() {
    const id = getFirstVisibleUrlHashTarget().id;
    return id && `#${id}` || window.location.origin + window.location.pathname + window.location.search;
}

overrideUrlHashTarget = null;
function scrollCurrentUrlHashTargetIntoView() {
    const currentUrlHashTarget = overrideUrlHashTarget || getCurrentUrlHashTarget();
    overrideUrlHashTarget = null;
    currentUrlHashTarget.scrollIntoView()
}

function setUrlHashToFirstVisibleUrlHashTargetNow() {
    const targetUrl = getTargetUrlFirFirstVisibleUrlHashTarget();
    window.history.replaceState(null, null, targetUrl);
    if (getCurrentUrlHashTarget() === scrollingTo) {
        scrollingTo = null;
    }
}

let _scrollEventThrottleTimeout = null;
let _scrollEventThrottled = false;
function setUrlHashToFirstVisibleUrlHashTargetThrottled() {
    if (!_scrollEventThrottled) {
        _scrollEventThrottled = true;
        _scrollEventThrottleTimeout = setTimeout(() => {
            setUrlHashToFirstVisibleUrlHashTargetNow();
            _scrollEventThrottled = false;
        }, 200);
        setUrlHashToFirstVisibleUrlHashTargetNow();
    }
}

document.addEventListener("scroll", (event) => {
    setUrlHashToFirstVisibleUrlHashTargetThrottled();
});

document.addEventListener("scrollend", (event) => {
    setUrlHashToFirstVisibleUrlHashTargetNow();
    scrollingTo = null;
});

document.addEventListener("fullscreenchange", (event) => {
    scrollCurrentUrlHashTargetIntoView();
});

document.addEventListener("onload", (event) => {
    scrollCurrentUrlHashTargetIntoView();
});

scrollingTo = null;
function scrollToNextUrlHashTarget(next) {
    const currentUrlHashTarget = scrollingTo || getCurrentUrlHashTarget();
    const candidates = getCandidateUrlHashTargets();
    for (let i = 0; i < candidates.length; i++) {
        if (candidates[i] === currentUrlHashTarget) {
            const newTarget = candidates[i + next];
            if (newTarget) {
                scrollingTo = newTarget;
                newTarget.scrollIntoView({ behavior: "smooth" });
                return;
            }
        }
    }
    // If we get stuck, try to get unstuck
    window.scrollBy({"top": 10 * next, "behavior": "smooth"});
}

document.addEventListener("keydown", (event) => {
    if (event.key === "ArrowDown" || event.key === "PageDown" || event.key === "ArrowRight" || event.key === " " && !event.shiftKey) {
        scrollToNextUrlHashTarget(+1);
        event.preventDefault();
    } else if (event.key === "ArrowUp" || event.key === "PageUp" || event.key === "ArrowLeft" || event.key === " " && event.shiftKey) {
        scrollToNextUrlHashTarget(-1);
        event.preventDefault();
    } else if (event.key === "f" || event.key === "Enter") {
        toggleFullscreen();
        event.preventDefault();
    }
});
