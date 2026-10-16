import http from 'node:http';
import {createHash,createHmac,timingSafeEqual,randomBytes} from 'node:crypto';
import {readFile,stat} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {join,resolve,extname} from 'node:path';
import {handleBridge} from './lib/bridge-service.mjs';
const root=resolve(fileURLToPath(new URL('./public',import.meta.url)));
const password=process.env.APP_PASSWORD;
if(!password||password.length<16)throw Error('Définir APP_PASSWORD avec au moins 16 caractères dans les variables de l’hébergeur.');
const secret=process.env.SESSION_SECRET||randomBytes(32).toString('hex');
const hash=s=>createHash('sha256').update(s).digest();
const equal=(a,b)=>timingSafeEqual(hash(a),hash(b));
const hmac=s=>createHmac('sha256',secret).update(s).digest('hex');
const connection=new Map();const bucket={get:async k=>connection.has(k)?{json:async()=>JSON.parse(connection.get(k))}:null,put:async(k,v)=>connection.set(k,v),delete:async k=>connection.delete(k)};
const limits=new Map();
function session(req){const token=(req.headers.cookie||'').split(';').map(x=>x.trim()).find(x=>x.startsWith('ben_session='))?.slice(12);if(!token)return false;const [expires,sig]=token.split('.');return !!sig&&Number(expires)>Date.now()&&equal(sig,hmac(expires));}
const login=error=>`<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Ben Bot · Connexion</title><style>body{background:#040604;color:#dadbc6;font:14px system-ui;display:grid;min-height:90vh;place-items:center;margin:0}form{width:min(320px,80vw);padding:30px;border:1px solid #2d3520;border-radius:8px;background:#090d07}h1{color:#d8b95f;letter-spacing:3px;font-size:24px}p{color:#859174;font-size:12px;line-height:1.8}label{font-size:12px}input{box-sizing:border-box;display:block;width:100%;margin:12px 0 20px;background:#030602;color:#e7ecd8;padding:12px;border:1px solid #354627;border-radius:4px}button{width:100%;background:#3bdaae;color:#062c1d;padding:12px;border:0;border-radius:4px;font-weight:600}.error{color:#f2969d}</style><form method="post" action="/login"><h1>BEN BOT</h1><p>Poste de commande privé<br>MetaTrader 5 · Compte démo</p>${error?'<p class="error">Mot de passe incorrect ou trop de tentatives.</p>':''}<label>Mot de passe du site<input name="password" type="password" required autocomplete="current-password" autofocus></label><button>Accéder au bot →</button><p>Utilise le mot de passe configuré chez ton hébergeur.</p></form></html>`;
const types={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'application/javascript; charset=utf-8','.csv':'text/csv','.zip':'application/zip','.json':'application/json'};
async function body(req,max=4096){let size=0;const parts=[];for await(const chunk of req){size+=chunk.length;if(size>max)throw Error('Corps trop grand');parts.push(chunk);}return Buffer.concat(parts).toString();}
const app=http.createServer(async(req,res)=>{const send=(status,data,headers={})=>{res.writeHead(status,{'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'no-referrer',...headers});res.end(data);};try{
 const host=req.headers.host||'localhost';const origin=process.env.PUBLIC_URL?new URL(process.env.PUBLIC_URL).origin:`${process.env.NODE_ENV==='production'?'https':'http'}://${host}`;const u=new URL(req.url,origin);
 if(u.pathname==='/health')return send(200,'ok');
 if(u.pathname==='/login'){
  if(req.method==='POST'){
   if(req.headers.origin!==origin)return send(403,'Origine refusée');
   const ip=req.socket.remoteAddress;const now=Date.now();const rate=limits.get(ip)||{count:0,since:now};if(now-rate.since>60000){rate.count=0;rate.since=now;}rate.count++;limits.set(ip,rate);if(limits.size>1000)for(const[k,v]of limits)if(now-v.since>60000)limits.delete(k);
   const value=new URLSearchParams(await body(req)).get('password')||'';
   if(rate.count>10||!equal(value,password))return send(401,login(true),{'Content-Type':'text/html; charset=utf-8'});
   const exp=String(now+12*3600000),cookie=`ben_session=${exp}.${hmac(exp)}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200${process.env.NODE_ENV==='production'?'; Secure':''}`;
   return send(303,'',{Location:'/', 'Set-Cookie':cookie});
  }return send(200,login(false),{'Content-Type':'text/html; charset=utf-8'});
 }
 if(!session(req)){if(u.pathname.startsWith('/api/'))return send(401,JSON.stringify({error:'Connexion requise.'}),{'Content-Type':'application/json'});return send(303,'',{Location:'/login'});}
 if(u.pathname==='/api/bridge'){
  const h=new Headers();h.set('oai-authenticated-user-id','owner');if(req.headers.origin)h.set('Origin',req.headers.origin);if(req.headers['content-type'])h.set('Content-Type',req.headers['content-type']);const r=await handleBridge(new Request(origin+'/api/bridge',{method:req.method,headers:h,body:req.method==='POST'?await body(req):undefined}),bucket);return send(r.status,Buffer.from(await r.arrayBuffer()),Object.fromEntries(r.headers));
 }
 if(!['GET','HEAD'].includes(req.method))return send(405,'Méthode refusée');
 const pathname=u.pathname==='/'?'/control.html':decodeURIComponent(u.pathname),file=resolve(root,'.'+pathname);if(!file.startsWith(root+'/'))return send(403,'Accès refusé');if(!(await stat(file)).isFile())return send(404,'Introuvable');return send(200,req.method==='HEAD'?'':await readFile(file),{'Content-Type':types[extname(file)]||'application/octet-stream'});
}catch(e){send(e.code==='ENOENT'?404:400,e.code==='ENOENT'?'Introuvable':'Requête refusée.');}});
app.listen(Number(process.env.PORT||3000),'0.0.0.0',()=>console.log('Ben Bot prêt sur le port '+(process.env.PORT||3000)));
