/* Check My PC page logic. Everything runs in your browser; nothing is sent anywhere. */
(function () {
  "use strict";
  var E = window.APVCheck, $ = function (id) { return document.getElementById(id); };
  var REL = 'target="_blank" rel="nofollow sponsored noopener"';
  var state = { specs: null, goal: "chat", raw: "" };
  function esc(s) { return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) { return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]; }); }

  /* ---- 1. Quick browser check ---- */
  async function quick() {
    var out = $("quick-out"); out.hidden = false; out.innerHTML = "<p>Checking...</p>";
    var gpu = "", arch = "";
    try {
      if (navigator.gpu) {
        var ad = await navigator.gpu.requestAdapter();
        if (ad) { var info = ad.info || (ad.requestAdapterInfo ? await ad.requestAdapterInfo() : {}); gpu = [info.vendor, info.description].filter(Boolean).join(" ").trim(); arch = info.architecture || ""; }
      }
    } catch (e) {}
    try {
      var c = document.createElement("canvas"), gl = c.getContext("webgl") || c.getContext("experimental-webgl");
      if (gl) { var ext = gl.getExtension("WEBGL_debug_renderer_info"); var r = ext ? gl.getParameter(ext.UNMASKED_RENDERER_WEBGL) : ""; if (r && r.length > gpu.length) gpu = r; }
    } catch (e) {}
    var clean = gpu.replace(/^ANGLE \(/, "").replace(/\)$/, "").replace(/Direct3D.*$|vs_\d.*$|\(0x[0-9A-F]+\)/gi, "").replace(/,\s*$/, "").trim();
    var mem = navigator.deviceMemory || 0, th = navigator.hardwareConcurrency || 0;
    if (document.body.classList.contains("os-mac")) {
      var apple = /Apple/i.test(clean) && !/Intel|AMD|Radeon/i.test(clean);
      var ml = ["<li><b>Chip:</b> " + (clean ? esc(clean) : "Your browser would not say") + "</li>", "<li><b>Processor threads:</b> " + (th || "unknown") + "</li>"];
      var mg = apple ? "This looks like a Mac with an Apple chip. Good news: Apple chips are very good at AI. How big a model you can run depends on your memory, which the browser cannot see." : "Your browser did not confirm an Apple chip. If your Mac is from 2020 or later it probably has one. Older Intel Macs work, but slowly.";
      out.innerHTML = '<p class="kicker">First guess only</p><ul>' + ml.join("") + "</ul><p><b>Rough take:</b> " + esc(mg) + '</p><p class="meta">For an exact answer, do the full check in step 2 with the Mac steps. It takes about a minute.</p>';
      return;
    }
    var s = E.fromBrowser({ gpu: clean, memory: mem, threads: th });
    var g = s.gpus[0];
    var lines = [];
    lines.push("<li><b>Graphics:</b> " + (clean ? esc(clean) + (arch ? " (" + esc(arch) + ")" : "") : "Your browser would not say") + "</li>");
    lines.push("<li><b>Memory (RAM):</b> " + (mem ? (mem >= 8 ? "at least 8GB (browsers never report more than 8, so you may have more)" : "about " + mem + "GB") : "Your browser would not say (Firefox and Safari hide this)") + "</li>");
    lines.push("<li><b>Processor threads:</b> " + (th || "unknown") + "</li>");
    var guess;
    if (g && g.vramGB >= 12) guess = "Your graphics card looks like it has about " + g.vramGB + "GB of memory. That is a great start: 8B to 14B models should run fast.";
    else if (g && g.vramGB >= 6) guess = "Your graphics card looks like it has about " + g.vramGB + "GB of memory. Small and medium models (3B to 8B) should run well.";
    else if (g && g.kind !== "integrated") guess = "You seem to have a separate graphics card" + (g.vramGB ? " with about " + g.vramGB + "GB" : "") + ". Small models will run; how big you can go depends on your memory. Run the full check below.";
    else guess = "It looks like your PC uses built-in graphics. Small models (like llama3.2:3b) usually run fine on the processor. How far you can go depends on how much memory you have, which the browser cannot fully see.";
    out.innerHTML = '<p class="kicker">First guess only</p><ul>' + lines.join("") + "</ul><p><b>Rough take:</b> " + esc(guess) + '</p><p class="meta">Browsers hide a lot on purpose, for your privacy. For an exact answer, do the full check in step 2. It takes about a minute.</p>';
    if (!state.specs || state.specs.source === "browser") {
      state.specs = s;
      state.raw = "Quick browser check: GPU " + (clean || "unknown") + ", memory " + (mem ? (mem >= 8 ? "8+" : mem) + "GB" : "unknown") + ", threads " + (th || "unknown");
      render();
    }
  }

  /* ---- 2. Copy command ---- */
  function copyCmd(mac) {
    var pre = $(mac ? "maccmd" : "pscmd"), txt = pre.textContent.trim(), btn = $(mac ? "copy-mac" : "copy-cmd");
    var done = function () { btn.textContent = mac ? "Copied! Paste it into Terminal, then press Return." : "Copied! Paste it into PowerShell, then hit Enter to continue."; setTimeout(function () { btn.textContent = "Copy command"; }, 6000); };
    if (navigator.clipboard && window.isSecureContext) navigator.clipboard.writeText(txt).then(done, fallback); else fallback();
    function fallback() { var t = document.createElement("textarea"); t.value = txt; t.setAttribute("readonly", ""); t.style.position = "fixed"; t.style.opacity = "0"; document.body.appendChild(t); t.select(); var ok = false; try { ok = document.execCommand("copy"); } catch (e) {} document.body.removeChild(t); if (ok) { done(); return; } var r = document.createRange(); r.selectNodeContents(pre); var sel = getSelection(); sel.removeAllRanges(); sel.addRange(r); try { document.execCommand("copy"); done(); } catch (e) { btn.textContent = mac ? "Press Command+C to copy the highlighted text" : "Press Ctrl+C to copy the highlighted text"; } }
  }

  function analyzePaste() {
    var err = $("paste-err"); err.hidden = true;
    try { state.raw = $("paste").value.trim(); state.specs = E.parseResult(state.raw); setOs(state.specs.mac ? "mac" : "win"); showSpecs(); render(); $("results").scrollIntoView({ behavior: "smooth" }); }
    catch (e) { err.textContent = e.message; err.hidden = false; }
  }
  function analyzeManual() {
    var m = { ram: $("m-ram").value, gpu: $("m-gpu").value, vram: $("m-vram").value, cpu: $("m-cpu").value, type: $("m-type").value, ddr: $("m-ddr").value };
    var err = $("manual-err"); err.hidden = true;
    if (!parseFloat(m.ram)) { err.textContent = "Please enter how much memory (RAM) you have, in GB."; err.hidden = false; return; }
    state.specs = E.fromManual(m); setOs("win");
    state.raw = "Manual entry: RAM " + m.ram + "GB, GPU " + (m.gpu || "none / built-in") + (m.vram ? ", VRAM " + m.vram + "GB" : "") + ", CPU " + (m.cpu || "?") + ", type " + m.type + (m.ddr ? ", memory " + m.ddr : "");
    showSpecs(); render(); $("results").scrollIntoView({ behavior: "smooth" });
  }

  function showSpecs() {
    var s = state.specs, r = s.ram, g = s.gpus;
    var rows = [];
    if (s.mac) {
      rows.push(["Chip", s.cpu + (s.apple ? " (Apple chip)" : " (older Intel Mac)")]);
      rows.push(["Memory", r.totalGB + "GB" + (s.apple ? " (shared with graphics; about " + Math.floor(r.totalGB * 0.72) + "GB can go to AI)" : "")]);
      if (s.gpuCores) rows.push(["Graphics cores", String(s.gpuCores)]);
      if (s.board) rows.push(["Mac model", s.board]);
      if (s.os) rows.push(["System", s.os]);
      if (s.freeGB) rows.push(["Free space", s.freeGB + "GB" + (s.freeGB < 30 ? " (tight: models take 2 to 20GB each)" : "")]);
      $("specs").innerHTML = "<h3>What we found</h3><dl>" + rows.map(function (x) { return "<dt>" + esc(x[0]) + "</dt><dd>" + esc(x[1]) + "</dd>"; }).join("") + "</dl>";
      return;
    }
    if (s.cpu) rows.push(["Processor", s.cpu + (s.cores ? " (" + s.cores + " cores, " + s.threads + " threads)" : "")]);
    rows.push(["Memory (RAM)", r.totalGB + "GB" + (r.ddr ? " " + r.ddr : "") + (r.mhz ? " at " + r.mhz + " MHz" : "") + (r.ff ? ", " + r.ff : "")]);
    if (r.slots) rows.push(["Memory slots", r.sticks + " of " + r.slots + " used" + (r.sizes.length ? " (" + r.sizes.map(function (x) { return x + "GB"; }).join(" + ") + ")" : "") + (r.maxGB ? ", board max about " + r.maxGB + "GB" : "")]);
    rows.push(["Graphics", g.length ? g.map(function (x) { return x.name + (x.kind === "integrated" ? " (built-in, shares your RAM)" : " (" + (x.vramGB || "?") + "GB)"); }).join("; ") : "Built-in / not entered"]);
    rows.push(["Type of computer", s.laptop ? "Laptop" : s.small ? "Mini PC / all-in-one" : "Desktop tower"]);
    if (s.board) rows.push(["Motherboard", s.board]);
    if (s.os) rows.push(["Windows", s.os]);
    if (s.freeGB) rows.push(["Free space on C:", s.freeGB + "GB" + (s.freeGB < 30 ? " (tight: models take 2 to 20GB each)" : "")]);
    $("specs").innerHTML = "<h3>What we found</h3><dl>" + rows.map(function (x) { return "<dt>" + esc(x[0]) + "</dt><dd>" + esc(x[1]) + "</dd>"; }).join("") + "</dl>";
  }

  /* ---- 3/4. Goals + verdict ---- */
  function pickGoal(k) {
    state.goal = k;
    document.querySelectorAll(".goal").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.goal === k ? "true" : "false"); });
    render();
  }
  function link(l) { var url = l.url || E.amz(l.q); return '<a class="btn sm" href="' + esc(url) + '" ' + REL + ">" + esc(l.name) + " on Amazon</a>"; }
  function render() {
    var box = $("verdict");
    if (!state.specs) { box.innerHTML = '<p class="meta">Run the quick check or full check above, then pick a goal, and your answer appears here.</p>'; return; }
    var onMac = document.body.classList.contains("os-mac"), sp = state.specs;
    if (sp.source !== "browser" && !!sp.mac !== onMac) { $("specs").innerHTML = ""; box.innerHTML = '<p class="meta">Your results are from a ' + (sp.mac ? "Mac" : "Windows PC") + '. Pick <strong>' + (sp.mac ? "Mac" : "Windows PC") + '</strong> above to see them, or run the check on this computer.</p>'; return; }
    var r = E.recommend(state.specs, state.goal);
    var cls = { "Ready now": "ok", "Add memory": "mem", "Add a graphics card": "gpu", "Consider a mini PC or new PC": "new", "Consider a Mac with more memory": "new" }[r.verdict] || "ok";
    var h = '<div class="verdict ' + cls + '"><p class="kicker">For: ' + esc(r.goal) + (state.specs.source === "browser" ? " (first guess)" : "") + "</p><h3>" + esc(r.verdict) + "</h3>";
    h += r.why.map(function (w) { return "<p>" + esc(w) + "</p>"; }).join("");
    if (r.models.length) {
      h += '<table class="fit"><thead><tr><th>Model</th><th>Size</th><th>On your PC</th></tr></thead><tbody>';
      h += r.models.map(function (m) { return Array.isArray(m) ? "<tr><td>" + esc(m[0]) + "</td><td colspan=2>" + esc(m[1]) + "</td></tr>" :
        '<tr><td><code>' + esc(m.name) + "</code></td><td>~" + m.size + 'GB</td><td class="' + m.fit.level + '">' + esc(m.fit.label) + "</td></tr>"; }).join("");
      h += "</tbody></table>";
    }
    if (r.actions.length) h += "<h4>What to do</h4><ul>" + r.actions.map(function (a) { return "<li>" + esc(a) + "</li>"; }).join("") + "</ul>";
    if (r.crucial) h += '<p><b>Get the exact right memory:</b> the free <a href="https://www.crucial.com/store/advisor" target="_blank" rel="noopener">Crucial System Scanner / Advisor</a> tells you exactly which sticks fit your PC and how many slots are free. It is the trusted way to be sure before you buy.</p>';
    if (r.links.length) h += '<div class="links">' + r.links.map(link).join("") + "</div>";
    if (r.psu) h += '<p class="meta">Before buying a graphics card, check your power supply. <a href="#psu">How to read the power supply label</a>.</p>';
    if (state.specs.source === "browser") h += '<p class="meta">This is based on what your browser shares. Do the full check for a real answer.</p>';
    box.innerHTML = h + "</div>";
    updateMail();
  }

  /* ---- 5. Ask Blake ---- */
  function updateMail() {
    var a = $("ask-blake"); if (!a) return;
    var body = "Hi Blake,\n\nCould you check my computer for local AI?\nWhat I want to do: " + (E.GOALS[state.goal] || {}).title + "\n\nMy results:\n" + (state.raw || "(I have not run the check yet)") + "\n\nThanks!";
    if (body.length > 1800) body = body.slice(0, 1800) + "...";
    a.href = "mailto:contact@aipickvault.com?subject=" + encodeURIComponent("Check my PC for local AI") + "&body=" + encodeURIComponent(body);
  }

  function setOs(os) {
    document.body.classList.toggle("os-mac", os === "mac");
    document.body.classList.toggle("os-win", os !== "mac");
    document.querySelectorAll(".os-btn").forEach(function (b) { b.setAttribute("aria-pressed", b.dataset.os === os ? "true" : "false"); });
    var sp = state.specs;
    if (sp && sp.source === "browser" && os === "mac") { state.specs = null; $("quick-out").hidden = true; }
    if (state.specs) showSpecs();
    render();
  }

  document.addEventListener("DOMContentLoaded", function () {
    $("quick-btn").addEventListener("click", quick);
    $("copy-cmd").addEventListener("click", function () { copyCmd(false); });
    $("copy-mac").addEventListener("click", function () { copyCmd(true); });
    if (E.isPhone({ userAgent: navigator.userAgent, maxTouchPoints: navigator.maxTouchPoints, width: Math.min(screen.width || 0, window.innerWidth || 9999), coarse: window.matchMedia && matchMedia("(pointer:coarse)").matches })) {
      var pb = $("phonebox"), url = "https://aipickvault.com/check-my-pc/"; pb.hidden = false;
      var sh = $("pb-share");
      sh.addEventListener("click", function () {
        if (navigator.share) navigator.share({ title: "Check my computer for AI", text: "Open this on my PC or Mac:", url: url }).catch(function () {});
        else location.href = $("pb-mail").href;
      });
      $("pb-copy").addEventListener("click", function () {
        var b = $("pb-copy"), ok = function () { b.textContent = "Link copied!"; };
        if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(url).then(ok, function () { prompt("Copy this link:", url); });
        else prompt("Copy this link:", url);
      });
    }
    var isMac = (/Mac/i.test(navigator.platform || "") && !(navigator.maxTouchPoints > 1)) || (/Macintosh|Mac OS X/i.test(navigator.userAgent) && !/iPhone|iPad/i.test(navigator.userAgent) && !(navigator.maxTouchPoints > 1));
    setOs(isMac ? "mac" : "win");
    document.querySelectorAll(".os-btn").forEach(function (b) { b.addEventListener("click", function () { setOs(b.dataset.os); }); });
    $("analyze").addEventListener("click", analyzePaste);
    $("manual-go").addEventListener("click", analyzeManual);
    document.querySelectorAll(".goal").forEach(function (b) { b.addEventListener("click", function () { pickGoal(b.dataset.goal); }); });
    render(); updateMail();
  });
})();
