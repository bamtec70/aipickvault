/**
 * Truth Desk / Wire media controller
 * - Only one HTML5 video plays at a time
 * - Pause when a video is scrolled mostly out of view
 * - For Twitter/X oEmbed iframes: reset src (only way to stop cross-origin players)
 *
 * Load site-wide on wethepeople.news.blog (Custom JS / header-footer plugin):
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

  function isTdVideo(el) {
    if (!el || el.tagName !== "VIDEO") return false;
    // Prefer marked players; still manage WP shortcode videos on desk pages
    if (el.classList.contains("td-media-player")) return true;
    if (el.classList.contains("wp-video-shortcode")) return true;
    if (el.closest && el.closest(".td-media-wrap, .wp-video, #truth-alex, .td-x-card"))
      return true;
    // On pages that opted in via body/root marker
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

  function pauseVideo(v) {
    try {
      if (v && !v.paused) v.pause();
    } catch (e) {}
  }

  function stopTwitterIframe(iframe, except) {
    if (!iframe || iframe === except) return;
    try {
      var src = iframe.getAttribute("src") || iframe.src;
      if (!src) return;
      // Reload embed to halt playback (cross-origin; no pause API)
      iframe.src = src;
    } catch (e) {}
  }

  function pauseOthers(active) {
    allVideos().forEach(function (v) {
      if (v !== active) pauseVideo(v);
    });
    allTwitterIframes().forEach(function (f) {
      stopTwitterIframe(f, null);
    });
  }

  // When any HTML5 video plays, stop siblings + Twitter embeds
  document.addEventListener(
    "play",
    function (e) {
      var t = e.target;
      if (!isTdVideo(t)) return;
      allVideos().forEach(function (v) {
        if (v !== t) pauseVideo(v);
      });
      allTwitterIframes().forEach(function (f) {
        stopTwitterIframe(f, null);
      });
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
      allTwitterIframes().forEach(function (f) {
        if (f !== active) stopTwitterIframe(f, active);
      });
    },
    true
  );

  function observeScroll() {
    if (!("IntersectionObserver" in window)) return;
    var io = new IntersectionObserver(
      function (entries) {
        entries.forEach(function (en) {
          if (en.isIntersecting) return;
          var el = en.target;
          if (el.tagName === "VIDEO") {
            pauseVideo(el);
          } else if (el.tagName === "IFRAME") {
            stopTwitterIframe(el, null);
          } else if (el.querySelector) {
            var v = el.querySelector("video");
            if (v) pauseVideo(v);
            var f = el.querySelector("iframe");
            if (f) stopTwitterIframe(f, null);
          }
        });
      },
      { threshold: 0.2, rootMargin: "0px" }
    );

    function watch() {
      allVideos().forEach(function (v) {
        try {
          io.observe(v);
        } catch (e) {}
      });
      allTwitterIframes().forEach(function (f) {
        try {
          io.observe(f);
        } catch (e) {}
      });
      document
        .querySelectorAll(
          "figure.wp-block-embed-twitter, .wp-video, .td-media-wrap, .td-x-card"
        )
        .forEach(function (box) {
          try {
            io.observe(box);
          } catch (e) {}
        });
    }

    watch();
    // Tweets/oEmbeds hydrate late
    setTimeout(watch, 1500);
    setTimeout(watch, 4000);
    if ("MutationObserver" in window) {
      var mo = new MutationObserver(function () {
        watch();
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
