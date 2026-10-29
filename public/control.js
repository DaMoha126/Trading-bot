'use strict';
let settingsAccount=null,settingsDirty=false,settingsSignature="";
const $=id=>document.getElementById(id),format=n=>Number(n).toLocaleString('fr-FR',{minimumFractionDigits:2,maximumFractionDigits:2}),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let state=null,polling=false,acting=false,points=[],accountKey='',historyLimit=50;
function alertText(s){$('alert').textContent=s||'';$('alert').hidden=!s;}
async function api(body){let r;try{r=await fetch('/api/bridge',{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined,cache:'no-store'});}catch{throw Error('Réponse réseau non reçue. État de la commande inconnu : actualise le tableau de bord avant de réessayer.');}let d;try{d=await r.json();}catch{throw Error('Session expirée ou service indisponible. Recharge la page pour te reconnecter.');}if(r.status===401){location.href='/login';throw Error('Connexion requise.');}if(!r.ok)throw Error(d.error||'La commande a échoué.');return d;}
function render(d){state=d;renderStrategySettings(d);const latest=(d.events||[]).filter(x=>x.event==='SIGNAL').at(-1);for(const [id,on] of [['step-connect',d.connected],['step-structure',d.running],['step-signal',d.running&&latest&&Date.now()/1000-latest.time<180],['analysis-dot',d.running]])$(id).classList.toggle('active',!!on);$('analysis-caption').textContent=d.running?'Le bot surveille la structure M1 et les prises de liquidité.':d.connected?'Compte connecté. Démarre le bot pour activer la stratégie.':'Relie ton compte démo pour commencer l’analyse.';const ok=d.connected&&d.account?.demo===true;$('connection').textContent=ok?'CONNECTÉ':d.paired?'LIAISON INTERROMPUE':'NON CONNECTÉ';$('connection').className='chip'+(ok?' on':'');$('bot-state').textContent=d.running===null?'ÉTAT INCONNU':d.running?'EN MARCHE':d.halted?'LIMITE ATTEINTE':'À L’ARRÊT';$('bot-state').className='chip'+(d.running===null?' unknown':d.running?' running':'');$('start').disabled=!ok||!!d.running||!!d.halted||acting;$('stop').disabled=!d.paired||acting;$('unpair').disabled=!d.paired||acting;['symbol','risk','daily','rr'].forEach(id=>$(id).disabled=!!d.running);$('autonomous').disabled=!!d.running||!ok||d.connector_version!=='4.0';if(d.running){$('autonomous').checked=d.supervision==='autonomous';$('symbol').value=d.symbol;$('risk').value=(d.risk*100).toFixed(2);if(Number.isFinite(d.daily_loss))$('daily').value=(d.daily_loss*100).toFixed(2);$('rr').value=d.rr;}if(ok&&d.connector_version!=='4.0')$('autonomous').checked=false;$('bot-description').textContent=d.running?(d.supervision==='autonomous'?'Mode autonome : tu peux fermer le site. Garde le PC, MT5 et le connecteur ouverts.':'Mode supervisé : garde le tableau de bord actif.'):ok?'Compte démo prêt. Aucun ordre avant de cliquer sur Démarrer.':'Le connecteur doit être actif sur ton PC pour démarrer.';
if(ok){const a=d.account,key=a.login+'@'+a.server;if(key!==accountKey){points=[];accountKey=key;if(d.symbol)$('symbol').value=d.symbol;}$('balance').innerHTML=format(a.balance)+' <small>USD</small>';$('equity').textContent=format(a.equity)+' $';$('profit').textContent=(a.profit>0?'+':'')+format(a.profit)+' $';$('profit').className=a.profit>=0?'positive':'negative';$('margin').textContent=format(a.free_margin)+' $';$('account-label').textContent='Compte démo #'+a.login;$('server').textContent=a.server;$('updated').textContent='Actualisé à '+new Date().toLocaleTimeString('fr-FR');if(Array.isArray(d.equity_curve)&&d.equity_curve.length)points=d.equity_curve.map(p=>({v:p.equity,t:p.time*1000})).slice(-2880);else{points.push({v:a.equity,t:Date.now()});points=points.slice(-150);}$('empty-chart').hidden=true;draw();}else{$('account-label').textContent=d.paired?'Dernières données connues — connexion interrompue.':'Relie ton PC pour afficher ton compte.';$('updated').textContent='Hors connexion';}
if($('quote-symbol'))$('quote-symbol').textContent=d.symbol||'—';const digits=Number.isInteger(d.price_digits)&&d.price_digits>=0&&d.price_digits<=8?d.price_digits:5;if(d.quote&&ok){$('bid').textContent=d.quote.bid.toFixed(digits);$('ask').textContent=d.quote.ask.toFixed(digits);$('quote-age').textContent=Date.now()/1000-d.quote.time>30?'Cotation périmée':'';}else{$('bid').textContent=$('ask').textContent='—';$('quote-age').textContent='';}
const ps=ok?d.positions||[]:[];$('position-count').textContent=ps.length+' position'+(ps.length===1?'':'s');$('positions').innerHTML=ps.map(p=>`<tr><td>${esc(p.symbol)}</td><td class="${p.side==='BUY'?'positive':'negative'}">${esc(p.side)}</td><td>${p.volume}</td><td>${p.entry.toFixed(5)}</td><td>${p.current.toFixed(5)}</td><td>${p.sl.toFixed(5)} / ${p.tp.toFixed(5)}</td><td class="${p.profit>=0?'positive':'negative'}">${format(p.profit)} $</td><td>${p.owned?'Trading Bot':'Autre'}</td></tr>`).join('')||`<tr><td colspan="8" class="empty">${ok?'Aucune position ouverte sur le compte.':'Connecte ton compte pour voir les positions.'}</td></tr>`;
const events=d.events||[];$('events').innerHTML=events.slice().reverse().map(e=>`<div class="event"><time>${new Date(e.time*1000).toLocaleTimeString('fr-FR')}</time><div><strong>${esc(e.event)}</strong><p>${esc([e.detail,e.side===1?'BUY':e.side===-1?'SELL':e.side,Number.isFinite(e.level)?'Niveau : '+e.level:'',e.symbol,e.volume?'Lots : '+e.volume:'',e.price?'Prix : '+e.price:''].filter(Boolean).join(' · ')||'Événement enregistré')}</p></div></div>`).join('')||'<p class="empty">Les actions et décisions du bot apparaîtront ici.</p>';
renderDiagnostics(d);renderHistory();$('remove-account').disabled=!d.paired||acting;if(d.error)alertText(d.error);}
function renderDiagnostics(d){
const box=$('engine-diagnostics');if(!box)return;
const diag=d.diagnostics,clock=t=>Number.isFinite(t)?new Date(t*1000).toLocaleString('fr-FR',{timeZone:'UTC'})+' UTC':'—';
if(!d.connected||!diag){$('engine-cycle').textContent=d.connected?'Diagnostic indisponible : mettre à jour le service du PC.':'Diagnostic indisponible : connexion interrompue.';for(const id of ['engine-last-bar','engine-count','engine-stage','engine-structure','engine-choch','engine-zone'])$(id).textContent='';return;}
const age=Number.isFinite(diag.last_cycle_at)?Math.max(0,Math.floor((Number.isFinite(d.time)?d.time:Date.now()/1000)-diag.last_cycle_at)):null;
$('engine-cycle').textContent=!d.running?'Moteur arrêté':age===null?'Premier cycle de surveillance en attente':age>15?'Surveillance à vérifier : dernier cycle il y a '+age+' s':'Dernier cycle réussi : '+clock(diag.last_cycle_at);
$('engine-last-bar').textContent='Dernière bougie traitée (clôture) : '+clock(diag.last_bar_close);
$('engine-count').textContent='Bougies après démarrage : '+diag.live_bars+' · Historique initial : '+diag.warmup_bars;
$('engine-stage').textContent='État : '+diag.stage+(d.running&&diag.live_bars===0?' · Aucune nouvelle bougie traitée depuis le démarrage.':'');
const digits=Number.isInteger(d.price_digits)&&d.price_digits>=0&&d.price_digits<=8?d.price_digits:5,price=n=>Number.isFinite(n)?n.toFixed(digits):'—';
const pivot=p=>Array.isArray(p)?price(p[1])+' (bougie ouverte à '+clock(p[0])+')':'—';
$('engine-structure').textContent='Structure : '+(diag.trend===1?'haussière':diag.trend===-1?'baissière':'indéterminée')+' · Sommet : '+pivot(diag.swing_high)+' · Creux : '+pivot(diag.swing_low);
const ch=diag.last_choch;
$('engine-choch').textContent=ch?'Dernier CHoCH depuis démarrage : '+(ch.side===1?'haussier · BUY':'baissier · SELL')+' · Niveau cassé : '+price(ch.level)+' · Clôture : '+clock(ch.time):'Aucun CHoCH détecté depuis ce démarrage.';
const z=diag.zone;
$('engine-zone').textContent=z?'Zone active '+(z.side===1?'support · BUY':'résistance · SELL')+' : '+price(z.low)+' à '+price(z.high)+' · '+(z.retested?'Retest détecté, rejet attendu':'Retest attendu'):'Aucune zone active. Un ancien CHoCH ne signifie pas qu’une entrée reste valide.';
}
async function poll(){if(polling||acting)return;polling=true;try{render(await api());}catch(e){$('start').disabled=true;$('connection').textContent='SERVICE INJOIGNABLE';$('bot-state').textContent='ÉTAT INCONNU';$('bot-state').className='chip unknown';alertText(e.message);}finally{polling=false;}}
async function command(body){if(acting)return;acting=true;$('start').disabled=$('stop').disabled=$('pair').disabled=$('unpair').disabled=true;try{alertText('');const d=await api(body);acting=false;render(d);if(d.warning)alertText(d.warning);return d;}catch(e){alertText(e.message);}finally{acting=false;$('pair').disabled=false;if(state)render(state);}}
$('pair-form').onsubmit=async e=>{e.preventDefault();const d=await command({action:'pair',url:$('bridge-url').value.trim(),key:$('bridge-key').value.trim()});if(d){$('bridge-key').value='';$('bridge-url').value='';document.getElementById('dashboard').scrollIntoView({behavior:'smooth'});}};
$('start-form').onsubmit=e=>{e.preventDefault();command({action:'start',id:crypto.randomUUID(),symbol:$('symbol').value.trim(),supervision:$('autonomous').checked?'autonomous':'browser'});};$('stop').onclick=()=>command({action:'stop',id:crypto.randomUUID()});$('unpair').onclick=()=>command({action:'unpair'});
function draw(){const canvas=$('chart'),box=canvas.getBoundingClientRect();if(!box.width||!points.length)return;const dpr=devicePixelRatio||1;canvas.width=box.width*dpr;canvas.height=box.height*dpr;const c=canvas.getContext('2d');c.scale(dpr,dpr);const w=box.width,h=box.height;let lo=Math.min(...points.map(p=>p.v)),hi=Math.max(...points.map(p=>p.v));const pad=Math.max((hi-lo)*.2,1);lo-=pad;hi+=pad;const y=v=>15+(hi-v)/(hi-lo)*(h-35),x=i=>58+i/Math.max(1,points.length-1)*(w-70);c.font='9px system-ui';for(let i=0;i<4;i++){const v=lo+(hi-lo)*i/3,yy=y(v);c.strokeStyle='#2b3526';c.lineWidth=1;c.beginPath();c.moveTo(55,yy);c.lineTo(w-10,yy);c.stroke();c.fillStyle='#6f8560';c.textAlign='right';c.fillText(v.toFixed(0),48,yy+3);}c.beginPath();points.forEach((p,i)=>i?c.lineTo(x(i),y(p.v)):c.moveTo(x(i),y(p.v)));c.lineWidth=2;c.strokeStyle='#c5af70';c.stroke();if(points.length===1){c.beginPath();c.arc(x(0),y(points[0].v),3,0,Math.PI*2);c.fillStyle='#c5af70';c.fill();}}
window.addEventListener('resize',draw);poll();setInterval(poll,5000);

$('remove-account').onclick=()=>$('unpair').click();

function historyRows(){return(state?.history?.trades||[]).filter(t=>$('history-side').value==='all'||t.side===$('history-side').value);}
function renderHistory(){
 const h=state?.history,rows=historyRows(),valid=state?.connected&&h?.status==='ok';
 $('export-trades').disabled=!valid||!rows.length;$('export-report').disabled=!valid;
 if(!valid){$('history-status').textContent=!state?.connected?'Connecte le PC pour charger l’historique.':state?.connector_version!=='4.0'?'Mets à jour le connecteur Windows pour activer l’historique.':h?.detail||'Historique MT5 indisponible.';$('closed-trades').innerHTML='<tr><td colspan="8" class="empty">Historique indisponible.</td></tr>';for(const id of ['history-net','history-win','history-count','history-expectancy'])$(id).textContent='—';return;}
 const net=rows.reduce((sum,t)=>sum+t.net,0),wins=rows.filter(t=>t.net>0).length;
 $('history-net').textContent=format(net)+' $';$('history-net').className=net>=0?'positive':'negative';$('history-win').textContent=(rows.length?wins/rows.length*100:0).toFixed(1)+' %';$('history-count').textContent=rows.length;$('history-expectancy').textContent=format(rows.length?net/rows.length:0)+' $';
 $('history-status').textContent=`90 jours · ${h.excluded_mixed||0} positions mixtes et ${h.excluded_incomplete||0} incomplètes exclues${h.truncated?' · affichage limité aux 500 dernières positions':''}. Montants liés aux exécutions MT5.`;
 $('closed-trades').innerHTML=rows.slice().reverse().slice(0,historyLimit).map(t=>`<tr><td>${new Date(t.closed*1000).toISOString().slice(0,16).replace('T',' ')}</td><td class="${t.side==='BUY'?'positive':'negative'}">${esc(t.side)}</td><td>${t.volume}</td><td>${t.entry.toFixed(5)} / ${t.exit.toFixed(5)}</td><td>${format(t.commission+t.fee)}</td><td>${format(t.swap)}</td><td class="${t.net>=0?'positive':'negative'}">${format(t.net)}</td><td>${esc(t.reason)}${t.exit_deals>1?' · '+t.exit_deals+' sorties':''}</td></tr>`).join('')||'<tr><td colspan="8" class="empty">Aucune position clôturée du bot pour ce filtre.</td></tr>';
 $('more-trades').hidden=rows.length<=historyLimit;
}
function download(text,name,type){const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
const csvCell=value=>{let s=String(value??'');if(typeof value==='string'&&/^[=+@-]/.test(s))s="'"+s;return '"'+s.replace(/"/g,'""')+'"';};
$('history-side').onchange=()=>{historyLimit=50;renderHistory();};$('more-trades').onclick=()=>{historyLimit+=50;renderHistory();};
$('export-trades').onclick=()=>{const keys=['id','symbol','side','volume','opened','closed','entry','exit','profit','commission','swap','fee','net','reason'];const text=[keys.map(csvCell).join(','),...historyRows().map(t=>keys.map(k=>csvCell(t[k])).join(','))].join('\r\n');download('\uFEFF'+text,'trading-bot-historique.csv','text/csv;charset=utf-8');};
$('export-report').onclick=()=>{if(state?.history)download(JSON.stringify({generated:new Date().toISOString(),account:state.account,mode:state.supervision,history:state.history,events:state.events},null,2),'trading-bot-rapport.json','application/json');};

// Strategy settings are persisted by the authenticated MT5 worker, never shared in localStorage.
function fillStrategySettings(values){
 for(const [key,value] of Object.entries(values)){
  const el=$('setting-'+key);if(!el)continue;
  if(el.type==='checkbox')el.checked=!!value;
  else el.value=['risk','daily_loss','be_trigger'].includes(key)?Number((value*100).toFixed(4)):value;
 }
}
function renderStrategySettings(d){
 const fields=$('settings-fields');if(!fields)return;
 const supported=d.connected&&d.account?.demo===true&&!!d.strategy_settings;
 const key=d.account?String(d.account.login)+'@'+d.account.server:null;
 const signature=JSON.stringify(d.strategy_settings||{});
 if(supported&&(settingsAccount!==key||(!settingsDirty&&settingsSignature!==signature))){fillStrategySettings(d.strategy_settings);settingsAccount=key;settingsSignature=signature;settingsDirty=false;}
 fields.disabled=!supported||!!d.running||acting;
 $('settings-status').textContent=!d.connected?'Connecte ton compte pour charger ses réglages.':!supported?'Mise à jour du moteur du PC nécessaire pour personnaliser la stratégie.':d.running?'Bot en marche : arrête-le pour modifier les réglages.':settingsDirty?'Modifications non enregistrées. Enregistre avant de démarrer.':'Réglages de ce compte démo. Enregistre tes modifications avant de démarrer.';
 if(supported){$('risk').value=(d.strategy_settings.risk*100).toFixed(2);$('daily').value=(d.strategy_settings.daily_loss*100).toFixed(2);$('risk').readOnly=$('daily').readOnly=true;}
}
$('strategy-settings-form').onsubmit=async e=>{
 e.preventDefault();if(!state?.strategy_settings||state.running||acting)return;
 const config={};
 for(const el of $('strategy-settings-form').querySelectorAll('input[name]')){
  config[el.name]=el.type==='checkbox'?el.checked:Number(el.value);
  if(['risk','daily_loss','be_trigger'].includes(el.name))config[el.name]/=100;
 }
 if(config.risk>config.daily_loss){$('settings-status').textContent='Le risque par série ne peut pas dépasser la limite quotidienne.';return;}
 $('settings-fields').disabled=true;
 const result=await command({action:'settings',id:crypto.randomUUID(),config});
 if(result?.strategy_settings){fillStrategySettings(result.strategy_settings);settingsDirty=false;settingsSignature=JSON.stringify(result.strategy_settings);$('settings-status').textContent='Réglages enregistrés. Ils seront utilisés au prochain démarrage.';}
 else $('settings-status').textContent='Enregistrement non confirmé : consulte le message affiché et recharge les réglages avant de réessayer.';
 renderStrategySettingsFields();
};
function renderStrategySettingsFields(){if($('settings-fields'))$('settings-fields').disabled=!state?.connected||!state?.strategy_settings||!!state?.running||acting;}
$('strategy-settings-form').addEventListener('input',()=>{settingsDirty=true;$('settings-status').textContent='Modifications non enregistrées.';});
$('reset-settings').onclick=()=>{if(state?.strategy_settings_defaults){fillStrategySettings(state.strategy_settings_defaults);settingsDirty=true;$('settings-status').textContent='Valeurs par défaut préparées. Clique sur Enregistrer pour les appliquer au prochain démarrage.';}};
for(const link of document.querySelectorAll('.bottom-nav a'))link.addEventListener('click',()=>{
 const settings=link.getAttribute('href')==='#strategy-settings';
 $('strategy-settings').hidden=!settings;
 for(const el of document.querySelectorAll('.screen-grid,.account-status,#closed-history,#activity'))el.hidden=settings;
 for(const peer of document.querySelectorAll('.bottom-nav a'))peer.removeAttribute('aria-current');
 link.setAttribute('aria-current','page');
});
