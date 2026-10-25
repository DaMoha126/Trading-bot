import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';
const source = (await readFile(new URL('./proxy.mjs', import.meta.url), 'utf8')).replace("import http from 'node:http';", '');
function setup(env = {}) {
  let handle; const calls = [];
  const context = vm.createContext({
    process:{env:{MT5_HOST_URL:'https://pilot.trycloudflare.com',MT5_HOST_KEY:'k'.repeat(40),PUBLIC_URL:'https://bot.example',...env}},
    http:{createServer(fn){handle=fn;return {listen(){}};}},
    URL, Headers, Buffer, AbortSignal,
    fetch:async(url, options)=>{calls.push({url,options});return new Response('ok',{status:200,headers:{'content-type':'text/plain'}});}
  });
  vm.runInContext(source,context);
  return {calls, async request(method, url, headers={}, body='') {
    const req = {method,url,headers,async *[Symbol.asyncIterator](){if(body) yield Buffer.from(body);}};
    const out = {headersSent:false,writeHead(status,headers){this.status=status;this.headers=headers;this.headersSent=true;},end(data){this.body=data;}};
    await handle(req,out);return out;
  }};
}
for (const url of ['http://pilot.trycloudflare.com','https://localhost','https://evil.example','https://pilot.trycloudflare.com/path',
  'https://other.ngrok-free.dev','https://refreeze-throwback-ladder.ngrok-free.dev.evil.example',
  'https://refreeze-throwback-ladder.ngrok-free.dev:8443','https://refreeze-throwback-ladder.ngrok-free.dev/private']) {
  assert.throws(()=>setup({MT5_HOST_URL:url}));
}
const proxy = setup();
assert.equal((await proxy.request('GET','/hosted/accounts.json')).status,404);
assert.equal((await proxy.request('DELETE','/api/bridge')).status,405);
assert.equal((await proxy.request('POST','/login',{origin:'https://evil.example'},'password=x')).status,403);
assert.equal((await proxy.request('POST','/login',{origin:'https://bot.example'},'x'.repeat(4097))).status,413);
assert.equal(proxy.calls.length,0);
const response=await proxy.request('POST','/login',{origin:'https://bot.example','content-type':'application/x-www-form-urlencoded',authorization:'Bearer attacker',cookie:'mt5_session=opaque'},'password=demo');
assert.equal(response.status,200);
assert.equal(proxy.calls[0].url,'https://pilot.trycloudflare.com/login');
assert.equal(proxy.calls[0].options.headers.get('authorization'),'Bearer '+'k'.repeat(40));
assert.equal(proxy.calls[0].options.headers.get('cookie'),'mt5_session=opaque');
assert.equal(proxy.calls[0].options.redirect,'manual');
const ngrok=setup({MT5_HOST_URL:'https://refreeze-throwback-ladder.ngrok-free.dev'});
assert.equal((await ngrok.request('GET','/health',{'ngrok-skip-browser-warning':'attacker',authorization:'attacker'})).status,200);
assert.equal(ngrok.calls[0].url,'https://refreeze-throwback-ladder.ngrok-free.dev/health');
assert.equal(ngrok.calls[0].options.headers.get('ngrok-skip-browser-warning'),'1');
assert.equal(ngrok.calls[0].options.headers.get('authorization'),'Bearer '+'k'.repeat(40));
console.log('PASS: hosted proxy target allowlist, private routes, methods, body limit, origin, service-key isolation and session forwarding.');
