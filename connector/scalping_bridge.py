"""Experimental XAUUSD M1 strategy, restricted to USD demo hedging accounts.

A real broker run has NOT been validated. Stops remain broker-side; this module
fails closed on uncertain orders or missing data. Price settings are experimental.
"""
import hashlib
import math
import time
from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_FLOOR
from bridge import DemoBridge
from structure_m1 import Bar, StructureM1
from liquidity_signal import signal
from trade_history import aggregate_deals, empty_history
from scalping_settings import validate_settings,session_open

MAGIC_SCALP=26102701

class ScalpingBridge(DemoBridge):
    def __init__(self, mt5, state, journal):
        super().__init__(mt5, state, journal, instrument='XAUUSD')
        a=self.account()
        saved=self.risk.get('accounts',{}).get(f'{a.login}@{a.server}',{}).get('scalp_settings',{})
        self.options=validate_settings(saved)
        self.apply_settings()
        self.structure=None
        self.previous_bid=None
        self.quote_id=None
        self.resume_after=0
        self.last_structure=None
        self.last_seen_bar=None
        self.pending_closure=False
        self.be_tickets=set()
        self.had_owned=False

    def apply_settings(self):
        self.cfg=self.live_config({k:self.options[k] for k in ('risk','daily_loss')})
        self.penetration=self.options['penetration']
        self.stop_distance=self.options['stop_distance']
        self.max_spread=self.options['max_spread']

    def hedge_account(self):
        a=self.guard_trade()
        mode=getattr(a,'margin_mode',None)
        allowed=getattr(self.mt,'ACCOUNT_MARGIN_MODE_RETAIL_HEDGING',None)
        if allowed is None or mode != allowed:
            raise ValueError('Un compte MT5 démo en mode hedging est requis pour trois positions.')
        return a

    def _positions_orders(self):
        ps=self.mt.positions_get(); orders=self.mt.orders_get()
        if ps is None or orders is None: raise ValueError('Positions ou ordres indisponibles.')
        return list(ps),list(orders)

    def _quote(self):
        t=self.mt.symbol_info_tick(self.symbol)
        if t is None:
            raise ValueError('Aucun prix renvoyé par cette instance MT5 pour '+self.symbol+'.')
        try:
            valid=all(math.isfinite(float(v)) for v in (t.bid,t.ask,t.time)) and t.bid>0 and t.ask>=t.bid and t.time>0
        except (ValueError,TypeError,AttributeError):
            valid=False
        if not valid:
            raise ValueError('Prix Bid/Ask ou horodatage invalide pour '+self.symbol+'.')
        now=time.time();age=now-t.time
        if age>10 or age < -5:
            tick_utc=datetime.fromtimestamp(t.time,timezone.utc).strftime('%H:%M:%S')
            pc_utc=datetime.fromtimestamp(now,timezone.utc).strftime('%H:%M:%S')
            reason=('Prix ancien de '+str(round(age,1))+' s (limite 10 s)') if age>10 else ('Prix daté dans le futur de '+str(round(-age,1))+' s (tolérance 5 s)')
            raise ValueError(reason+' pour '+self.symbol+'. Prix UTC '+tick_utc+' ; PC UTC '+pc_utc+'. Vérifier flux et horloge de cette instance.')
        return t

    def _send(self, request, label):
        check=self.mt.order_check(request)
        if check is None or check.retcode != 0:
            raise ValueError(label+': contrôle courtier refusé.')
        self.hedge_account()
        result=self.mt.order_send(request)
        if result is None or result.retcode != self.mt.TRADE_RETCODE_DONE:
            # Partial fills and unknown outcomes must be reconciled manually.
            raise ValueError(label+': résultat incertain ou incomplet ; vérifier MT5 avant reprise.')
        return result

    def command(self,d):
        ident=d.get('id'); action=d.get('action')
        if not isinstance(ident,str) or not 10<=len(ident)<=80: raise ValueError('Identifiant de commande requis.')
        if ident in self.commands: return self.snapshot()
        if action=='settings':
            if self.running:raise ValueError('Arrête le bot avant de modifier les réglages.')
            a=self.account()
            options=validate_settings(d.get('config',{}))
            self.day_check(a)
            self.risk['accounts'][f'{a.login}@{a.server}']['scalp_settings']=options
            self.persist()
            self.options=options;self.apply_settings()
            self.log('SETTINGS',detail='Réglages enregistrés pour le prochain démarrage.')
        elif action=='stop':
            self.running=False
            self.log('STOP',detail='Entrées et gestion actives suspendues ; SL/TP restent chez le courtier.')
        elif action=='start':
            if self.running: raise ValueError('Bot déjà actif.')
            a=self.hedge_account()
            symbol=str(d.get('symbol','XAUUSD'))
            if not 1<=len(symbol)<=40 or not self.mt.symbol_select(symbol,True): raise ValueError('Symbole indisponible.')
            info=self.symbol_details(symbol)
            self.symbol=symbol; self.pin=(a.login,a.server)
            ps,orders=self._positions_orders()
            if ps or orders: raise ValueError('Fermer ou vérifier les positions et ordres existants avant le démarrage.')
            if self.day_check(a): raise ValueError('Limite de perte quotidienne atteinte.')
            self._quote()
            supervision=d.get('supervision','browser')
            if supervision not in ('browser','autonomous'): raise ValueError('Supervision invalide.')
            rates=self.mt.copy_rates_from_pos(symbol,self.mt.TIMEFRAME_M1,1,300)
            if rates is None or len(rates)<50: raise ValueError('Historique M1 insuffisant.')
            engine=StructureM1(self.options['pivot'])
            for r in sorted(rates,key=lambda x:int(x['time'])):
                ts=int(r['time'])
                if ts+60>time.time(): continue
                state=engine.feed(Bar(ts,float(r['open']),float(r['high']),float(r['low']),float(r['close'])))
            if not engine.bars or time.time()-(engine.bars[-1].time+60)>120: raise ValueError('Historique M1 périmé.')
            self.structure=engine;self.last_structure=state;self.last_seen_bar=engine.bars[-1].time
            self.previous_bid=None;self.quote_id=None;self.resume_after=0;self.be_tickets.clear();self.had_owned=False
            self.supervision=supervision;self.running=True;self.last_seen=time.time();self.last_error=''
            self.analysis_warmup=len(engine.bars);self.analysis_bars=0;self.analysis_at=None;self.cycle_at=None
            self.log('START',symbol=symbol,detail='Scalping expérimental M1, démo uniquement')
        else: raise ValueError('Commande inconnue.')
        self.commands.append(ident)
        return self.snapshot()

    def submit_scalp(self, side, stop, target, tick, info, signal_id):
        a=self.hedge_account()
        if self.day_check(a): return
        ps,orders=self._positions_orders()
        if ps or orders: return
        if self.risk.get('scalp_signal')==signal_id: return
        if any(not math.isfinite(float(getattr(info,k))) or getattr(info,k)<=0 for k in ('point','volume_step','volume_min','volume_max')):
            raise ValueError('Spécifications du symbole invalides.')
        sideint=1 if side=='BUY' else -1
        kind=self.mt.ORDER_TYPE_BUY if sideint==1 else self.mt.ORDER_TYPE_SELL
        point=float(info.trade_tick_size or info.point)
        sl=round((math.floor(stop/point) if sideint==1 else math.ceil(stop/point))*point,info.digits)
        tp=round((math.floor(target/point) if sideint==1 else math.ceil(target/point))*point,info.digits)
        entry=tick.ask if sideint==1 else tick.bid
        minimum=info.trade_stops_level*info.point
        if (sideint==1 and not (sl < tick.bid-minimum and tp > tick.bid+minimum and tp > entry)) or (sideint==-1 and not (sl > tick.ask+minimum and tp < tick.ask-minimum and tp < entry)):
            self.log('REJECT',detail='Stop ou objectif incompatible avec les prix ou le courtier.');return
        loss=self.mt.order_calc_profit(kind,self.symbol,1.0,entry+sideint*(self.cfg.slippage+10*info.point),sl-sideint*self.cfg.slippage)
        margin=self.mt.order_calc_margin(kind,self.symbol,1.0,entry)
        if loss is None or margin is None or not math.isfinite(loss) or not math.isfinite(margin) or loss>=0 or margin<=0:
            raise ValueError('Calcul de risque ou de marge impossible.')
        cost=abs(loss)+2*self.cfg.commission
        budget=min(a.equity*self.cfg.risk,a.equity-self.risk['baseline']*(1-self.cfg.daily_loss))
        count=self.options['positions']
        raw=min(max(0,budget)/(count*cost),a.margin_free*.90/(count*margin),info.volume_max)
        vol=float((Decimal(str(raw))/Decimal(str(info.volume_step))).to_integral_value(rounding=ROUND_FLOOR)*Decimal(str(info.volume_step)))
        if vol<info.volume_min:
            self.log('REJECT',detail='Lot minimal trop élevé pour la série et le budget de risque.');return
        fill=self.mt.ORDER_FILLING_FOK if info.filling_mode&1 else self.mt.ORDER_FILLING_IOC if info.filling_mode&2 else self.mt.ORDER_FILLING_RETURN
        self.risk['scalp_signal']=signal_id;self.persist()
        for i in range(count):
            # Re-check before every send; no automatic resend on uncertain outcome.
            a=self.hedge_account()
            current, pending=self._positions_orders()
            if pending or any(p.magic != MAGIC_SCALP or p.symbol != self.symbol for p in current) or len(current)>i:
                raise ValueError('Positions inattendues pendant la série ; contrôle manuel requis.')
            if self.day_check(a): raise ValueError('Limite quotidienne atteinte pendant la série.')
            t=self._quote()
            if abs((t.ask if sideint==1 else t.bid)-entry)>self.cfg.slippage:
                raise ValueError('Prix trop éloigné pendant la série ; vérifiez les positions ouvertes.')
            req=dict(action=self.mt.TRADE_ACTION_DEAL,symbol=self.symbol,volume=vol,type=kind,
                     price=t.ask if sideint==1 else t.bid,sl=sl,tp=tp,deviation=10,magic=MAGIC_SCALP,
                     comment='Scalp '+hashlib.sha256((signal_id+str(i)).encode()).hexdigest()[:10],
                     type_time=self.mt.ORDER_TIME_GTC,type_filling=fill)
            self._send(req,'Ouverture')
            self.log('ENTRY',side=side,volume=vol,stop=sl,target=tp)

    def close_owned(self,positions,tick,info):
        for p in positions:
            if p.magic!=MAGIC_SCALP or p.symbol!=self.symbol: continue
            self.hedge_account()
            tick=self._quote()
            typ=self.mt.ORDER_TYPE_SELL if p.type==self.mt.ORDER_TYPE_BUY else self.mt.ORDER_TYPE_BUY
            fill=self.mt.ORDER_FILLING_FOK if info.filling_mode&1 else self.mt.ORDER_FILLING_IOC if info.filling_mode&2 else self.mt.ORDER_FILLING_RETURN
            req=dict(action=self.mt.TRADE_ACTION_DEAL,position=p.ticket,symbol=p.symbol,volume=p.volume,type=typ,
                     price=tick.bid if typ==self.mt.ORDER_TYPE_SELL else tick.ask,deviation=10,magic=MAGIC_SCALP,
                     comment='Scalp exit',type_time=self.mt.ORDER_TIME_GTC,type_filling=fill)
            self._send(req,'Fermeture')
            self.log('EXIT',ticket=str(p.ticket),detail='CHoCH ou limite quotidienne')
        self.resume_after=time.time()+self.options['cooldown']

    def manage_break_even(self,positions,tick,info):
        step=float(info.trade_tick_size or info.point)
        for p in positions:
            if p.magic!=MAGIC_SCALP or p.symbol!=self.symbol or p.ticket in self.be_tickets: continue
            if not p.sl or not p.tp: raise ValueError('Une position du bot n’a pas de SL/TP : contrôle manuel requis.')
            if not self.options['break_even']:continue
            buy=p.type==self.mt.ORDER_TYPE_BUY
            price=tick.bid if buy else tick.ask
            if (buy and price < (p.price_open+(p.tp-p.price_open)*self.options['be_trigger'])) or (not buy and price > (p.price_open+(p.tp-p.price_open)*self.options['be_trigger'])): continue
            # Opening price only: commission and slippage may still produce a loss.
            sl=round((math.ceil(p.price_open/step) if buy else math.floor(p.price_open/step))*step,info.digits)
            if (buy and sl<=p.sl) or (not buy and sl>=p.sl): self.be_tickets.add(p.ticket);continue
            minimum=max(info.trade_stops_level,getattr(info,'trade_freeze_level',0))*info.point
            if (buy and tick.bid-sl<=minimum) or (not buy and sl-tick.ask<=minimum): continue
            self.hedge_account()
            result=self.mt.order_send(dict(action=self.mt.TRADE_ACTION_SLTP,position=p.ticket,symbol=self.symbol,sl=sl,tp=p.tp,magic=MAGIC_SCALP))
            if result is None or result.retcode != self.mt.TRADE_RETCODE_DONE:
                raise ValueError('Modification du stop incertaine ; vérifier MT5.')
            self.be_tickets.add(p.ticket);self.log('BREAK_EVEN',ticket=str(p.ticket))

    def step(self):
        if not self.running:return
        if self.supervision=='browser' and time.time()-self.last_seen>25:
            self.running=False;self.log('PAUSE',detail='Tableau de bord inactif.');return
        try:
            a=self.hedge_account();self.record_equity(a)
            tick=self._quote(); info=self.symbol_details(self.symbol)
            ps,orders=self._positions_orders()
            own=[p for p in ps if p.magic==MAGIC_SCALP and p.symbol==self.symbol]
            if self.day_check(a):
                self.close_owned(own,tick,info);self.running=False;return
            rates=self.mt.copy_rates_from_pos(self.symbol,self.mt.TIMEFRAME_M1,1,50)
            if rates is None or len(rates)==0: raise ValueError('Bougies M1 indisponibles.')
            choch=False
            for r in sorted(rates,key=lambda x:int(x['time'])):
                ts=int(r['time'])
                if ts<=self.last_seen_bar or ts+60>time.time():continue
                if ts!=self.last_seen_bar+60:
                    self.previous_bid=None
                    raise ValueError('Historique M1 interrompu ; reprise manuelle requise.')
                self.last_structure=self.structure.feed(Bar(ts,float(r['open']),float(r['high']),float(r['low']),float(r['close'])))
                self.last_seen_bar=ts;self.previous_bid=None;self.analysis_bars+=1;self.analysis_at=time.time()
                if self.last_structure['event'] in ('choch_up','choch_down'):choch=True
            if time.time()-(self.last_seen_bar+60)>120:raise ValueError('Historique M1 périmé.')
            self.cycle_at=time.time()
            if choch and own:
                self.close_owned(own,tick,info);return
            self.manage_break_even(own,tick,info)
            if own: self.had_owned=True
            elif self.had_owned:
                self.had_owned=False;self.resume_after=time.time()+self.options['cooldown'];self.be_tickets.clear();self.previous_bid=None
            if own or ps or orders:
                self.previous_bid=tick.bid;return
            tick_id=(getattr(tick,'time_msc',0),tick.time,tick.bid,tick.ask)
            if tick_id==self.quote_id:return
            self.quote_id=tick_id
            prev=self.previous_bid;self.previous_bid=tick.bid
            hour=datetime.now(timezone.utc).hour
            if prev is None or time.time()<self.resume_after or not session_open(hour,self.options) or tick.ask-tick.bid>self.max_spread:return
            s=self.last_structure or {}; low=s.get('support'); high=s.get('resistance')
            if low is None or high is None or low>=high:return
            event=signal(prev,tick.bid,low,high,s['trend'],self.penetration,self.stop_distance)
            if event:
                signal_id=f"{self.symbol}:{self.last_seen_bar}:{event.side}:{event.level}:{tick_id}"
                self.submit_scalp(event.side,event.stop,event.target,tick,info,signal_id)
        except Exception as ex:
            self.running=False;self.last_error=str(ex);self.log('ERROR',detail=str(ex))

    def candles(self):
        self.account()
        if not self.mt.symbol_select(self.symbol,True): raise ValueError('Symbole indisponible.')
        info=self.symbol_details(self.symbol)
        rates=self.mt.copy_rates_from_pos(self.symbol,self.mt.TIMEFRAME_M1,1,10000)
        if rates is None or len(rates)<50: raise ValueError('Historique M1 insuffisant.')
        bars=[]
        for r in sorted(rates,key=lambda x:int(x['time'])):
            t=int(r['time'])
            if t+60<=time.time():
                bars.append(dict(time=t,open=float(r['open']),high=float(r['high']),low=float(r['low']),close=float(r['close']),spread=float(r['spread'])*info.point))
        return dict(symbol=self.symbol,timeframe='M1',bars=bars,source='MT5',closed_only=True)

    def refresh_history(self,a,positions):
        identity=(a.login,a.server)
        if identity==self.history_account and time.time()-self.history_at<30: return
        self.history_account=identity;self.history_at=time.time()
        if not hasattr(self.mt,'history_deals_get'):
            self.history=empty_history('unavailable','Historique indisponible.');return
        try:
            now=datetime.now(timezone.utc);start=now-timedelta(days=90)
            deals=self.mt.history_deals_get(start,now)
            if deals is None or len(deals)>100000: raise ValueError('Historique indisponible ou trop volumineux.')
            missing={d.position_id for d in deals if d.magic==MAGIC_SCALP and d.entry in (1,3)}-{d.position_id for d in deals if d.entry==0}
            all_deals=list(deals)
            for pid in list(missing)[:20]:
                older=self.mt.history_deals_get(position=int(pid))
                if older:all_deals.extend(older)
            self.history=aggregate_deals(all_deals,MAGIC_SCALP,[getattr(p,'identifier',p.ticket) for p in positions],start.timestamp())
            self.history.update(updated=time.time(),truncated=max(0,len(self.history['trades'])-500))
            self.history['trades']=self.history['trades'][-500:]
        except Exception as ex:self.history=empty_history('unavailable',str(ex))

    def diagnostics(self):
        s=self.last_structure or {}
        return dict(timeframe='M1',last_bar_open=self.last_seen_bar,
                    last_bar_close=self.last_seen_bar+60 if self.last_seen_bar is not None else None,
                    trend={'up':1,'down':-1}.get(s.get('trend'),0),
                    stage='Scalping expérimental : recherche de franchissement' if self.running else 'Moteur arrêté',
                    swing_high=[0,s['resistance']] if s.get('resistance') else None,
                    swing_low=[0,s['support']] if s.get('support') else None,
                    last_choch=None,zone=None,warmup_bars=self.analysis_warmup,live_bars=self.analysis_bars,last_cycle_at=self.cycle_at,last_analysis_at=self.analysis_at)

    def snapshot(self):
        result=super().snapshot()
        if result.get('connected'):
            result.update(strategy='Scalping expérimental XAUUSD M1',risk=self.cfg.risk,daily_loss=self.cfg.daily_loss,strategy_settings=dict(self.options),strategy_settings_defaults=validate_settings({}))
            for p in result.get('positions',[]):
                p['owned']=any(str(x.ticket)==p['ticket'] and x.magic==MAGIC_SCALP for x in (self.mt.positions_get() or []))
        return result
