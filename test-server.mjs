import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {randomBytes} from 'node:crypto';
import {once} from 'node:events';
import {readFile} from 'node:fs/promises';
const password=randomBytes(24).toString('hex'),origin='http://127.0.0.1:19381';
const proc=spawn(process.execPath,['server.mjs'],{cwd:new URL('.',import.meta.url),env:{...process.env,APP_PASSWORD:password,PORT:'19381',NODE_ENV:'test'},stdio:['ignore','pipe','pipe']});
try{await Promise.race([once(proc.stdout,'data'),new Promise((_,r)=>setTimeout(()=>r(Error('server timeout')),5000))]);
let r=await fetch(origin+'/api/bridge');assert.equal(r.status,401);
r=await fetch(origin+'/',{redirect:'manual'});assert.equal(r.status,303);assert.equal(r.headers.get('location'),'/login');
r=await fetch(origin+'/login',{method:'POST',headers:{origin,'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password:'incorrect'})});assert.equal(r.status,401);
r=await fetch(origin+'/login',{method:'POST',headers:{origin,'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password}),redirect:'manual'});assert.equal(r.status,303);const cookie=r.headers.get('set-cookie').split(';')[0];assert.ok(r.headers.get('set-cookie').includes('HttpOnly'));
r=await fetch(origin+'/',{headers:{cookie}});assert.equal(r.status,200);assert.ok((await r.text()).includes('ANALYSE DU BOT'));
r=await fetch(origin+'/api/bridge',{headers:{cookie}});assert.equal((await r.json()).paired,false);
r=await fetch(origin+'/api/bridge',{method:'POST',headers:{cookie,origin:'https://evil.test','content-type':'application/json'},body:JSON.stringify({action:'pair',url:'https://localhost',key:'a'.repeat(43)})});assert.equal(r.status,403);
r=await fetch(origin+'/api/bridge',{method:'POST',headers:{cookie,origin,'content-type':'application/json'},body:JSON.stringify({action:'pair',url:'https://localhost',key:'a'.repeat(43)})});assert.equal(r.status,400);
r=await fetch(origin+'/server.mjs',{headers:{cookie}});assert.equal(r.status,404);
const html=await readFile(new URL('./public/control.html',import.meta.url),'utf8'),js=await readFile(new URL('./public/control.js',import.meta.url),'utf8');const ids=[...js.matchAll(/(?:\$|document.getElementById)\('([^']+)'\)/g)].map(m=>m[1]);for(const id of ids)assert.ok(html.includes('id="'+id+'"'),id+' absent');assert.ok(!html.includes('chatgpt.site'));console.log('PASS: login/session, private routes, CSRF, SSRF, protected files and all dashboard DOM IDs.');
}finally{proc.kill();}
