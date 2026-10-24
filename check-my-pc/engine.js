/* AI Pick Vault "Check My PC" engine. Runs 100% in your browser. Nothing is uploaded. */
(function (root) {
  "use strict";
  var TAG = "wethepeopl0b9-20";
  function amz(q) { return "https://www.amazon.com/s?k=" + encodeURIComponent(q).replace(/%20/g, "+") + "&tag=" + TAG; }

  var DDR = { 20: "DDR", 21: "DDR2", 24: "DDR3", 26: "DDR4", 27: "LPDDR", 28: "LPDDR2", 29: "LPDDR3", 30: "LPDDR4", 34: "DDR5", 35: "LPDDR5" };
  var LAPTOP_CHASSIS = [8, 9, 10, 11, 12, 14, 18, 21, 30, 31, 32];
  var SMALL_CHASSIS = [13, 35, 36]; // all-in-one, mini PC, stick PC

  // Approximate VRAM for common cards (used when only a name is known).
  var VRAM_TABLE = [
    [/RTX\s*5090/i, 32], [/RTX\s*5080/i, 16], [/RTX\s*5070\s*Ti/i, 16], [/RTX\s*5070/i, 12], [/RTX\s*5060\s*Ti/i, 16], [/RTX\s*5060/i, 8],
    [/RTX\s*4090/i, 24], [/RTX\s*4080/i, 16], [/RTX\s*4070\s*Ti\s*Super/i, 16], [/RTX\s*4070/i, 12], [/RTX\s*4060\s*Ti/i, 8], [/RTX\s*4060/i, 8],
    [/RTX\s*3090/i, 24], [/RTX\s*3080\s*Ti/i, 12], [/RTX\s*3080/i, 10], [/RTX\s*3070/i, 8], [/RTX\s*3060\s*Ti/i, 8], [/RTX\s*3060/i, 12], [/RTX\s*3050/i, 8],
    [/RTX\s*2080\s*Ti/i, 11], [/RTX\s*2080/i, 8], [/RTX\s*2070/i, 8], [/RTX\s*2060/i, 6],
    [/GTX\s*1660/i, 6], [/GTX\s*1650/i, 4], [/GTX\s*1080\s*Ti/i, 11], [/GTX\s*1080/i, 8], [/GTX\s*1070/i, 8], [/GTX\s*1060/i, 6], [/GTX\s*1050\s*Ti/i, 4], [/GTX\s*1050/i, 2],
    [/RX\s*7900\s*XTX/i, 24], [/RX\s*7900/i, 20], [/RX\s*7800/i, 16], [/RX\s*7700/i, 12], [/RX\s*7600\s*XT/i, 16], [/RX\s*7600/i, 8],
    [/RX\s*9070/i, 16], [/RX\s*9060\s*XT/i, 16], [/RX\s*6950|RX\s*6900|RX\s*6800/i, 16], [/RX\s*6700/i, 12], [/RX\s*6600/i, 8], [/RX\s*6500/i, 4],
    [/RX\s*5[67]00/i, 8], [/RX\s*5[78]0/i, 8], [/Arc\s*B580/i, 12], [/Arc\s*B570/i, 10], [/Arc\s*A770/i, 16], [/Arc\s*A750/i, 8], [/Arc\s*A380/i, 6]
  ];
  function guessVram(name) { for (var i = 0; i < VRAM_TABLE.length; i++) if (VRAM_TABLE[i][0].test(name || "")) return VRAM_TABLE[i][1]; return 0; }

  function gpuKind(name) {
    var n = name || "";
    if (/microsoft basic|remote display|virtual|parsec|citrix|displaylink|meta virtual/i.test(n)) return "ignore";
    if (/nvidia|geforce|quadro|tesla|\brtx\b|\bgtx\b/i.test(n)) return "nvidia";
    if (/radeon\s*(rx|pro|r9|r7\s*2|vii)|\brx\s*\d{3,4}/i.test(n)) return "amd";
    if (/arc\s*\(?tm?\)?\s*[ab]\d{3}|arc\s*[ab]\d{3}/i.test(n)) return "intelarc";
    return "integrated"; // Intel UHD/Iris/HD, Intel Arc Graphics (no number), AMD Radeon(TM) Graphics, Vega, 780M...
  }

  function num(x) { var v = parseFloat(x); return isFinite(v) ? v : 0; }

  /* ---------- Parse the pasted PowerShell JSON ---------- */
  function parseResult(text) {
    if (/Get-CimInstance/i.test(text || "") || /^\s*\$c=/.test(text || "") || /^\s*\$z1=/.test(text || "")) throw new Error("That is the command, not the results. Go back to the blue PowerShell window and press Enter, wait for Done!, then paste here again.");
    if (/pbcopy|sysctl -n|^\s*z1=/.test(text || "")) throw new Error("That is the command, not the results. Go back to the Terminal window and press Return, wait for Done!, then paste here again.");
    if (!text || !String(text).trim()) throw new Error("The box is empty. Paste your results first.");
    var s = String(text).trim();
    var i = s.indexOf("{"), j = s.lastIndexOf("}");
    if (i < 0 || j < i) throw new Error("That does not look like the results from the command. Try copying the command again.");
    var d;
    try { d = JSON.parse(s.slice(i, j + 1)); } catch (e) { throw new Error("The pasted text got cut off or changed. Run the command again and paste right away."); }
    if (d && d.os === "mac") return fromMac(d);
    if (!d || (!d.ram && !d.cpu && !d.gpu)) throw new Error("That does not look like the results from the command.");
    var arr = function (x) { return x == null ? [] : (Array.isArray(x) ? x : [x]); };
    var sticks = arr(d.ram).filter(function (r) { return num(r.gb) > 0; });
    var totalGB = Math.round(sticks.reduce(function (a, r) { return a + num(r.gb); }, 0));
    var types = sticks.map(function (r) { return num(r.t); }).filter(Boolean);
    var t = types.length ? types[0] : 0;
    var mhz = sticks.length ? Math.max.apply(null, sticks.map(function (r) { return num(r.mhz); })) : 0;
    var ddr = DDR[t] || "";
    if (!ddr && mhz) ddr = mhz >= 4400 ? "DDR5" : mhz >= 2133 ? "DDR4" : mhz >= 800 ? "DDR3" : "";
    var ff = sticks.length ? num(sticks[0].ff) : 0; // 8 = DIMM (desktop), 12 = SO-DIMM (laptop / mini PC)
    var vramReg = arr(d.vram);
    var gpus = arr(d.gpu).map(function (g) {
      var name = String(g.n || "").trim();
      var reg = vramReg.filter(function (r) { return String(r.n || "").trim() === name; })[0];
      var bytes = reg ? num(reg.b) : num(g.b);
      var gb = Math.round(bytes / 1073741824);
      var kind = gpuKind(name);
      var guess = guessVram(name);
      if (kind !== "integrated" && guess && (!reg && gb <= 4 && guess > gb)) gb = guess; // AdapterRAM caps at 4GB
      return { name: name, vramGB: kind === "integrated" ? 0 : gb, kind: kind };
    }).filter(function (g) { return g.kind !== "ignore" && g.name; });
    var chassis = arr(d.chassis).map(num);
    var laptop = !!d.battery || chassis.some(function (c) { return LAPTOP_CHASSIS.indexOf(c) >= 0; });
    var small = !laptop && (chassis.some(function (c) { return SMALL_CHASSIS.indexOf(c) >= 0; }) || ff === 12);
    return {
      source: "powershell",
      cpu: String(d.cpu || "").trim(), cores: num(d.cores), threads: num(d.threads),
      board: String(d.board || "").trim(), os: String(d.os || "").trim(), freeGB: num(d.freegb),
      ram: { totalGB: totalGB, sticks: sticks.length, sizes: sticks.map(function (r) { return Math.round(num(r.gb)); }), mhz: mhz, ddr: ddr,
             lp: /^LP/.test(ddr), ff: ff === 12 ? "SO-DIMM" : ff === 8 ? "DIMM" : "", slots: num(d.slots), maxGB: num(d.maxgb) },
      gpus: gpus, laptop: laptop, small: small, desktop: !laptop && !small
    };
  }

  /* ---------- Mac (Terminal command) ---------- */
  function fromMac(d) {
    var cpu = String(d.cpu || "").trim();
    var apple = String(d.arm) === "1" || /arm64/i.test(d.arch || "") || /^Apple/i.test(cpu);
    var gb = num(d.memgb);
    if (!gb) throw new Error("That does not look like the results from the command.");
    return {
      source: "mac", mac: true, apple: apple, cpu: cpu || (apple ? "Apple chip" : "Intel"), cores: num(d.pcores), threads: num(d.threads),
      board: String(d.model || "").trim(), os: d.macos ? "macOS " + d.macos : "", freeGB: num(d.freegb), gpuCores: num(d.gpucores),
      ram: { totalGB: gb, sticks: 0, sizes: [], mhz: 0, ddr: "", lp: true, ff: "", slots: 0, maxGB: 0 },
      gpus: [], laptop: false, small: false, desktop: false
    };
  }
  var MAC_USABLE = 0.72;
  function macPick(gb) { return gb <= 12 ? "llama3.2:3b" : gb <= 20 ? "qwen3:8b" : gb <= 47 ? "qwen3:14b" : "qwen3:30b"; }
  function macLinks(gb) {
    var want = gb < 16 ? 16 : gb < 24 ? 24 : gb < 32 ? 32 : 64;
    var air = Math.min(32, Math.max(24, want)), pro = Math.max(48, want);
    return [{ name: "Mac mini with " + want + "GB memory", q: "Mac mini M4 " + want + "GB" }, { name: "MacBook Air with " + air + "GB memory", q: "MacBook Air M4 " + air + "GB" }, { name: "MacBook Pro with " + pro + "GB memory", q: "MacBook Pro M4 Pro " + pro + "GB" }];
  }

  /* ---------- Manual entry (msinfo32 route) ---------- */
  function fromManual(m) {
    var name = String(m.gpu || "").trim();
    var kind = name ? gpuKind(name) : "integrated";
    var v = num(m.vram) || (kind === "integrated" ? 0 : guessVram(name));
    var type = m.type || "desktop";
    return {
      source: "manual", cpu: String(m.cpu || "").trim(), cores: 0, threads: 0, board: "", os: "", freeGB: 0,
      ram: { totalGB: num(m.ram), sticks: 0, sizes: [], mhz: 0, ddr: m.ddr || "", lp: m.ddr === "soldered", ff: "", slots: 0, maxGB: 0 },
      gpus: name ? [{ name: name, vramGB: kind === "integrated" ? 0 : v, kind: kind }] : [],
      laptop: type === "laptop", small: type === "mini", desktop: type === "desktop"
    };
  }

  /* ---------- Quick browser check ---------- */
  function fromBrowser(b) {
    var name = b.gpu || "";
    var kind = name ? gpuKind(name) : "integrated";
    return {
      source: "browser", cpu: "", cores: Math.round((b.threads || 0) / 2), threads: b.threads || 0, board: "", os: "", freeGB: 0,
      ram: { totalGB: b.memory || 0, capped: (b.memory || 0) >= 8, sticks: 0, sizes: [], mhz: 0, ddr: "", lp: false, ff: "", slots: 0, maxGB: 0 },
      gpus: name ? [{ name: name, vramGB: kind === "integrated" ? 0 : guessVram(name), kind: kind }] : [],
      laptop: false, small: false, desktop: true, unknownBody: true
    };
  }

  /* ---------- Goals and models (approximate Ollama q4 download sizes) ---------- */
  var GOALS = {
    writing: { title: "Writing letters and email help", models: [["llama3.2:3b", 2.0], ["qwen3:8b", 5.2], ["gemma3:12b", 8.1]], target: 1 },
    docs:    { title: "Reading and summarizing documents", models: [["gemma3:4b", 3.3], ["gemma3:12b", 8.1], ["qwen3:14b", 9.3]], target: 1, ctx: 2 },
    chat:    { title: "Everyday questions and chat", models: [["llama3.2:3b", 2.0], ["qwen3:8b", 5.2], ["qwen3:30b", 19]], target: 1 },
    coding:  { title: "Coding help", models: [["qwen2.5-coder:7b", 4.7], ["qwen3:14b", 9.3], ["qwen3-coder:30b", 19]], target: 1, ctx: 1 },
    reason:  { title: "Thinking through hard problems", models: [["deepseek-r1:8b", 5.2], ["deepseek-r1:14b", 9.0], ["deepseek-r1:32b", 20]], target: 1, ctx: 1 },
    image:   { title: "Making pictures (image generation)", image: true },
    voice:   { title: "Voice: read aloud and dictation", voice: true }
  };
  var OVERHEAD = 1.5, OS_RESERVE = 4;

  function bestGpu(s) { return s.gpus.filter(function (g) { return g.kind !== "integrated"; }).sort(function (a, b) { return b.vramGB - a.vramGB; })[0] || null; }

  function fit(s, size, ctx) {
    var need = size + OVERHEAD + (ctx || 0);
    if (s.mac) {
      if (s.apple) return need <= s.ram.totalGB * MAC_USABLE ? { level: "fast", label: "Fast (your Apple chip uses its memory for AI)", need: need } : { level: "no", label: "Too big for this Mac", need: need };
      return need <= s.ram.totalGB - OS_RESERVE ? { level: "ok", label: "Works, but slow (older Intel Mac)", need: need } : { level: "no", label: "Too big for this Mac", need: need };
    }
    var g = bestGpu(s), v = g ? g.vramGB : 0;
    var freeRam = Math.max(0, s.ram.totalGB - OS_RESERVE);
    if (v && need <= v) return { level: "fast", label: "Fast (fits on your graphics card)", need: need };
    if (need <= freeRam + (v ? v : 0) && (v || need <= freeRam)) return { level: "ok", label: v ? "Works, slower (splits between graphics card and memory)" : "Works, slower (runs on your processor)", need: need };
    return { level: "no", label: "Too big for this PC right now", need: need };
  }

  function canUpgradeRam(s) {
    if (s.ram.lp) return false;
    if (s.source === "browser" || s.laptop || s.small) return null;
    return true;
  }

  function ramLinks(s) {
    var ddr = /DDR5/.test(s.ram.ddr) ? "DDR5" : /DDR4/.test(s.ram.ddr) ? "DDR4" : s.ram.ddr === "DDR3" ? "DDR3" : "";
    var sodimm = s.ram.ff === "SO-DIMM" || s.laptop || s.small;
    var size = s.ram.maxGB && s.ram.maxGB < 32 ? s.ram.maxGB : (s.ram.totalGB >= 32 ? 64 : 32);
    var kit = size === 64 ? "2x32GB" : size === 32 ? "2x16GB" : "";
    var speed = ddr === "DDR5" ? (sodimm ? "5600" : "6000") : ddr === "DDR4" ? "3200" : "";
    var q = [size + "GB", ddr, speed, sodimm ? "SODIMM laptop RAM" : "desktop RAM", kit ? "kit " + kit : ""].filter(Boolean).join(" ");
    return { size: size, ddr: ddr || "your type of", sodimm: sodimm, label: size + "GB " + (ddr || "") + " " + (sodimm ? "SO-DIMM (laptop/mini PC size)" : "desktop DIMM") + " kit", url: amz(q) };
  }

  var GPU_PICKS = [
    { name: "NVIDIA RTX 3060 12GB", q: "RTX 3060 12GB graphics card", vram: 12, psu: 550, note: "Best value. Needs one 8-pin power cable." },
    { name: "NVIDIA RTX 5060 Ti 16GB", q: "RTX 5060 Ti 16GB graphics card", vram: 16, psu: 450, note: "New, more memory, 14B to 20B models fast." },
    { name: "NVIDIA RTX 3050 6GB low profile", q: "RTX 3050 6GB low profile graphics card", vram: 6, psu: 300, note: "For slim office PCs. No extra power cable. Small models only." }
  ];

  function recommend(s, goalKey) {
    var goal = GOALS[goalKey] || GOALS.chat;
    var g = bestGpu(s);
    var v = g ? g.vramGB : 0;
    var nvidia = g && g.kind === "nvidia";
    var old = s.ram.ddr === "DDR3" || s.ram.ddr === "DDR2" || s.ram.ddr === "DDR";
    var ramUp = canUpgradeRam(s);
    var out = { goal: goal.title, verdict: "", why: [], actions: [], models: [], links: [], psu: false, crucial: false };
    var freeSlots = s.ram.slots && s.ram.sticks ? Math.max(0, s.ram.slots - s.ram.sticks) : null;

    if (s.mac) return recommendMac(s, goal, out);
    if (goal.voice) {
      out.verdict = "Ready now";
      out.why.push("Read-aloud and dictation are light. Windows already has them built in (Narrator, Voice Access, and Windows key + H for typing by voice), and free offline tools like Piper (read aloud) and Whisper (dictation) run on almost any PC from the last 8 years.");
      if (s.ram.totalGB && s.ram.totalGB < 8) out.why.push("With under 8GB of memory, stick to the built-in Windows tools.");
      return out;
    }

    if (goal.image) {
      out.models = [["Stable Diffusion 1.5 (via ComfyUI)", "about 4 to 6GB of graphics memory"], ["SDXL (via ComfyUI)", "about 8GB+ of graphics memory"], ["FLUX (via ComfyUI)", "about 12GB+ of graphics memory"]];
      if (nvidia && v >= 8) { out.verdict = "Ready now"; out.why.push("Your " + g.name + " has about " + v + "GB of graphics memory. That is enough for Stable Diffusion and SDXL with ComfyUI" + (v >= 12 ? ", and even FLUX." : ".")); return out; }
      if (g && v >= 8) { out.verdict = "Ready now"; out.why.push("Your " + g.name + " has about " + v + "GB. Picture making works, but most guides and tools assume an NVIDIA card, so expect a bit more setup."); return out; }
      if (s.desktop) {
        out.verdict = "Add a graphics card";
        out.why.push(g ? "Your " + g.name + " has about " + v + "GB of graphics memory. Picture making wants about 8GB or more, ideally on an NVIDIA card." : "Your PC uses built-in graphics. Making pictures really needs a separate graphics card with about 8GB or more.");
        out.actions.push("Add an NVIDIA graphics card with 12GB or more. The RTX 3060 12GB is the usual budget pick.");
        out.links = GPU_PICKS.slice(0, 2); out.psu = true; return out;
      }
      out.verdict = "Consider a mini PC or new PC";
      out.why.push((s.laptop ? "Laptops" : "Small PCs") + " usually cannot take a graphics card. Image generation needs about 8GB+ of graphics memory.");
      out.actions.push("Look at a desktop with an NVIDIA RTX card with 12GB or more, or use a free online image tool for now.");
      out.links = [{ name: "Desktop PC with RTX 4060 or better", q: "desktop PC RTX 4060 Ti 16GB" }];
      return out;
    }

    // Text goals
    out.models = goal.models.map(function (m) { var f = fit(s, m[1], goal.ctx); return { name: m[0], size: m[1], fit: f }; });
    var small = out.models[0], target = out.models[goal.target];
    var targetFits = target.fit.level !== "no", smallFits = small.fit.level !== "no";

    if (target.fit.level === "fast" || (targetFits && !old)) {
      out.verdict = "Ready now";
      out.why.push(target.fit.level === "fast" ? "The recommended model (" + target.name + ") fits on your " + g.name + ", so replies will be quick." : "The recommended model (" + target.name + ") fits in your " + s.ram.totalGB + "GB of memory. It runs on your processor, so expect replies at reading speed or a bit slower.");
      if (target.fit.level !== "fast" && s.desktop) { out.actions.push("Optional speed boost later: a graphics card with 12GB or more makes replies several times faster."); out.links = GPU_PICKS.slice(0, 2); out.psu = true; }
      return out;
    }

    if (old) {
      out.verdict = "Consider a mini PC or new PC";
      out.why.push("Your PC uses DDR3 memory, which means the motherboard and processor are roughly 10 or more years old. DDR3 is slow for AI and is no longer worth buying.");
      if (smallFits) out.why.push("You can still try the small model (" + small.name + ") today for free.");
      if (s.desktop) { out.actions.push("If you would rather keep this PC: a graphics card with 12GB does the heavy lifting no matter how old the rest is, as long as your power supply and case can take it. Older PCs often have small power supplies, so check the label first."); out.links = GPU_PICKS.slice(0, 1); out.psu = true; }
      out.links = out.links.concat([{ name: "Mini PC with 32GB RAM", q: "mini PC 32GB RAM Ryzen" }]);
      return out;
    }

    var needRam = Math.ceil((target.fit.need + OS_RESERVE) / 16) * 16;
    if (needRam < 32) needRam = needRam <= 16 ? 16 : 32;
    if (ramUp !== false && (!s.ram.maxGB || s.ram.maxGB >= needRam)) {
      out.verdict = "Add memory";
      out.why.push("The recommended model (" + target.name + ") needs about " + Math.ceil(target.fit.need) + "GB of free memory. You have " + s.ram.totalGB + "GB, and Windows itself uses about 4GB.");
      var rl = ramLinks(s);
      var slotsTxt = freeSlots === null ? "" : (freeSlots > 0 ? " You have " + freeSlots + " empty slot" + (freeSlots > 1 ? "s" : "") + "." : " All your slots are full, so you would replace your current sticks with one matched kit.");
      out.actions.push("Upgrade to " + rl.size + "GB of " + rl.ddr + " memory (" + (rl.sodimm ? "SO-DIMM, the short laptop size" : "DIMM, the full desktop size") + ")." + slotsTxt + (s.ram.maxGB ? " Your board reports a maximum of about " + s.ram.maxGB + "GB." : ""));
      if (ramUp === null) out.actions.push("Some laptops have memory soldered to the board and cannot be upgraded. The Crucial scanner below will tell you.");
      out.actions.push("Buy one matched kit (2 sticks) rather than adding a single odd stick.");
      out.crucial = true;
      out.links = [{ name: rl.label, url: rl.url }];
      if (s.desktop) { out.actions.push("Or, for much faster replies: add a graphics card with 12GB or more."); out.links = out.links.concat(GPU_PICKS.slice(0, 1)); out.psu = true; }
      return out;
    }

    if (s.desktop) {
      out.verdict = "Add a graphics card";
      out.why.push("Your memory is already near what this motherboard can hold, so a graphics card is the upgrade that unlocks bigger models.");
      out.actions.push("Add an NVIDIA graphics card with 12GB or more (needs a free PCIe x16 slot, which nearly every desktop has).");
      out.links = GPU_PICKS.slice(0, 2); out.psu = true; return out;
    }

    out.verdict = "Consider a mini PC or new PC";
    out.why.push(s.ram.lp ? "Your memory is soldered to the board (LPDDR), so it cannot be upgraded." : "This " + (s.laptop ? "laptop" : "PC") + " cannot take more memory or a graphics card.");
    if (smallFits) out.why.push("Good news: you can still try " + small.name + " today for free. It is fine for short letters and simple questions.");
    out.actions.push("For bigger models, a mini PC with 32GB of upgradeable memory is a quiet, affordable box that sits next to your current PC.");
    out.links = [{ name: "Mini PC with 32GB RAM", q: "mini PC 32GB RAM Ryzen" }];
    return out;
  }

  function recommendMac(s, goal, out) {
    out.psu = false; out.crucial = false; out.mac = true;
    var gb = s.ram.totalGB;
    if (goal.voice) {
      out.verdict = "Ready now";
      out.why.push("Your Mac already reads text aloud and types what you say. Look in System Settings > Accessibility > Spoken Content, and press the microphone key (or Fn twice) to dictate.");
      return out;
    }
    if (goal.image) {
      out.models = [["Draw Things (free Mac app)", "works on Apple chip Macs, best with 16GB or more"]];
      if (s.apple && gb >= 16) { out.verdict = "Ready now"; out.why.push("Your Apple chip Mac with " + gb + "GB can make pictures with the free Draw Things app. Expect about a minute per picture."); return out; }
      out.verdict = "Consider a Mac with more memory";
      out.why.push(s.apple ? "Making pictures works best with 16GB or more. Your Mac has " + gb + "GB, so it will be very slow or may not work." : "This is an older Intel Mac. Making pictures on it is too slow to be useful.");
      out.actions.push("Mac memory cannot be added later. If you buy a Mac for AI, get one with at least 24GB.");
      out.links = macLinks(gb); return out;
    }
    out.models = goal.models.map(function (m) { var f = fit(s, m[1], goal.ctx); return { name: m[0], size: m[1], fit: f }; });
    var target = out.models[goal.target], small = out.models[0];
    var pick = macPick(gb);
    if (!s.apple) {
      var ok = small.fit.level !== "no";
      out.verdict = ok ? "Ready now" : "Consider a Mac with more memory";
      out.why.push("This is an older Intel Mac, so AI runs only on the processor. It will be slow: expect a few words per second.");
      if (ok) out.why.push("Start with " + small.name + ". It is fine for short letters and simple questions.");
      out.actions.push("For fast AI, a newer Mac with an Apple chip (M1 or later) and 16GB or more is a big step up. Mac memory cannot be added later.");
      out.links = macLinks(gb); return out;
    }
    if (target.fit.level !== "no") {
      out.verdict = "Ready now";
      out.why.push("Apple chip Macs share one pool of memory, and about " + Math.floor(gb * MAC_USABLE) + "GB of your " + gb + "GB can go to AI. The recommended model (" + target.name + ") fits and will run fast.");
      out.why.push("Best everyday pick for your Mac: " + pick + ".");
      return out;
    }
    out.verdict = small.fit.level !== "no" ? "Ready now" : "Consider a Mac with more memory";
    out.why.push("Your Mac has " + gb + "GB. About " + Math.floor(gb * MAC_USABLE) + "GB can go to AI, which is enough for " + small.name + " but not the bigger recommended model (" + target.name + ").");
    out.why.push("Best everyday pick for your Mac: " + pick + ".");
    out.actions.push("Mac memory cannot be upgraded. If you want bigger, smarter models, the answer is a Mac with more memory: 24GB or more.");
    out.links = macLinks(gb);
    return out;
  }

  /* ---------- Phone / tablet detection ---------- */
  function isPhone(nav) {
    nav = nav || {};
    var ua = nav.userAgent || "", w = nav.width || 0, touch = nav.maxTouchPoints || 0;
    if (/iPhone|iPod|iPad|Android|Mobile|Silk|Kindle|webOS|BlackBerry|Opera Mini|IEMobile/i.test(ua)) return true;
    if (/Macintosh/i.test(ua) && touch > 1) return true; // iPadOS reports as a Mac
    return touch > 0 && w > 0 && w < 820 && !!nav.coarse;
  }

  var API = { parseResult: parseResult, fromManual: fromManual, fromBrowser: fromBrowser, recommend: recommend, isPhone: isPhone, fromMac: fromMac, macLinks: macLinks, fit: fit, GOALS: GOALS, GPU_PICKS: GPU_PICKS, amz: amz, guessVram: guessVram, gpuKind: gpuKind };
  if (typeof module !== "undefined" && module.exports) module.exports = API; else root.APVCheck = API;
})(this);
