// node tests/check_my_pc_engine.test.js
const E = require("../check-my-pc/engine.js"); const assert = require("assert");
const S = {
 gtx1650: '{"apv":1,"cpu":"Intel(R) Core(TM) i5-10400 CPU @ 2.90GHz","cores":6,"threads":12,"board":"ASUSTeK PRIME B460M-A","ram":[{"gb":8.0,"t":26,"ff":8,"mhz":2666},{"gb":8.0,"t":26,"ff":8,"mhz":2666}],"slots":4.0,"maxgb":128.0,"gpu":[{"n":"NVIDIA GeForce GTX 1650","b":4293918720}],"vram":[{"n":"NVIDIA GeForce GTX 1650","b":4294967296}],"chassis":[3],"battery":false,"os":"Microsoft Windows 11 Home","freegb":250.0}',
 laptop8: 'Done!\n{"apv":1,"cpu":"Intel(R) Core(TM) i3-1115G4","cores":2,"threads":4,"board":"HP 8A3C","ram":[{"gb":8,"t":35,"ff":0,"mhz":4267}],"slots":1,"maxgb":8,"gpu":[{"n":"Intel(R) UHD Graphics","b":1073741824}],"vram":[],"chassis":[10],"battery":true,"os":"Microsoft Windows 11 Home","freegb":60}',
 rtx3060: '{"apv":1,"cpu":"AMD Ryzen 5 5600X 6-Core Processor","cores":6,"threads":12,"board":"Micro-Star B550","ram":[{"gb":16,"t":26,"ff":8,"mhz":3200},{"gb":16,"t":26,"ff":8,"mhz":3200}],"slots":4,"maxgb":128,"gpu":[{"n":"NVIDIA GeForce RTX 3060","b":4293918720}],"vram":[{"n":"NVIDIA GeForce RTX 3060","b":12884901888}],"chassis":[3],"battery":false,"os":"Microsoft Windows 10 Pro","freegb":400}',
 ddr3: '{"apv":1,"cpu":"Intel(R) Core(TM) i5-3470 CPU @ 3.20GHz","cores":4,"threads":4,"board":"Dell Inc. 0MN1TX","ram":[{"gb":4,"t":24,"ff":8,"mhz":1600},{"gb":4,"t":24,"ff":8,"mhz":1600}],"slots":4,"maxgb":32,"gpu":[{"n":"Intel(R) HD Graphics 2500","b":2147483648}],"vram":[],"chassis":[6],"battery":false,"os":"Microsoft Windows 10 Pro","freegb":80}'
};
let pass = 0; const t = (name, fn) => { fn(); pass++; console.log("PASS", name); };
const P = Object.fromEntries(Object.entries(S).map(([k, v]) => [k, E.parseResult(v)]));
t("1650 parse", () => { const s = P.gtx1650; assert.equal(s.ram.totalGB, 16); assert.equal(s.ram.ddr, "DDR4"); assert.equal(s.ram.slots, 4); assert.equal(s.gpus[0].vramGB, 4); assert.equal(s.gpus[0].kind, "nvidia"); assert.ok(s.desktop); });
t("1650 chat ready", () => assert.equal(E.recommend(P.gtx1650, "chat").verdict, "Ready now"));
t("1650 image -> add GPU", () => { const r = E.recommend(P.gtx1650, "image"); assert.equal(r.verdict, "Add a graphics card"); assert.ok(r.psu); });
t("1650 coding big -> ready (fits RAM+VRAM)", () => assert.equal(E.recommend(P.gtx1650, "coding").verdict, "Ready now"));
t("laptop parse", () => { const s = P.laptop8; assert.ok(s.laptop); assert.equal(s.ram.ddr, "LPDDR5"); assert.ok(s.ram.lp); assert.equal(s.gpus[0].kind, "integrated"); assert.equal(s.gpus[0].vramGB, 0); });
t("laptop chat -> mini PC", () => { const r = E.recommend(P.laptop8, "chat"); assert.equal(r.verdict, "Consider a mini PC or new PC"); assert.ok(/soldered/.test(r.why[0])); });
t("laptop voice ready", () => assert.equal(E.recommend(P.laptop8, "voice").verdict, "Ready now"));
t("3060 parse 12GB from registry", () => assert.equal(P.rtx3060.gpus[0].vramGB, 12));
t("3060 coding fast", () => { const r = E.recommend(P.rtx3060, "coding"); assert.equal(r.verdict, "Ready now"); assert.equal(r.models[1].fit.level, "fast"); });
t("3060 image ready", () => assert.equal(E.recommend(P.rtx3060, "image").verdict, "Ready now"));
t("3060 30b works slower", () => assert.equal(E.recommend(P.rtx3060, "chat").models[2].fit.level, "ok"));
t("ddr3 parse", () => { assert.equal(P.ddr3.ram.ddr, "DDR3"); assert.equal(P.ddr3.ram.totalGB, 8); });
t("ddr3 chat -> new PC", () => { const r = E.recommend(P.ddr3, "chat"); assert.equal(r.verdict, "Consider a mini PC or new PC"); assert.ok(r.psu); });
t("16GB no GPU desktop docs -> ready slower or add mem", () => { const s = E.fromManual({ ram: 8, gpu: "", type: "desktop", ddr: "DDR4" }); assert.equal(E.recommend(s, "chat").verdict, "Add memory"); });
t("manual gpu name guess", () => { const s = E.fromManual({ ram: 16, gpu: "NVIDIA GeForce RTX 3060", type: "desktop" }); assert.equal(s.gpus[0].vramGB, 12); });
t("bad input", () => assert.throws(() => E.parseResult("hello"), /does not look/));
t("truncated input", () => assert.throws(() => E.parseResult('{"apv":1,"cpu":"x"'), /does not look|cut off/));
t("links tagged", () => { const r = E.recommend(P.gtx1650, "image"); r.links.forEach(l => assert.ok(E.amz(l.q).includes("tag=wethepeopl0b9-20"))); });
t("browser quick", () => { const s = E.fromBrowser({ gpu: "ANGLE (NVIDIA, NVIDIA GeForce RTX 3060 Direct3D11)", memory: 8, threads: 12 }); assert.equal(s.gpus[0].vramGB, 12); assert.ok(s.ram.capped); });
for (const k of Object.keys(P)) for (const g of Object.keys(E.GOALS)) { const r = E.recommend(P[k], g); assert.ok(r.verdict); console.log("  ", k.padEnd(8), g.padEnd(7), "=>", r.verdict); }
console.log(pass + " tests passed");
