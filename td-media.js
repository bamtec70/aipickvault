/**
 * Truth Desk / Wire media controller
 * - Only one HTML5 video plays at a time
 * - Pause HTML5 / YouTube when scrolled mostly out of view
 * - For Twitter/X oEmbed iframes: reset src (only way to stop cross-origin players)
 * - Never reload YouTube embeds via src= (that was breaking Glenn Blaze clips)
 *
 * Load site-wide on wethepeoplepress.com (Custom JS / header-footer plugin):
 *   <script src="https://aipickvault.com/td-media.js" defer></script>
 */
(function () {
  "use strict";
  if (window.__tdMediaController) return;
  window.__tdMediaController = true;

  var VIDEO_SEL =
    "video.td-media-player, video.wp-video-shortcode, .wp-video video, video";
  var TWITTER_SEL =
    "figure.wp-block-embed-twitter iframe, " +
    "figure.wp-block-embed.is-provider-twitter iframe, " +
    ".wp-block-embed-twitter iframe";
  var YOUTUBE_SEL =
    'iframe[src*="youtube.com/embed"], iframe[src*="youtube-nocookie.com/embed"], ' +
    "figure.wp-block-embed-youtube iframe, " +
    "figure.wp-block-embed.is-provider-youtube iframe, " +
    "iframe.td-youtube-player";

  function isTdVideo(el) {
    if (!el || el.tagName !== "VIDEO") return false;
    if (el.classList.contains("td-media-player")) return true;
    if (el.classList.contains("wp-video-shortcode")) return true;
    if (el.closest && el.closest(".td-media-wrap, .wp-video, #truth-alex, .td-x-card"))
      return true;
    if (document.querySelector("[data-td-media-root]")) return true;
    return false;
  }

  function allVideos() {
    return Array.prototype.slice
      .call(document.querySelectorAll(VIDEO_SEL))
      .filter(isTdVideo);
  }

  function allTwitterIframes() {
    return Array.prototype.slice.call(document.querySelectorAll(TWITTER_SEL));
  }

  function isYouTubeIframe(iframe) {
    if (!iframe || iframe.tagName !== "IFRAME") return false;
    var src = iframe.getAttribute("src") || iframe.src || "";
    return /youtube(?:-nocookie)?\.com\/embed\//i.test(src);
  }

  function allYouTubeIframes() {
    return Array.prototype.slice
      .call(document.querySelectorAll(YOUTUBE_SEL))
      .filter(isYouTubeIframe);
  }

  function pauseVideo(v) {
    try {
      if (v && !v.paused) v.pause();
    } catch (e) {}
  }

  function stopTwitterIframe(iframe, except) {
    if (!iframe || iframe === except) return;
    // Never treat YouTube as a tweet player
    if (isYouTubeIframe(iframe)) return;
    try {
      var src = iframe.getAttribute("src") || iframe.src;
      if (!src) return;
      if (/youtube(?:-nocookie)?\.com/i.test(src)) return;
      // Reload embed to halt playback (cross-origin; no pause API)
      iframe.src = src;
    } catch (e) {}
  }

  function ensureYouTubeApi(iframe) {
    if (!iframe || !isYouTubeIframe(iframe)) return;
    try {
      var src = iframe.getAttribute("src") || iframe.src || "";
      if (!src || /[?&]enablejsapi=1\b/i.test(src)) return;
      var join = src.indexOf("?") >= 0 ? "&" : "?";
      var next = src + join + "enablejsapi=1";
      try {
        var origin = encodeURIComponent(location.origin || "");
        if (origin && src.indexOf("origin=") < 0) {
          next += "&origin=" + origin;
        }
      } catch (e2) {}
      iframe.setAttribute("src", next);
    } catch (e) {}
  }

  function pauseYouTubeIframe(iframe) {
    if (!iframe || !isYouTubeIframe(iframe)) return;
    try {
      ensureYouTubeApi(iframe);
      var win = iframe.contentWindow;
      if (!win || !win.postMessage) return;
      // IFrame Player API pause (works when enablejsapi=1)
      win.postMessage(
        JSON.stringify({ event: "command", func: "pauseVideo", args: [] }),
        "*"
      );
      win.postMessage(
        '{"event":"command","func":"pauseVideo","args":""}',
        "*"
      );
    } catch (e) {}
  }

  function pauseAllYouTube(except) {
    allYouTubeIframes().forEach(function (f) {
      if (f !== except) pauseYouTubeIframe(f);
    });
  }

  function pauseOthers(activeVideo) {
    allVideos().forEach(function (v) {
      if (v !== activeVideo) pauseVideo(v);
    });
    allTwitterIframes().forEach(function (f) {
      stopTwitterIframe(f, null);
    });
    pauseAllYouTube(null);
  }

  // When any HTML5 video plays, stop siblings + Twitter + YouTube
  document.addEventListener(
    "play",
    function (e) {
      var t = e.target;
      if (!isTdVideo(t)) return;
      pauseOthers(t);
    },
    true
  );

  // Clicking a Twitter/X embed: stop HTML5 videos and other tweet iframes
  document.addEventListener(
    "click",
    function (e) {
      var node = e.target;
      if (!node || !node.closest) return;
      var wrap = node.closest(
        "figure.wp-block-embed-twitter, figure.wp-block-embed.is-provider-twitter, .wp-block-embed-twitter"
      );
      if (!wrap) return;
      var active = wrap.querySelector("iframe");
      allVideos().forEach(pauseVideo);
      pauseAllYouTube(null);
      allTwitterIframes().forEach(function (f) {
        if (f !== active) stopTwitterIframe(f, active);
      });
    },
    true
  );

  // Clicking near a YouTube card: pause other media (can't detect YT play cross-origin easily)
  document.addEventListener(
    "pointerdown",
    function (e) {
      var node = e.target;
      if (!node || !node.closest) return;
      var ytWrap = node.closest(
        ".td-youtube-wrap, figure.wp-block-embed-youtube, figure.wp-block-embed.is-provider-youtube"
      );
      if (!ytWrap) return;
      allVideos().forEach(pauseVideo);
      allTwitterIframes().forEach(function (f) {
        stopTwitterIframe(f, null);
      });
      var active = ytWrap.querySelector("iframe");
      pauseAllYouTube(active);
    },
    true
  );

  function observeScroll() {
    if (!("IntersectionObserver" in window)) return;
    var seen = typeof WeakSet !== "undefined" ? new WeakSet() : null;

    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) return;
          var el = en.target;
          if (el.tagName === "VIDEO") {
            pauseVideo(el);
            return;
          }
          if (el.tagName === "IFRAME") {
            if (isYouTubeIframe(el)) {
              pauseYouTubeIframe(el);
            } else {
              stopTwitterIframe(el, null);
            }
            return;
          }
          if (!el.querySelector) return;
          var v = el.querySelector("video");
          if (v) pauseVideo(v);
          // Only stop Twitter iframes inside the box — never hard-reload YouTube
          var tw = el.querySelector(
            "figure.wp-block-embed-twitter iframe, .wp-block-embed-twitter iframe"
          );
          if (tw) stopTwitterIframe(tw, null);
          var yts = el.querySelectorAll(
            'iframe[src*="youtube.com/embed"], iframe[src*="youtube-nocookie.com/embed"], iframe.td-youtube-player'
          );
          Array.prototype.forEach.call(yts, pauseYouTubeIframe);
        });
      },
      { threshold: 0.2, rootMargin: "0px" }
    );

    function observeEl(el) {
      if (!el) return;
      if (seen) {
        if (seen.has(el)) return;
        seen.add(el);
      }
      try {
        io.observe(el);
      } catch (e) {}
    }

    function watch() {
      allVideos().forEach(observeEl);
      allTwitterIframes().forEach(observeEl);
      allYouTubeIframes().forEach(function (f) {
        ensureYouTubeApi(f);
        observeEl(f);
      });
      // Observe tweet figures and HTML5 wrappers only (not whole .td-x-card —
      // that was resetting every YouTube iframe on partial scroll-out).
      document
        .querySelectorAll(
          "figure.wp-block-embed-twitter, figure.wp-block-embed.is-provider-twitter, .wp-video"
        )
        .forEach(observeEl);
    }

    watch();
    setTimeout(watch, 1500);
    setTimeout(watch, 4000);
    if ("MutationObserver" in window) {
      var moTimer = null;
      var mo = new MutationObserver(function () {
        if (moTimer) clearTimeout(moTimer);
        moTimer = setTimeout(watch, 200);
      });
      mo.observe(document.documentElement, { childList: true, subtree: true });
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observeScroll);
  } else {
    observeScroll();
  }
})();
