// Run with jsdom installed as a development dependency; no network or MT5 access.
const assert=require('node:assert/strict');
const fs=require('node:fs');
const {JSDOM}=require('jsdom');
const {randomUUID}=require('node:crypto');
const html=fs.readFileSync(__dirname+'/public/control.html','utf8');
const js=fs.readFileSync(__dirname+'/public/control.js','utf8');
const defaults={risk:.005,daily_loss:.02,positions:3,cooldown:60,pivot:2,penetration:.1,stop_distance:1,max_spread:.5,break_even:true,be_trigger:.5,use_sessions:true,start1:0,end1:5,start2:13,end2:17};
let saved={...defaults};const calls=[];
function snapshot(){return {connected:true,paired:true,running:false,halted:false,connector_version:'4.0',symbol:'XAUUSD',risk:saved.risk,daily_loss:saved.daily_loss,rr:2,supervision:'browser',strategy_settings:saved,strategy_settings_defaults:defaults,account:{demo:true,login:'test-only',server:'Demo',balance:10000,equity:10000,profit:0,free_margin:10000},positions:[],events:[],equity_curve:[],history:{status:'unavailable'},time:Date.now()/1000};}
const settle=()=>new Promise(resolve=>setTimeout(resolve,20));
function page(){
 const dom=new JSDOM(html,{url:'https://bot.example/',runScripts:'outside-only'});const w=dom.window;
 w.crypto.randomUUID=randomUUID;
 w.fetch=async(url,options={})=>{
  if(options.method==='POST'){const body=JSON.parse(options.body);calls.push(body);assert.equal(body.action,'settings');saved={...body.config};}
  return {ok:true,status:200,json:async()=>snapshot()};
 };
 w.eval(js+'\nwindow.testRender=render;window.testState=()=>state;');return dom;
}
(async()=>{
 let dom=page(),w=dom.window;await settle();const $=id=>w.document.getElementById(id);
 w.document.querySelector('.bottom-nav a[href="#strategy-settings"]').click();
 assert.equal($('strategy-settings').hidden,false);assert.equal(w.document.querySelector('.screen-grid').hidden,true);
 $('setting-risk').value='0.4';$('setting-positions').value='2';
 w.testRender(w.testState());assert.equal($('setting-risk').value,'0.4'); // Polling preserves an unsaved draft.
 $('strategy-settings-form').dispatchEvent(new w.Event('submit',{cancelable:true}));await settle();
 assert.equal(calls.length,1);assert.equal(calls[0].config.risk,.004);assert.equal(calls[0].config.positions,2);
 assert.match($('settings-status').textContent,/enregistrés/);
 $('reset-settings').click();assert.equal($('setting-risk').value,'0.5');assert.equal(calls.length,1);
 w.testRender({...w.testState(),running:true});assert.equal($('settings-fields').disabled,true);
 dom.window.close();dom=page();w=dom.window;await settle();assert.equal(w.document.getElementById('setting-risk').value,'0.4');
 w.sample={...snapshot(),account:{...snapshot().account,login:'another-account'},strategy_settings:{...defaults}};
 w.testRender(w.sample);assert.equal(w.document.getElementById('setting-risk').value,'0.5');
 dom.window.close();console.log('PASS: settings navigation, draft preservation, save request, defaults without auto-save, running lock, reload and account switch.');
})().catch(e=>{console.error(e);process.exit(1);});
