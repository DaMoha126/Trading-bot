import vm from 'node:vm';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const html=await readFile(new URL('./public/control.html',import.meta.url),'utf8'),js=await readFile(new URL('./public/control.js',import.meta.url),'utf8');
const items=new Map([...html.matchAll(/id="([^"]+)"/g)].map(m=>[m[1],{value:m[1]==='history-side'?'all':'',textContent:'',innerHTML:'',disabled:false,checked:false,hidden:false,className:'',classList:{toggle(){}},getBoundingClientRect:()=>({width:300,height:180}),getContext:()=>new Proxy({},{get:()=>()=>{}}),scrollIntoView(){},click(){this.onclick?.();}}]));
const scope=vm.createContext({document:{getElementById:id=>items.get(id),createElement:()=>({click(){}})},window:{addEventListener(){}},location:{href:'',protocol:'https:'},fetch:async()=>({ok:true,status:200,json:async()=>({paired:false,connected:false,running:false})}),setInterval(){},setTimeout,URL,URLSearchParams,Blob,crypto:globalThis.crypto,devicePixelRatio:1,Date,console});
vm.runInContext(js,scope);await new Promise(r=>setImmediate(r));
function render(data){scope.data=data;vm.runInContext('render(data)',scope);}
const account={demo:true,login:'123',server:'Demo',balance:10000,equity:10001,profit:1,free_margin:9000};
render({paired:true,connected:true,running:true,account,connector_version:'4.0',supervision:'autonomous',symbol:'EURUSD',risk:.005,daily_loss:.01,rr:2,events:[],positions:[]});assert.ok(items.get('bot-description').textContent.includes('autonome'));assert.equal(items.get('autonomous').checked,true);assert.equal(items.get('start').disabled,true);
render({paired:true,connected:false,running:null});assert.equal(items.get('bot-state').textContent,'ÉTAT INCONNU');assert.equal(items.get('stop').disabled,false);assert.equal(items.get('start').disabled,true);
render({paired:true,connected:true,running:false,account,events:[],positions:[],connector_version:'4.0',history:{status:'ok',trades:[{id:'x',symbol:'EURUSD',side:'BUY',volume:.1,entry:1.1,exit:1.102,closed:Math.floor(Date.now()/1000),commission:-.7,fee:0,swap:-1,net:18.3,reason:'TP',exit_deals:1}],excluded_mixed:0,excluded_incomplete:0}});assert.ok(items.get('history-net').textContent.includes('18,30'));assert.equal(items.get('export-trades').disabled,false);assert.ok(items.get('closed-trades').innerHTML.includes('BUY'));
render({paired:true,connected:true,running:false,account:{...account,login:'gold'},symbol:'XAUUSD',instrument:'XAUUSD',price_digits:2,quote:{bid:2700.12,ask:2700.42,time:Date.now()/1000},positions:[],events:[]});
assert.equal(items.get('quote-symbol').textContent,'XAUUSD');assert.equal(items.get('symbol').value,'XAUUSD');assert.equal(items.get('bid').textContent,'2700.12');
assert.ok(html.includes('id="dashboard"'));console.log('PASS: dashboard renders gold symbol and precision, autonomous mode, unknown remote state, closed trade net and exports.');
