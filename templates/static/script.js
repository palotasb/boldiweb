function toggleFullscreen() {
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
    return document.querySelectorAll("header, article.image, #bottom");
}

function getCurrentUrlHashTarget() {
    return window.location.hash && document.querySelector(window.location.hash) || defaultHashTarget();
}

function getFirstVisibleUrlHashTarget() {
    const viewport = window.visualViewport;
    const candidates = getCandidateUrlHashTargets();
    for (const candidate of candidates) {
        const rect = candidate.getBoundingClientRect();
        if (rect.top <= viewport.offsetTop + viewport.height &&
            viewport.offsetTop < rect.bottom - rect.height * 0.1875
        ) { return candidate; }
    }
    return defaultHashTarget();
}

function getTargetUrlFirFirstVisibleUrlHashTarget() {
    const id = getFirstVisibleUrlHashTarget().id;
    return id && `#${id}` || window.location.origin + window.location.pathname + window.location.search;
}

function scrollCurrentUrlHashTargetIntoView() {
    const currentUrlHashTarget = getCurrentUrlHashTarget();
    currentUrlHashTarget.scrollIntoView()
}

function setUrlHashToFirstVisibleUrlHashTargetNow() {
    const targetUrl = getTargetUrlFirFirstVisibleUrlHashTarget();
    window.history.replaceState(null, null, targetUrl);
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
});

document.addEventListener("fullscreenchange", (event) => {
    scrollCurrentUrlHashTargetIntoView();
});

document.addEventListener("onload", (event) => {
    scrollCurrentUrlHashTargetIntoView();
});

function scrollToNextUrlHashTarget(next) {
    const currentUrlHashTarget = getCurrentUrlHashTarget();
    const candidates = getCandidateUrlHashTargets();
    for (let i = 0; i < candidates.length; i++) {
        if (candidates[i] === currentUrlHashTarget) {
            const nextSibling = candidates[i + next];
            if (nextSibling) {
                nextSibling.scrollIntoView({ behavior: "smooth" });
                return;
            } else {
                console.log("Cannot find next sibling", candidates[i]);
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
