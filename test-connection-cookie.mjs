import assert from 'node:assert/strict';
import {sealConnection,openConnection,connectionBucket} from './lib/connection-cookie.mjs';
const secret='unit-test-only-stable-secret',value=JSON.stringify({url:'https://test.trycloudflare.com',key:'fake-key-for-test'}),now=Date.now();
const token=sealConnection(value,secret,now);assert.equal(openConnection(token,secret,now+1),value);assert.ok(!token.includes('fake-key-for-test'));
assert.equal(openConnection(token,'wrong-secret',now),null);assert.equal(openConnection(token,secret,now+31*86400000),null);
const damaged=token.slice(0,30)+(token[30]==='a'?'b':'a')+token.slice(31);assert.equal(openConnection(damaged,secret,now),null);
const before=connectionBucket({headers:{}},secret,true);await before.put('owner',value);assert.ok(before.cookie.includes('HttpOnly'));assert.ok(before.cookie.includes('SameSite=Strict'));assert.ok(before.cookie.includes('; Secure'));
// A fresh store instance models a new server process: no shared memory.
const after=connectionBucket({headers:{cookie:before.cookie.split(';')[0]}},secret,true);assert.deepEqual(await (await after.get('owner')).json(),JSON.parse(value));await after.delete('owner');assert.equal(await after.get(),null);assert.ok(after.cookie.includes('Max-Age=0'));
console.log('PASS: encrypted link survives new process, secret stays opaque, expiry/tamper/key rotation rejected, secure cookie and removal.');
