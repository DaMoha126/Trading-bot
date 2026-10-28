// Single-instance, in-memory reverse HTTP relay. Never retries a dispatched request.
import http from 'node:http';
import {randomUUID, createHash, timingSafeEqual} from 'node:crypto';
export const allowed = new Set(['/','/login','/logout','/control.html','/control.css','/control.js','/guide.css','/api/bridge','/lab/index.html','/lab/app.js','/lab/style.css','/lab/engine.js','/lab/worker.js','/lab/demo.csv']);
const baseHeaders={'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY','Referrer-Policy':'same-origin'};
const digest=s=>createHash('sha256').update(s).digest();
const equal=(a,b)=>timingSafeEqual(digest(a),digest(b));
async function read(req,max){let size=0;const parts=[];for await(const c of req){size+=c.length;if(size>max)throw Error('size');parts.push(c);}return Buffer.concat(parts);}
const offline='<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Trading Bot · Moteur déconnecté</title><style>body{font:16px system-ui;max-width:560px;margin:15vh auto;padding:24px;background:#080c0a;color:#ecf0e8}h1{color:#d6bb72}p{line-height:1.7}a{color:#64dfbc}</style><h1>Trading Bot</h1><h2>Moteur du PC déconnecté</h2><p>Le site est disponible. Pour retrouver ton compte, garde MT5, le service Trading Bot et la liaison sortante ouverts sur le PC.</p><p>La reconnexion ne démarre pas le bot.</p><a href="/login">Réessayer la connexion</a></html>';
export function createRelayServer({key,origin,ttl=25000,onlineMs=35000,maxPending=32}){
 if(typeof key!=='string'||key.length<32||!origin||new URL(origin).protocol!=='https:'||new URL(origin).origin!==origin)throw Error('MT5_HOST_KEY et PUBLIC_URL HTTPS requis.');
 const jobs=new Map();let queue=[];let agent=null;let seen=0;let closing=false;
 const send=(res,status,body='',headers={})=>{if(res.destroyed||res.writableEnded)return;res.writeHead(status,{...baseHeaders,...headers});res.end(body);};
 const fail=(res,status,message)=>send(res,status,JSON.stringify({error:message}),{'Content-Type':'application/json; charset=utf-8'});
 const finish=(id,status,body,headers={})=>{const job=jobs.get(id);if(!job)return false;clearTimeout(job.timer);jobs.delete(id);job.payload=null;send(job.res,status,body,headers);return true;};
 const server=http.createServer(async(req,res)=>{
  try{
   const u=new URL(req.url,origin);
   if(req.url.length>2048)return fail(res,414,'Adresse trop longue.');
   if(u.pathname==='/health'&&req.method==='GET')return send(res,200,'ok',{'Content-Type':'text/plain'});
   if(u.pathname.startsWith('/relay/')){
    if(!equal(req.headers.authorization||'','Bearer '+key))return fail(res,401,'Accès refusé.');
    const aid=req.headers['x-relay-agent'];
    if(typeof aid!=='string'||!/^[a-f0-9-]{36}$/.test(aid))return fail(res,400,'Identité de liaison invalide.');
    const now=Date.now();
    if(agent&&agent!==aid&&now-seen<onlineMs)return fail(res,409,'Une liaison est déjà active.');
    if(agent!==aid){
     for(const [id,j] of jobs)if(j.dispatched)finish(id,503,JSON.stringify({error:'Liaison remplacée. Résultat inconnu : vérifier MT5 avant toute nouvelle commande.'}),{'Content-Type':'application/json'});
     agent=aid;
    }
    seen=now;
    if(u.pathname==='/relay/poll'&&req.method==='GET'){
     let job;
     while(queue.length){const id=queue.shift();const candidate=jobs.get(id);if(candidate&&candidate.deadline>Date.now()){job=candidate;break;}}
     if(!job)return send(res,204);
     job.dispatched=true;job.agent=aid;
     const payload={...job.payload,id:job.id,deadline:job.deadline,serverTime:Date.now()};job.payload=null;
     return send(res,200,JSON.stringify(payload),{'Content-Type':'application/json'});
    }
    if(u.pathname==='/relay/result'&&req.method==='POST'){
     const data=JSON.parse((await read(req,4100000)).toString('utf8'));
     const job=jobs.get(data.id);
     if(!job||!job.dispatched||job.agent!==aid||job.deadline<Date.now())return fail(res,410,'Réponse expirée. Ne pas rejouer la requête.');
     if(!Number.isInteger(data.status)||data.status<200||data.status>599||typeof data.body!=='string'||!/^[A-Za-z0-9+/]*={0,2}$/.test(data.body))return fail(res,400,'Réponse invalide.');
     const body=Buffer.from(data.body,'base64');if(body.length>3000000)return fail(res,413,'Réponse trop grande.');
     const h={};for(const name of ['content-type','set-cookie','location']){const value=data.headers?.[name];if(value!==undefined){if(typeof value!=='string'||value.length>16000||/[\r\n]/.test(value))return fail(res,400,'En-tête invalide.');h[name]=value;}}
     if(data.status>=300&&data.status<400&&!['/','/login'].includes(h.location))return fail(res,400,'Redirection refusée.');
     finish(data.id,data.status,body,h);return send(res,200,'ok');
    }
    return fail(res,404,'Introuvable.');
   }
   if(!['GET','POST'].includes(req.method))return fail(res,405,'Méthode refusée.');
   if(!allowed.has(u.pathname)||u.origin!==origin||req.url[0]!=='/')return fail(res,404,'Introuvable.');
   if(req.method==='POST'&&req.headers.origin!==origin)return fail(res,403,'Origine refusée.');
   if(closing||!agent||Date.now()-seen>onlineMs){
    if(req.method==='GET'&&['/','/login','/control.html'].includes(u.pathname))return send(res,503,offline,{'Content-Type':'text/html; charset=utf-8'});
    return fail(res,503,'Moteur du PC déconnecté. Aucune commande envoyée.');
   }
   if(jobs.size>=maxPending)return fail(res,503,'Liaison occupée. Aucune commande envoyée.');
   const bytes=await read(req,4096);const headers={};
   for(const name of ['cookie','content-type','origin'])if(req.headers[name]){const value=req.headers[name];if(typeof value!=='string'||value.length>16000)return fail(res,400,'En-tête trop grand.');headers[name]=value;}
   const id=randomUUID();
   const job={id,res,deadline:Date.now()+ttl,dispatched:false,payload:{method:req.method,path:u.pathname+u.search,headers,body:bytes.toString('base64')}};
   job.timer=setTimeout(()=>finish(id,504,JSON.stringify({error:job.dispatched?'Réponse non reçue. Résultat inconnu : vérifier MT5 avant toute nouvelle commande.':'PC indisponible. Aucune commande envoyée.'}),{'Content-Type':'application/json'}),ttl);
   jobs.set(id,job);queue.push(id);
   // Drop disconnected browser requests; already dispatched requests are never requeued.
   res.on('close',()=>{const j=jobs.get(id);if(j){clearTimeout(j.timer);j.payload=null;jobs.delete(id);}});
   if(queue.length>maxPending*2)queue=queue.filter(x=>jobs.has(x));
  }catch(e){fail(res,e.message==='size'?413:400,'Requête refusée.');}
 });
 server.on('close',()=>{for(const j of jobs.values())clearTimeout(j.timer);jobs.clear();queue=[];});
 server.shutdown=()=>{closing=true;for(const id of [...jobs.keys()])finish(id,503,JSON.stringify({error:'Service redémarré. Vérifier MT5 avant toute nouvelle commande.'}),{'Content-Type':'application/json'});server.close();};
 return server;
}
