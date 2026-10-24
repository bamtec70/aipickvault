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
