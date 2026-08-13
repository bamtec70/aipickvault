/**
 * Truth Desk deep-link play
 * When arriving with #x-post-… / #yt-… / #rumble-… / #truth-… :
 *  1) scroll the card into view
 *  2) start YouTube / Rumble when possible (muted autoplay for reliability)
 *  3) for X/Twitter embeds: focus the card (platform blocks autoplay without gesture)
 *
 * Loaded from Truth Desk post HTML:
 *   <script src="https://aipickvault.com/td-hash-play.js" defer></script>
 */
(function () {
  "use strict";
  if (window.__tdHashPlay) return;
  window.__tdHashPlay = true;

  function cleanHash() {
    try {
      return String(location.hash || "")
        .replace(/^#/, "")
        .trim();
    } catch (e) {
      return "";
    }
  }

  function findTarget(hash) {
    if (!hash) return null;
    var el = document.getElementById(hash);
    if (el) return el;
    // name= fallbacks used on some host headers
    var named = document.getElementsByName(hash);
    if (named && named.length) return named[0];
    return null;
  }

  function scrollToEl(el) {
    if (!el) return;
    try {
      el.scrollIntoView({ behavior: "smooth", block: "center" });
    } catch (e) {
      try {
        el.scrollIntoView(true);
      } catch (e2) {}
    }
    try {
      el.style.outline = "2px solid #f59e0b";
      el.style.outlineOffset = "4px";
      setTimeout(function () {
        try {
          el.style.outline = "";
          el.style.outlineOffset = "";
        } catch (e3) {}
      }, 2600);
    } catch (e4) {}
  }

  function isYouTubeIframe(iframe) {
    if (!iframe || iframe.tagName !== "IFRAME") return false;
    var src = iframe.getAttribute("src") || iframe.src || "";
    return /youtube(?:-nocookie)?\.com\/embed\//i.test(src);
  }

  function isRumbleIframe(iframe) {
    if (!iframe || iframe.tagName !== "IFRAME") return false;
    var src = iframe.getAttribute("src") || iframe.src || "";
    return /rumble\.com\/embed/i.test(src);
  }

  function withAutoplay(src, muted) {
    if (!src) return src;
    var next = src;
    // strip conflicting flags then add
    next = next.replace(/([?&])autoplay=\d+/gi, "$1").replace(/([?&])mute=\d+/gi, "$1");
    next = next.replace(/[?&]$/, "");
    var join = next.indexOf("?") >= 0 ? "&" : "?";
    next += join + "autoplay=1";
    if (muted) next += "&mute=1";
    // enable JS API for postMessage play
    if (/youtube(?:-nocookie)?\.com\/embed\//i.test(next) && !/[?&]enablejsapi=1/i.test(next)) {
      next += "&enablejsapi=1";
    }
    return next;
  }

  function playYouTube(iframe) {
    if (!iframe || !isYouTubeIframe(iframe)) return;
    try {
      var src = iframe.getAttribute("src") || iframe.src || "";
      if (!src) return;
      // Reload with autoplay (muted = higher success after cross-page navigation)
      var next = withAutoplay(src, true);
      if (next !== src) {
        iframe.setAttribute("src", next);
        iframe.src = next;
      }
      // Also try IFrame API command once loaded
      setTimeout(function () {
        try {
          var win = iframe.contentWindow;
          if (!win || !win.postMessage) return;
          win.postMessage(
            JSON.stringify({ event: "command", func: "playVideo", args: [] }),
            "*"
          );
          win.postMessage(
            JSON.stringify({ event: "command", func: "unMute", args: [] }),
            "*"
          );
        } catch (e) {}
      }, 900);
    } catch (e) {}
  }

  function playRumble(iframe) {
    if (!iframe || !isRumbleIframe(iframe)) return;
    try {
      var src = iframe.getAttribute("src") || iframe.src || "";
      if (!src) return;
      // Rumble embed accepts pub=… and autoplay=2 in some players
      var next = src;
      if (!/[?&#]autoplay=/i.test(next)) {
        if (next.indexOf("#") >= 0) {
          next = next.replace(/#/, "?autoplay=2#");
        } else {
          next += (next.indexOf("?") >= 0 ? "&" : "?") + "autoplay=2";
        }
      }
      if (next !== src) {
        iframe.setAttribute("src", next);
        iframe.src = next;
      }
    } catch (e) {}
  }

  function startMediaIn(root) {
    if (!root || !root.querySelector) return;
    var yt =
      root.querySelector(
        'iframe[src*="youtube.com/embed"], iframe[src*="youtube-nocookie.com/embed"], iframe.youtube-player'
      ) || null;
    if (yt) {
      playYouTube(yt);
      return;
    }
    var rumble =
      root.querySelector('iframe[src*="rumble.com/embed"], .td-rumble-card iframe') ||
      null;
    if (rumble) {
      playRumble(rumble);
      return;
    }
    // X / Twitter: scroll is the main win; try to focus the iframe
    var tw =
      root.querySelector(
        "figure.wp-block-embed-twitter iframe, .wp-block-embed-twitter iframe, .twitter-tweet iframe"
      ) || null;
    if (tw) {
      try {
        tw.setAttribute("tabindex", "-1");
        tw.focus();
      } catch (e) {}
    }
  }

  function run() {
    var hash = cleanHash();
    if (!hash) return;
    // Only act on Truth Desk-style fragments
    if (
      !/^(x-post-\d+|yt-[A-Za-z0-9_-]+|rumble-[A-Za-z0-9_-]+|truth-[a-z0-9-]+)$/i.test(
        hash
      )
    ) {
      return;
    }
    var target = findTarget(hash);
    if (!target) {
      // Jetpack / theme may delay oEmbed; retry briefly
      var tries = 0;
      var t = setInterval(function () {
        tries += 1;
        target = findTarget(hash);
        if (target || tries > 12) {
          clearInterval(t);
          if (target) {
            scrollToEl(target);
            startMediaIn(target);
          }
        }
      }, 400);
      return;
    }
    scrollToEl(target);
    // Wait a tick for lazy iframes / oEmbed
    setTimeout(function () {
      startMediaIn(target);
    }, 350);
    setTimeout(function () {
      startMediaIn(target);
    }, 1400);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
  window.addEventListener("hashchange", function () {
    setTimeout(run, 50);
  });
})();
