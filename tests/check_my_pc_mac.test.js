var E=require(__dirname+'/../check-my-pc/engine.js'),fs=require('fs'),n=0;
function ok(c,m){if(!c)throw new Error('FAIL '+m);n++;console.log('ok - '+m)}
function mac(gb,arm,cpu){return JSON.stringify({apv:1,os:"mac",cpu:cpu||(arm?"Apple M2":"Intel(R) Core(TM) i5-8210Y CPU @ 1.60GHz"),arch:arm?"arm64":"x86_64",arm:arm?"1":"",model:"Mac14,2",memgb:gb,pcores:"4",threads:"8",gpucores:"10",macos:"15.1",freegb:"212"})}
var m8=E.parseResult(mac(8,1)),m16=E.parseResult(mac(16,1)),m32=E.parseResult(mac(32,1)),mi=E.parseResult(mac(16,0));
ok(m8.mac&&m8.apple&&m8.ram.totalGB===8,'mac 8 parsed');
var r=E.recommend(m8,'chat');ok(r.verdict==='Ready now'&&/llama3.2:3b/.test(r.why.join(' ')),'mac 8 chat ready w/ 3b; '+r.verdict);
r=E.recommend(m8,'coding');ok(r.verdict!=='Add memory'&&r.links.every(function(l){return /Mac/.test(l.name)}),'mac 8 coding -> '+r.verdict);
r=E.recommend(m8,'image');ok(r.verdict==='Consider a Mac with more memory','mac 8 image needs more');
r=E.recommend(m16,'chat');ok(r.verdict==='Ready now'&&r.models[1].fit.level==='fast'&&/qwen3:8b/.test(r.why.join(' ')),'mac 16 chat qwen3:8b fast');
r=E.recommend(m16,'image');ok(r.verdict==='Ready now','mac 16 image ready');
r=E.recommend(m32,'reason');ok(r.verdict==='Ready now'&&/qwen3:14b/.test(r.why.join(' ')),'mac 32 ready, pick 14b');
ok(E.recommend(m32,'chat').models[2].fit.level==='fast','mac 32 runs qwen3:30b fast (23 GB usable)');
ok(mi.mac&&!mi.apple,'intel mac parsed');
r=E.recommend(mi,'chat');ok(/Intel Mac/.test(r.why.join(' '))&&/slow/i.test(r.models[1].fit.label),'intel mac says slow');
ok(/tag=wethepeopl0b9-20/.test(E.amz(r.links[0].q)),'mac links tagged');
var cmd=fs.readFileSync(__dirname+'/../scripts/check_my_pc_cmd_mac.sh','utf8'),msg='';try{E.parseResult(cmd)}catch(e){msg=e.message}ok(/Terminal window/.test(msg),'pasted mac command detected');
console.log(n+' mac tests passed');

// --- Mac results must never contain PC-only advice ---
var PCWORDS = /graphics card|power supply|RAM stick|memory stick|slot|motherboard|msinfo|Windows|Crucial|RTX|GPU/i;
[8, 16, 24, 32, 64].forEach(function (gb) { [1, 0].forEach(function (arm) {
  var sp = E.parseResult(mac(gb, arm));
  Object.keys(E.GOALS).forEach(function (g) {
    var r = E.recommend(sp, g), txt = [r.verdict].concat(r.why, r.actions, r.links.map(function (l) { return l.name + " " + l.q; })).join(" ");
    ok(!r.psu && !r.crucial && !PCWORDS.test(txt) && r.links.every(function (l) { return /^Mac/.test(l.name); }), 'mac ' + gb + 'GB ' + (arm ? 'arm' : 'intel') + ' ' + g + ': no PC advice');
  });
}); });
ok(E.macLinks(16).some(function (l) { return /MacBook Pro/.test(l.name); }), 'mac links include MacBook Pro');
// --- static page: PC-only content is wrapped for Windows, Mac block exists ---
var html = fs.readFileSync(__dirname + '/../check-my-pc/index.html', 'utf8');
ok(/<section class="step only-win" id="psu">/.test(html), 'power supply section is Windows-only');
ok(/<section class="step only-mac" id="macbuy">/.test(html) && /Which Mac for AI/.test(html), 'Which Mac for AI section present');
ok(/<div class="sticky only-win">/.test(html) && /<div class="sticky only-mac">/.test(html), 'sticky bars split by OS');
ok(/<div data-os="win"><details class="alt" id="manual">/.test(html), 'msinfo32 is Windows-only');
var macLinks = html.match(/<section class="step only-mac" id="macbuy">[\s\S]*?<\/section>/)[0].match(/<a [^>]*amazon[^>]*>/g);
ok(macLinks.length === 3 && macLinks.every(function (a) { return /tag=wethepeopl0b9-20/.test(a) && /rel="nofollow sponsored noopener"/.test(a); }), 'Mac Amazon links tagged + rel');
ok(!/\$\d/.test(html.match(/id="macbuy"[\s\S]*?<\/section>/)[0]), 'no static prices in Mac section');
console.log(n + ' mac tests passed (total)');

// --- phone / tablet detection ---
var IPH="Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Mobile/15E148 Safari/604.1",
    AND="Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 Chrome/130.0 Mobile Safari/537.36",
    ANDTAB="Mozilla/5.0 (Linux; Android 14; SM-X710) AppleWebKit/537.36 Chrome/130.0 Safari/537.36",
    IPADOS="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 Version/18.0 Safari/605.1.15",
    WIN="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36";
ok(E.isPhone({userAgent:IPH}),'iPhone is phone');
ok(E.isPhone({userAgent:AND}),'Android phone is phone');
ok(E.isPhone({userAgent:ANDTAB}),'Android tablet is phone/tablet');
ok(E.isPhone({userAgent:IPADOS,maxTouchPoints:5}),'iPadOS (Mac UA + touch) is tablet');
ok(!E.isPhone({userAgent:IPADOS,maxTouchPoints:0,width:1440}),'real Mac is not phone');
ok(!E.isPhone({userAgent:WIN,maxTouchPoints:0,width:390}),'narrow desktop window is not phone');
ok(!E.isPhone({userAgent:WIN,maxTouchPoints:10,width:1920,coarse:false}),'touchscreen laptop is not phone');
ok(E.isPhone({userAgent:"Mozilla/5.0 (X11; Linux x86_64)",maxTouchPoints:5,width:400,coarse:true}),'narrow touch device is phone');
console.log(n + ' tests passed (with phone)');
