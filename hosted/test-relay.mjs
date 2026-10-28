import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {createRelayServer} from './relay-server.mjs';
const origin='https://bot.example',key='test-only-key-not-a-real-secret-123456789';
async function fixture(options={}){
 const server=createRelayServer({key,origin,...options});await new Promise(r=>server.listen(0,'127.0.0.1',r));
 const url='http://127.0.0.1:'+server.address().port;const agent=randomUUID();
 const call=(path,options={})=>fetch(url+path,{redirect:'manual',...options});
 const auth={'Authorization':'Bearer '+key,'X-Relay-Agent':agent};
 const poll=()=>call('/relay/poll',{headers:auth});
 return {server,call,auth,poll,close:async()=>{server.shutdown();server.closeAllConnections();await new Promise(r=>setTimeout(r,1));}};
}
test('health and clear offline page independent of PC',async()=>{const f=await fixture();try{
 assert.equal((await f.call('/health')).status,200);
 const r=await f.call('/login');assert.equal(r.status,503);assert.match(await r.text(),/Moteur du PC déconnecté/);
}finally{await f.close();}});
test('relay auth and public CSRF cannot be bypassed',async()=>{const f=await fixture();try{
 assert.equal((await f.call('/relay/poll')).status,401);
 assert.equal((await f.call('/relay/poll',{headers:{...f.auth,Authorization:'Bearer wrong'}})).status,401);
 assert.equal((await f.poll()).status,204);
 assert.equal((await f.call('/api/bridge',{method:'POST',headers:{Origin:'https://evil.example'},body:'{}'})).status,403);
 assert.equal((await f.call('/secrets')).status,404);
}finally{await f.close();}});
test('login request and secure cookie roundtrip; never dispatch twice',async()=>{const f=await fixture();try{
 await f.poll();
 const pending=f.call('/login',{method:'POST',headers:{Origin:origin,'Content-Type':'application/x-www-form-urlencoded'},body:'login=123&password=test-only'});
 await new Promise(r=>setTimeout(r,20));
 const job=await (await f.poll()).json();assert.equal(job.method,'POST');assert.equal(job.headers.origin,origin);
 assert.match(Buffer.from(job.body,'base64').toString(),/password=test-only/);
 assert.equal((await f.poll()).status,204);
 const result=await f.call('/relay/result',{method:'POST',headers:{...f.auth,'Content-Type':'application/json'},body:JSON.stringify({id:job.id,status:303,headers:{location:'/', 'set-cookie':'session=test; Secure; HttpOnly; SameSite=Strict'},body:''})});
 assert.equal(result.status,200);
 const response=await pending;assert.equal(response.status,303);assert.match(response.headers.get('set-cookie'),/HttpOnly/);
 assert.equal((await f.call('/relay/result',{method:'POST',headers:f.auth,body:JSON.stringify({id:job.id,status:200,body:''})})).status,410);
}finally{await f.close();}});
test('expired queued requests are not delivered',async()=>{const f=await fixture({ttl:80});try{
 await f.poll();const pending=f.call('/api/bridge',{method:'POST',headers:{Origin:origin},body:'{"action":"start"}'});
 assert.equal((await pending).status,504);assert.equal((await f.poll()).status,204);
}finally{await f.close();}});
test('lost response gives uncertain status; no replay',async()=>{const f=await fixture({ttl:100});try{
 await f.poll();const pending=f.call('/api/bridge',{method:'POST',headers:{Origin:origin},body:'{"action":"start"}'});
 await new Promise(r=>setTimeout(r,20));assert.equal((await f.poll()).status,200);
 const r=await pending;assert.equal(r.status,504);assert.match(await r.text(),/Résultat inconnu/);assert.equal((await f.poll()).status,204);
}finally{await f.close();}});
test('single active agent and bounded queue',async()=>{const f=await fixture({ttl:100,maxPending:1});try{
 await f.poll();assert.equal((await f.call('/relay/poll',{headers:{...f.auth,'X-Relay-Agent':randomUUID()}})).status,409);
 const pending=f.call('/api/bridge');await new Promise(r=>setTimeout(r,20));assert.equal((await f.call('/api/bridge')).status,503);
 assert.equal((await pending).status,504);
}finally{await f.close();}});
test('external redirects and response header injection rejected',async()=>{const f=await fixture({ttl:120});try{
 await f.poll();const pending=f.call('/login');await new Promise(r=>setTimeout(r,20));const j=await (await f.poll()).json();
 const r=await f.call('/relay/result',{method:'POST',headers:f.auth,body:JSON.stringify({id:j.id,status:302,headers:{location:'https://evil.example'},body:''})});assert.equal(r.status,400);
 assert.equal((await pending).status,504);
}finally{await f.close();}});
