"""Ben Forex Lab: demo-account-only MT5 connector. No real accounts accepted."""
from __future__ import annotations
import argparse, hashlib, hmac, json, math, os, secrets, threading, time
from collections import deque
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_FLOOR
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from strategy import Config, Engine, Bar
from trade_history import aggregate_deals, empty_history

MAGIC=26101603
STATE=Path(__file__).with_name('risk_state.json')
JOURNAL=Path(__file__).with_name('journal.jsonl')

class DemoBridge:
    def __init__(self,mt5,state=STATE,journal=JOURNAL):
        self.mt=mt5;self.state_path=Path(state);self.journal_path=Path(journal)
        self.lock=threading.RLock();self.running=False;self.engine=None;self.symbol='EURUSD'
        self.cfg=Config();self.events=deque(maxlen=100);self.pin=None;self.last_error=''
        self.last_seen=0;self.last_quote=0;self.commands=deque(maxlen=200)
        self.supervision='browser';self.history=empty_history();self.history_at=0;self.history_account=None
        self.risk=json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        self.last_signal=self.risk.get('last_signal')
        self.equity_path=self.state_path.with_name(self.state_path.stem+'_equity.json')
        self.equity_account=None;self.equity_points=deque(maxlen=2880);self.equity_saved=0
        try:
            saved=json.loads(self.equity_path.read_text())
            pts=saved.get('points',[])
            if all(isinstance(p,dict) and all(math.isfinite(float(p[k])) for k in ('time','equity')) for p in pts):
                self.equity_account=saved.get('account');self.equity_points.extend(pts[-2880:])
        except (OSError,ValueError,KeyError,TypeError):pass
    def log(self,event,**data):
        row=dict(time=time.time(),event=event,**data);self.events.append(row)
        with self.journal_path.open('a',encoding='utf8') as f:f.write(json.dumps(row,ensure_ascii=False)+'\n')
    def persist(self):
        tmp=self.state_path.with_suffix('.tmp')
        with tmp.open('w') as f:json.dump(self.risk,f);f.flush();os.fsync(f.fileno())
        os.replace(tmp,self.state_path)
    def account(self):
        a=self.mt.account_info();terminal=self.mt.terminal_info()
        if a is None or terminal is None or not terminal.connected:raise ValueError('Terminal MT5 deconnecte.')
        if a.trade_mode!=self.mt.ACCOUNT_TRADE_MODE_DEMO:raise ValueError('Compte REEL ou concours refuse. Compte DEMO obligatoire.')
        if not all(math.isfinite(float(getattr(a,k))) for k in ('equity','balance','margin_free')):raise ValueError('Valeurs de compte invalides.')
        if a.currency!='USD':raise ValueError('V1 : compte de demonstration en USD requis.')
        if self.pin and (a.login,a.server)!=self.pin:raise ValueError('Compte change : bot mis en pause. Reconnecter le compte initial.')
        return a
    def guard_trade(self):
        a=self.account();t=self.mt.terminal_info()
        if not a.trade_allowed or not a.trade_expert or not t.trade_allowed or getattr(t,'tradeapi_disabled',False):
            raise ValueError('Autoriser Algo Trading et le trading via API Python dans MT5.')
        if a.equity<=0:raise ValueError('Capital de demonstration insuffisant.')
        return a
    def day_check(self,a):
        day=datetime.now(timezone.utc).date().isoformat();key=f'{a.login}@{a.server}'
        before=json.dumps(self.risk,sort_keys=True)
        states=self.risk.setdefault('accounts',{})
        if key not in states:
            states[key]={k:self.risk[k] for k in ('day','baseline','halted') if k in self.risk} if self.risk.get('account')==key else {}
        record=states[key]
        if record.get('day')!=day:
            record.update(day=day,baseline=a.equity,halted=False)
        self.risk.update(day=record['day'],account=key,baseline=record['baseline'],halted=record.get('halted',False))
        if a.equity<=record['baseline']*(1-self.cfg.daily_loss)+1e-8 and not record.get('halted'):
            record['halted']=True;self.risk['halted']=True;self.log('DAILY_HALT',equity=a.equity)
        if json.dumps(self.risk,sort_keys=True)!=before:self.persist()
        return bool(record.get('halted'))
    def record_equity(self,a):
        identity=f'{a.login}@{a.server}';now=time.time()
        if identity!=self.equity_account:
            self.equity_account=identity;self.equity_points.clear();self.equity_saved=0
        if self.equity_points and now-self.equity_points[-1]['time']<30:return
        self.equity_points.append(dict(time=now,equity=a.equity))
        if now-self.equity_saved>=60:
            temp=self.equity_path.with_suffix('.tmp')
            with temp.open('w') as f:json.dump(dict(account=identity,points=list(self.equity_points)),f,allow_nan=False);f.flush();os.fsync(f.fileno())
            os.replace(temp,self.equity_path);self.equity_saved=now
    def refresh_history(self,a,positions):
        identity=(a.login,a.server)
        if identity==self.history_account and time.time()-self.history_at<30:return
        self.history_account=identity;self.history_at=time.time()
        if not hasattr(self.mt,'history_deals_get'):
            self.history=empty_history('unavailable','Historique non disponible sur cette source.');return
        try:
            now=datetime.now(timezone.utc);start=now-timedelta(days=90)
            deals=self.mt.history_deals_get(start,now)
            if deals is None:raise ValueError('Lecture de l historique MT5 indisponible.')
            if len(deals)>100000:raise ValueError('Historique trop volumineux (100000 executions maximum).')
            # Recover complete entries for old positions that closed in the window.
            missing={d.position_id for d in deals if d.magic==MAGIC and d.entry in (1,3)}-{d.position_id for d in deals if d.entry==0}
            all_deals=list(deals)
            for pid in list(missing)[:20]:
                older=self.mt.history_deals_get(position=int(pid))
                if older:all_deals.extend(older)
            self.history=aggregate_deals(all_deals,MAGIC,[getattr(p,'identifier',p.ticket) for p in positions],start.timestamp())
            self.history.update(updated=time.time(),truncated=max(0,len(self.history['trades'])-500))
            self.history['trades']=self.history['trades'][-500:]
        except Exception as ex:self.history=empty_history('unavailable',str(ex))
    def candles(self):
        self.account()
        if not self.mt.symbol_select(self.symbol,True):raise ValueError('Symbole indisponible.')
        info=self.mt.symbol_info(self.symbol)
        if info is None or info.currency_base!='EUR' or info.currency_profit!='USD':raise ValueError('EURUSD uniquement.')
        rates=self.mt.copy_rates_from_pos(self.symbol,self.mt.TIMEFRAME_M3,1,10000)
        if rates is None or len(rates)<50:raise ValueError('Historique M3 insuffisant.')
        bars=[]
        for r in sorted(rates,key=lambda r:int(r['time'])):
            b=Bar(int(r['time']),float(r['open']),float(r['high']),float(r['low']),float(r['close']),float(r['spread'])*info.point)
            b.validate()
            if b.time+180<=time.time():bars.append(dict(time=b.time,open=b.open,high=b.high,low=b.low,close=b.close,spread=b.spread))
        return dict(symbol=self.symbol,timeframe='M3',bars=bars,source='MT5',closed_only=True)
    def snapshot(self):
        self.last_seen=time.time()
        try:
            a=self.account();positions=self.mt.positions_get()
            if positions is None:raise ValueError('Lecture des positions indisponible.')
            self.record_equity(a);self.refresh_history(a,positions)
            tick=self.mt.symbol_info_tick(self.symbol)
            account=dict(login=str(a.login),server=a.server,balance=a.balance,equity=a.equity,profit=a.profit,
                         margin=a.margin,free_margin=a.margin_free,currency=a.currency,demo=True)
            ps=[dict(ticket=str(p.ticket),symbol=p.symbol,side='BUY' if p.type==0 else 'SELL',
                     volume=p.volume,entry=p.price_open,current=p.price_current,sl=p.sl,tp=p.tp,
                     profit=p.profit,owned=p.magic==MAGIC) for p in positions]
            return dict(connected=True,running=self.running,account=account,positions=ps,symbol=self.symbol,
                        quote=dict(bid=tick.bid,ask=tick.ask,time=tick.time) if tick else None,
                        events=list(self.events),error=self.last_error,halted=self.risk.get('halted',False),history=self.history,
                        supervision=self.supervision,connector_version='4.0',equity_curve=list(self.equity_points),
                        time=time.time(),strategy='CHoCH / retest / rejet M3',risk=self.cfg.risk,daily_loss=self.cfg.daily_loss,rr=self.cfg.rr)
        except Exception as ex:
            self.running=False;self.last_error=str(ex)
            return dict(connected=False,running=False,error=str(ex),events=list(self.events),time=time.time())
    def command(self,d):
        ident=d.get('id');action=d.get('action')
        if not isinstance(ident,str) or len(ident)>80 or len(ident)<10:raise ValueError('Identifiant de commande requis.')
        if ident in self.commands:return self.snapshot()
        if action=='stop':
            self.running=False
            if self.engine:self.engine.cancel(time.time(),'manual_stop')
            self.log('STOP',detail='Nouvelles entrees suspendues. SL/TP existants conserves.')
        elif action=='start':
            a=self.guard_trade()
            if self.running:raise ValueError('Bot deja actif. Arreter avant de modifier les reglages.')
            supervision=d.get('supervision','browser')
            if supervision not in ('browser','autonomous'):raise ValueError('Mode de supervision invalide.')
            symbol=str(d.get('symbol','EURUSD'))
            if not 1<=len(symbol)<=40:raise ValueError('Symbole invalide.')
            if not self.mt.symbol_select(symbol,True):raise ValueError('Symbole introuvable dans MT5.')
            info=self.mt.symbol_info(symbol)
            if info is None or info.currency_base!='EUR' or info.currency_profit!='USD':raise ValueError('EUR/USD uniquement dans cette version.')
            cfg=d.get('config',{})
            if set(cfg)-{'risk','daily_loss','rr'}:raise ValueError('Parametres inconnus.')
            self.cfg=Config(**cfg)
            if self.cfg.risk>.01 or self.cfg.daily_loss>.03:raise ValueError('Tests DEMO : risque max 1 %, limite quotidienne max 3 %.')
            self.symbol=symbol;self.pin=(a.login,a.server)
            if self.day_check(a):raise ValueError('Limite quotidienne atteinte. Reprise au prochain jour UTC.')
            tick=self.mt.symbol_info_tick(symbol)
            if tick is None or time.time()-tick.time>30:raise ValueError('Cotation perimee : marche ferme ou connexion absente.')
            self.engine=Engine(self.cfg)
            rates=self.mt.copy_rates_from_pos(symbol,self.mt.TIMEFRAME_M3,1,300)
            if rates is None or len(rates)<50:raise ValueError('Historique M3 insuffisant (50 bougies minimum).')
            for r in sorted(rates,key=lambda r:int(r['time'])):
                self.engine.feed(Bar(int(r['time']),float(r['open']),float(r['high']),float(r['low']),float(r['close']),float(r['spread'])*info.point),now=time.time(),historical=False)
            self.engine.cancel(time.time(),'startup')
            self.event_cursor=len(self.engine.events)
            self.supervision=supervision
            self.running=True;self.last_seen=time.time();self.last_error=''
            self.risk['last_config']=dict(risk=self.cfg.risk,daily_loss=self.cfg.daily_loss,rr=self.cfg.rr,supervision=supervision)
            self.persist()
            self.log('START',account=str(a.login),symbol=symbol,detail='Mode autonome' if supervision=='autonomous' else 'Mode supervise (tableau de bord actif)')
        else:raise ValueError('Commande inconnue.')
        self.commands.append(ident)
        return self.snapshot()
    def submit(self,s,tick,info):
        a=self.guard_trade()
        if not all(math.isfinite(float(x)) for x in (tick.bid,tick.ask,tick.time)) or tick.bid<=0 or tick.ask<tick.bid or time.time()-tick.time>30 or tick.time>time.time()+5:raise ValueError('Cotation invalide ou perimee.')
        if not all(math.isfinite(float(getattr(info,k))) and getattr(info,k)>0 for k in ('point','volume_step','volume_min','volume_max')):raise ValueError('Metadonnees de volume ou de prix invalides.')
        if not math.isfinite(info.trade_tick_size) or info.trade_tick_size<0:raise ValueError('Taille de tick invalide.')
        if self.day_check(a):return
        positions=self.mt.positions_get();orders=self.mt.orders_get()
        if positions is None or orders is None:raise ValueError('Etat des ordres/positions indisponible.')
        if positions or orders:self.log('REJECT',detail='Une position ou un ordre existe deja sur ce compte.');return
        if s['id']==self.last_signal:return
        now=time.time()
        if tick.time<s['ready'] or now-s['ready']>30:self.log('REJECT',detail='Signal perime ou cotation anterieure au signal.');return
        side=s['side'];kind=self.mt.ORDER_TYPE_BUY if side==1 else self.mt.ORDER_TYPE_SELL
        step=info.trade_tick_size or info.point
        entry=tick.ask if side==1 else tick.bid
        sl=round((math.floor(s['stop']/step) if side==1 else math.ceil(s['stop']/step))*step,info.digits)
        distance=side*(entry-sl)
        if distance<=0:self.log('REJECT',detail='Stop invalide apres variation du prix.');return
        tp=round((math.ceil((entry+side*self.cfg.rr*distance)/step) if side==1 else math.floor((entry+side*self.cfg.rr*distance)/step))*step,info.digits)
        minimum=info.trade_stops_level*info.point
        if (side==1 and (tick.bid-sl<minimum or tp-tick.bid<minimum)) or (side==-1 and (sl-tick.ask<minimum or tick.ask-tp<minimum)):
            self.log('REJECT',detail='Distance minimale du courtier non respectee.');return
        worst_sl=sl-side*(10*info.point+self.cfg.slippage)
        loss=self.mt.order_calc_profit(kind,self.symbol,1.0,entry,worst_sl)
        if loss is None or loss>=0:raise ValueError('Calcul du risque MT5 impossible.')
        per_lot=abs(loss)+2*self.cfg.commission
        budget=min(a.equity*self.cfg.risk,a.equity-self.risk['baseline']*(1-self.cfg.daily_loss))
        margin=self.mt.order_calc_margin(kind,self.symbol,1.0,entry)
        if margin is None or margin<=0:raise ValueError('Calcul de marge MT5 impossible.')
        raw=min(max(0,budget)/per_lot,a.margin_free*.90/margin,info.volume_max)
        vol=float((Decimal(str(raw))/Decimal(str(info.volume_step))).to_integral_value(rounding=ROUND_FLOOR)*Decimal(str(info.volume_step)))
        if vol<info.volume_min:self.log('REJECT',detail='Lot minimal superieur au budget de risque.');return
        fill=self.mt.ORDER_FILLING_FOK if info.filling_mode&1 else self.mt.ORDER_FILLING_IOC if info.filling_mode&2 else self.mt.ORDER_FILLING_RETURN
        request=dict(action=self.mt.TRADE_ACTION_DEAL,symbol=self.symbol,volume=vol,type=kind,price=entry,
                     sl=sl,tp=tp,deviation=10,magic=MAGIC,comment='BenLab '+hashlib.sha256(s['id'].encode()).hexdigest()[:10],
                     type_time=self.mt.ORDER_TIME_GTC,type_filling=fill)
        checked=self.mt.order_check(request)
        if checked is None or checked.retcode!=0:
            self.log('REJECT',detail='Courtier : '+(checked.comment if checked else 'order_check indisponible'));return
        self.guard_trade() # re-check immediately before any broker mutation
        # Record before send; never blindly retry after uncertain response or restart.
        self.last_signal=s['id'];self.risk['last_signal']=self.last_signal;self.persist()
        result=self.mt.order_send(request)
        if result is None or result.retcode not in (self.mt.TRADE_RETCODE_DONE,self.mt.TRADE_RETCODE_DONE_PARTIAL):
            self.running=False;self.log('ORDER_UNCERTAIN',detail='Bot arrete : verifier MT5. Aucun renvoi automatique.',retcode=getattr(result,'retcode',None));return
        self.log('ENTRY',side='BUY' if side==1 else 'SELL',volume=vol,price=result.price,stop=sl,target=tp)
        # Attached protections remain even if exact RR adjustment fails.
        ps=self.mt.positions_get(symbol=self.symbol)
        own=[p for p in (ps or []) if p.magic==MAGIC]
        if len(own)==1:
            p=own[0];target=p.price_open+side*self.cfg.rr*side*(p.price_open-sl)
            target=round((math.ceil(target/step) if side==1 else math.floor(target/step))*step,info.digits)
            self.guard_trade()
            adjusted=self.mt.order_send(dict(action=self.mt.TRADE_ACTION_SLTP,position=p.ticket,symbol=self.symbol,sl=sl,tp=target,magic=MAGIC))
            if adjusted is None or adjusted.retcode!=self.mt.TRADE_RETCODE_DONE:self.log('WARNING',detail='Cible initiale conservee : ajustement au prix execute refuse.')
    def step(self):
        if not self.running:return
        if self.supervision=='browser' and time.time()-self.last_seen>25:
            self.running=False;self.log('PAUSE',detail='Tableau de bord inactif depuis 25 s.');return
        try:
            a=self.account()
            self.record_equity(a)
            if self.day_check(a):self.running=False;return
            tick=self.mt.symbol_info_tick(self.symbol);info=self.mt.symbol_info(self.symbol)
            if tick is None or info is None or time.time()-tick.time>30 or tick.time>time.time()+5:raise ValueError('Cotation perimee ou future.')
            positions=self.mt.positions_get();orders=self.mt.orders_get()
            if positions is None or orders is None:raise ValueError('Positions/ordres indisponibles.')
            self.engine.position=True if positions or orders else None
            rates=self.mt.copy_rates_from_pos(self.symbol,self.mt.TIMEFRAME_M3,1,50)
            if rates is None or len(rates)==0:raise ValueError('Bougies M3 indisponibles.')
            if time.time()-(int(rates[-1]['time'])+180)>180:raise ValueError('Historique M3 perime.')
            for r in sorted(rates,key=lambda r:int(r['time'])):
                ts=int(r['time'])
                if ts<=self.engine.bars[-1]['time']:continue
                self.engine.feed(Bar(ts,float(r['open']),float(r['high']),float(r['low']),float(r['close']),float(r['spread'])*info.point),now=time.time(),historical=False)
            for event in self.engine.events[getattr(self,'event_cursor',0):]:
                self.log(event['event'],detail=event.get('reason','Signal de strategie'),**{k:v for k,v in event.items() if k in ('side','level')})
            self.engine.events.clear();self.event_cursor=0
            self.engine.bars=self.engine.bars[-1000:];self.engine.used=self.engine.used[-1000:]
            if self.engine.pending:
                s=self.engine.pending
                if tick.time>=s['ready']:
                    self.engine.pending=None;self.submit(s,tick,info)
        except Exception as ex:
            self.running=False;self.last_error=str(ex);self.log('ERROR',detail=str(ex))


def serve(mt5,token,port=8765):
    bridge=DemoBridge(mt5)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,status,payload):
            data=json.dumps(payload,ensure_ascii=False,allow_nan=False).encode()
            self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
        def auth(self):return hmac.compare_digest(self.headers.get('Authorization',''),'Bearer '+token)
        def do_GET(self):
            if not self.auth():return self.reply(401,{'error':'Authentification requise'})
            if self.path not in ('/status','/candles'):return self.reply(404,{'error':'Route inconnue'})
            try:
                with bridge.lock:self.reply(200,bridge.snapshot() if self.path=='/status' else bridge.candles())
            except (ValueError,TypeError) as ex:self.reply(400,{'error':str(ex)})
        def do_POST(self):
            if not self.auth():return self.reply(401,{'error':'Authentification requise'})
            if self.path!='/command':return self.reply(404,{'error':'Route inconnue'})
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=4096:raise ValueError('Corps invalide')
                d=json.loads(self.rfile.read(n))
                with bridge.lock:self.reply(200,bridge.command(d))
            except (ValueError,TypeError,KeyError) as ex:self.reply(400,{'error':str(ex)})
    def loop():
        while True:
            try:
                with bridge.lock:bridge.step()
            except Exception as ex:
                with bridge.lock:
                    bridge.running=False;bridge.last_error='Moteur arrete : '+str(ex)
            time.sleep(.5)
    threading.Thread(target=loop,daemon=True).start()
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print('Trading Bot v4 - DEMO local actif. Aucun ordre avant Demarrer sur le site.',flush=True)
    server.serve_forever()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--port',type=int,default=8765);a=p.parse_args()
    import MetaTrader5 as mt5
    if not mt5.initialize():raise SystemExit('Ouvrir MT5 puis relancer le connecteur.')
    token=os.environ.get('BEN_BRIDGE_TOKEN') or secrets.token_urlsafe(32)
    print('Cle de liaison (a saisir sur ton site prive) :',token,flush=True)
    try:serve(mt5,token,a.port)
    finally:mt5.shutdown()
