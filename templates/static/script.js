function toggleFullScreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen({navigationUI: "hide"});
    } else {
        document.exitFullscreen();
    }
}

function defaultHashTarget() {
    return document.querySelector("header");
}

function getCandidateUrlHashTargets() {
    return document.querySelectorAll("header, #subfolders, #thumbnails, article.image, footer");
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

function isElementPreciselyScrolledIntoView(element) {
    const viewport = window.visualViewport;
    const rect = element.getBoundingClientRect();
    return (viewport.offsetTop -5 <= rect.top && rect.top <= viewport.offsetTop + 5);
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

function scrollCurrentUrlHashTargetIntoView(scrollBehavior) {
    scrollBehavior = scrollBehavior || "auto";
    const currentUrlHashTarget = getCurrentUrlHashTarget();
    currentUrlHashTarget.scrollIntoView({behavior: scrollBehavior})
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
    scrollCurrentUrlHashTargetIntoView("instant");
});

document.addEventListener("onload", (event) => {
    scrollCurrentUrlHashTargetIntoView();
});

scrollingTo = null;
function scrollToNextUrlHashTarget(next) {
    const currentUrlHashTarget = scrollingTo || getCurrentUrlHashTarget();
    if (!scrollingTo && !isElementPreciselyScrolledIntoView(currentUrlHashTarget) && next === 1) {
        next = 0;
    }
    const candidates = getCandidateUrlHashTargets();
    for (let i = 0; i < candidates.length; i++) {
        if (candidates[i] === currentUrlHashTarget) {
            const newTarget = candidates[i + next];
            if (newTarget) {
                scrollingTo = newTarget;
                newTarget.scrollIntoView();
                return;
            }
        }
    }
    // If we get stuck, try to get unstuck
    window.scrollBy({"top": 10 * next});
}

document.addEventListener("keydown", (event) => {
    if (
        event.key === "ArrowDown"
        || event.key === "PageDown"
        || event.key === "ArrowRight" 
        || event.key === "j"
        || (event.key === " " && !event.shiftKey)) {
        scrollToNextUrlHashTarget(+1);
    } else if (
        event.key === "ArrowUp"
        || event.key === "PageUp"
        || event.key === "ArrowLeft"
        || event.key === "k"
        || (event.key === " " && event.shiftKey)) {
        scrollToNextUrlHashTarget(-1);
    } else if (event.key === "h" || event.key === "e") {
        document.querySelector("header").scrollIntoView();
    } else if (event.key === "l") {
        document.querySelector("footer").scrollIntoView();
    } else if (event.key === "g") {
        document.querySelector("#thumbnails, #subfolders").scrollIntoView();
    } else if (event.key === "p") {
        document.querySelector("#images").scrollIntoView();
    } else if (event.key === "f" || event.key === "Enter") {
        toggleFullScreen();
    } else {
        // DON'T event.preventDefault() if event isn't handled 
        return;
    }
    event.preventDefault();
});
