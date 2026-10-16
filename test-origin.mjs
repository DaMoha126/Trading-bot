import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {once} from 'node:events';
import {randomBytes} from 'node:crypto';
import {siteOrigin} from './lib/site-origin.mjs';
const external='https://ben-bot-mt5.onrender.com',local='http://127.0.0.1:19382';
const req={headers:{host:'internal.render.local:10000','x-forwarded-host':'evil.example','x-forwarded-proto':'http'},socket:{}};
assert.equal(siteOrigin(req,{RENDER_EXTERNAL_URL:external,NODE_ENV:'development'}),external);
assert.equal(siteOrigin(req,{PUBLIC_URL:'https://custom.example/',RENDER_EXTERNAL_URL:external}),'https://custom.example');
assert.equal(siteOrigin({headers:{host:'localhost:3000'},socket:{}},{}),'http://localhost:3000');
const password=randomBytes(24).toString('hex');
const proc=spawn(process.execPath,['server.mjs'],{cwd:new URL('.',import.meta.url),env:{...process.env,APP_PASSWORD:password,PORT:'19382',NODE_ENV:'development',RENDER_EXTERNAL_URL:external,PUBLIC_URL:''},stdio:['ignore','pipe','pipe']});
let timeout;
try{
 await Promise.race([once(proc.stdout,'data'),new Promise((_,r)=>{timeout=setTimeout(()=>r(Error('server startup timeout')),5000);})]);clearTimeout(timeout);
 const page=await fetch(local+'/login');assert.equal(page.headers.get('referrer-policy'),'same-origin');
 const login=(origin,pw=password)=>fetch(local+'/login',{method:'POST',headers:{...(origin?{origin}:{}),'content-type':'application/x-www-form-urlencoded'},body:new URLSearchParams({password:pw}),redirect:'manual'});
 assert.equal((await login('https://evil.example')).status,403);
 assert.equal((await login(null)).status,403);
 assert.equal((await login('null')).status,403);
 assert.equal((await login(external,'incorrect')).status,401);
 const good=await login(external);assert.equal(good.status,303);const header=good.headers.get('set-cookie');assert.ok(header.includes('; Secure'));assert.ok(header.includes('HttpOnly'));const cookie=header.split(';')[0];
 const dashboard=await fetch(local+'/',{headers:{cookie}});assert.equal(dashboard.status,200);assert.ok((await dashboard.text()).includes('Trading Bot'));
 const api=await fetch(local+'/api/bridge',{method:'POST',headers:{origin:external,cookie,'content-type':'application/json'},body:JSON.stringify({action:'stop',id:'regression-test'})});assert.equal(api.status,400);assert.ok(!(await api.text()).includes('Origine refusée'));
 console.log('PASS: public HTTPS origin behind internal HTTP proxy, login/session, secure cookie, API and foreign/missing origin rejection.');
}finally{clearTimeout(timeout);proc.kill();}
