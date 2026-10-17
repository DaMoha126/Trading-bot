import {createHash,createCipheriv,createDecipheriv,randomBytes} from 'node:crypto';
const NAME='trading_connection',TTL=30*24*3600;
function key(secret){return createHash('sha256').update('trading-bot-link-v1\0'+secret).digest();}
export function sealConnection(value,secret,now=Date.now()){
 const iv=randomBytes(12),cipher=createCipheriv('aes-256-gcm',key(secret),iv);
 const data=Buffer.concat([cipher.update(JSON.stringify({value,expires:now+TTL*1000}),'utf8'),cipher.final()]);
 return Buffer.concat([iv,cipher.getAuthTag(),data]).toString('base64url');
}
export function openConnection(token,secret,now=Date.now()){
 try{if(!token||token.length>2000)return null;const b=Buffer.from(token,'base64url');if(b.length<29)return null;
 const decipher=createDecipheriv('aes-256-gcm',key(secret),b.subarray(0,12));decipher.setAuthTag(b.subarray(12,28));
 const data=JSON.parse(Buffer.concat([decipher.update(b.subarray(28)),decipher.final()]).toString());
 if(!Number.isFinite(data.expires)||data.expires<=now||typeof data.value!=='string')return null;return data.value;
 }catch{return null;}
}
export function connectionBucket(request,secret,secure){
 const token=(request.headers.cookie||'').split(';').map(s=>s.trim()).find(s=>s.startsWith(NAME+'='))?.slice(NAME.length+1);
 let value=openConnection(token,secret),cookie=null;
 const serialize=(token,max)=>`${NAME}=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${max}${secure?'; Secure':''}`;
 return{get cookie(){return cookie;},async get(){return value?{json:async()=>JSON.parse(value)}:null;},async put(_key,newValue){value=newValue;cookie=serialize(sealConnection(newValue,secret),TTL);},async delete(){value=null;cookie=serialize('',0);}};
}
