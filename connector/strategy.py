"""Forex Bot V1. Simulation only; Python 3.10+, standard library."""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import math
import os
import random
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

STEP = 180

def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()

@dataclass(frozen=True)
class Config:
    mode: str = 'simulation'
    symbol: str = 'EURUSD'
    capital: float = 10000.0
    risk: float = 0.005
    daily_loss: float = 0.01
    pivot: int = 2
    atr_period: int = 14
    zone_atr: float = 0.15  # total width, half on each side
    wick: float = 0.40
    expiry: int = 20
    stop_atr: float = 0.10
    rr: float = 2.0
    spread: float = 0.00010  # price units, not points
    slippage: float = 0.00002  # price units, adverse on both fills
    commission: float = 3.5  # USD / 100000 units / side
    min_units: int = 1000
    unit_step: int = 1000
    leverage: float = 30.0

    def __post_init__(self):
        if self.mode != 'simulation' or self.symbol != 'EURUSD':
            raise ValueError('V1: simulation EURUSD uniquement, capital en USD.')
        for key, val in asdict(self).items():
            if isinstance(val, (float, int)) and (isinstance(val, bool) or not math.isfinite(val)):
                raise ValueError('Parametre non fini: ' + key)
        for key in ('pivot','atr_period','expiry','min_units','unit_step'):
            if type(getattr(self,key)) is not int or getattr(self,key) < 1:
                raise ValueError('Entier positif requis: ' + key)
        if not (0 < self.risk <= self.daily_loss < 1 and 0 < self.wick <= 1):
            raise ValueError('Risque / limite quotidienne / meche invalides.')
        if min(self.capital,self.zone_atr,self.rr,self.leverage) <= 0:
            raise ValueError('Capital, largeur, ratio, levier doivent etre positifs.')
        if min(self.spread,self.slippage,self.commission,self.stop_atr) < 0:
            raise ValueError('Couts ou marge negatifs.')

@dataclass(frozen=True)
class Bar:
    time: int
    open: float
    high: float
    low: float
    close: float
    spread: float

    def validate(self):
        if type(self.time) is not int or self.time % STEP:
            raise ValueError('Horodatage UTC non aligne M3.')
        if not all(math.isfinite(x) for x in (self.open,self.high,self.low,self.close,self.spread)):
            raise ValueError('OHLC/spread non fini.')
        if self.low <= 0 or self.spread < 0 or not self.low <= min(self.open,self.close) <= max(self.open,self.close) <= self.high:
            raise ValueError('OHLC/spread incoherent.')

class Engine:
    def __init__(self, cfg=None):
        self.cfg = cfg or Config()
        self.cash = self.cfg.capital
        self.bars = []
        self.highs, self.lows = [], []
        self.trend = 0
        self.used = []
        self.zone = None
        self.pending = None
        self.position = None
        self.events, self.trades, self.equity = [], [], []
        self.day = None
        self.day_start = self.cash
        self.halted = False
        self.last_tick = None
        self.peak = self.cash
        self.max_dd = 0.0

    def log(self, kind, ts, **details):
        self.events.append(dict(event_id=len(self.events)+1, time=utc(ts), event=kind, **details))

    def mark(self, bid, ask):
        p = self.position
        if not p:
            return self.cash
        exit_price = bid-self.cfg.slippage if p['side']==1 else ask+self.cfg.slippage
        return self.cash + p['side']*(exit_price-p['entry'])*p['units'] - p['fee']

    def day_check(self, ts, bid, ask):
        day = utc(ts)[:10]
        eq = self.mark(bid,ask)
        if day != self.day:
            self.day, self.day_start, self.halted = day, eq, False
            self.log('DAY_START',ts,equity=eq)
        if not self.halted and eq <= self.day_start*(1-self.cfg.daily_loss)+1e-8:
            self.halted = True
            self.pending = self.zone = None
            self.log('DAILY_HALT',ts,equity=eq)
        self.peak = max(self.peak,eq)
        self.max_dd = max(self.max_dd,(self.peak-eq)/self.peak)
        return eq

    def cancel(self, ts, reason):
        if self.zone or self.pending:
            self.log('CANCEL',ts,reason=reason)
        self.zone = self.pending = None

    def enter(self, ts, bid, ask):
        s = self.pending
        if not s:
            return
        self.pending = None
        if self.position or self.halted or ts < s['ready'] or ts > s['ready']+STEP:
            self.log('REJECT',ts,reason='position_halt_or_stale',signal=s['id'])
            return
        side = s['side']
        entry = ask+self.cfg.slippage if side==1 else bid-self.cfg.slippage
        distance = side*(entry-s['stop'])
        if distance <= 0:
            self.log('REJECT',ts,reason='invalid_stop_after_gap',signal=s['id'])
            return
        # stop slippage and BOTH commissions included in planned cash risk.
        loss_per_unit = distance+self.cfg.slippage+2*self.cfg.commission/100000
        budget = min(self.cash*self.cfg.risk,
                     self.mark(bid,ask)-self.day_start*(1-self.cfg.daily_loss))
        raw = min(max(0,budget)/loss_per_unit, max(0,self.cash)*self.cfg.leverage/entry)
        units = math.floor(raw/self.cfg.unit_step)*self.cfg.unit_step
        if units < self.cfg.min_units:
            self.log('REJECT',ts,reason='insufficient_risk_or_margin',signal=s['id'])
            return
        fee = units*self.cfg.commission/100000
        self.position = dict(side=side,entry=entry,stop=s['stop'],target=entry+side*self.cfg.rr*distance,
                             units=units,fee=fee,opened=ts,signal=s['id'],planned_risk=units*loss_per_unit)
        self.cash -= fee
        self.log('ENTRY',ts,**self.position)

    def close(self, ts, price, reason):
        p = self.position
        net = p['side']*(price-p['entry'])*p['units']-2*p['fee']
        self.cash += p['side']*(price-p['entry'])*p['units']-p['fee']
        self.trades.append(dict(**p,closed=ts,exit=price,pnl=net,reason=reason))
        self.log('EXIT',ts,pnl=net,reason=reason,signal=p['signal'])
        self.position = None

    def exit_tick(self, ts, bid, ask):
        p = self.position
        if not p:
            return
        q = bid if p['side']==1 else ask
        if p['side']*(q-p['stop'])<=0:
            self.close(ts,q-p['side']*self.cfg.slippage,'SL')
        elif p['side']*(q-p['target'])>=0:
            self.close(ts,p['target'],'TP')

    def quote(self, ts, bid, ask):
        if not all(math.isfinite(x) for x in (ts,bid,ask)) or bid<=0 or ask<bid:
            raise ValueError('Cotation invalide')
        if self.last_tick is not None and ts <= self.last_tick:
            return
        self.last_tick = ts
        self.day_check(ts,bid,ask)
        self.exit_tick(ts,bid,ask)
        self.day_check(ts,bid,ask)
        self.enter(ts,bid,ask)
        self.day_check(ts,bid,ask)

    def atr(self):
        n = self.cfg.atr_period
        if len(self.bars)<n+1:
            return None
        a = self.bars
        return sum(max(a[i]['high']-a[i]['low'],abs(a[i]['high']-a[i-1]['close']),
                       abs(a[i]['low']-a[i-1]['close'])) for i in range(len(a)-n,len(a)))/n

    def update_structure(self):
        n = self.cfg.pivot
        if len(self.bars)<2*n+1:
            return
        window = self.bars[-(2*n+1):]
        middle = window[n]
        neighbors = window[:n]+window[n+1:]
        if all(middle['high']>x['high'] for x in neighbors):
            self.highs.append([middle['time'],middle['high']])
        if all(middle['low']<x['low'] for x in neighbors):
            self.lows.append([middle['time'],middle['low']])
        self.highs, self.lows = self.highs[-2:], self.lows[-2:]
        # Establish initial context only; subsequent breaks change the bias.
        if self.trend==0 and len(self.highs)==len(self.lows)==2:
            if self.highs[-1][1]>self.highs[-2][1] and self.lows[-1][1]>self.lows[-2][1]:
                self.trend=1
            elif self.highs[-1][1]<self.highs[-2][1] and self.lows[-1][1]<self.lows[-2][1]:
                self.trend=-1

    def strategy(self, b):
        self.update_structure()
        atr = self.atr()
        if atr is None or atr<=0:
            return
        side, pivot = 0, None
        if self.trend==-1 and self.highs and b.close>self.highs[-1][1]:
            side,pivot=1,self.highs[-1]
        elif self.trend==1 and self.lows and b.close<self.lows[-1][1]:
            side,pivot=-1,self.lows[-1]
        if side and [side,pivot[0]] not in self.used:
            self.used.append([side,pivot[0]])
            self.trend=side
            self.cancel(b.time+STEP,'opposite_choch')
            self.log('CHOCH',b.time+STEP,side=side,level=pivot[1],pivot_time=pivot[0])
            if not self.position and not self.halted:
                half=atr*self.cfg.zone_atr/2
                self.zone=dict(side=side,low=pivot[1]-half,high=pivot[1]+half,
                               born=b.time,retested=False)
            return  # no retest on CHoCH candle itself
        z=self.zone
        if not z or self.position or self.halted:
            return
        if (b.time-z['born'])//STEP>self.cfg.expiry:
            self.cancel(b.time+STEP,'expired'); return
        if (z['side']==1 and b.close<=z['low']) or (z['side']==-1 and b.close>=z['high']):
            self.cancel(b.time+STEP,'zone_invalidated'); return
        if b.low<=z['high'] and b.high>=z['low']:
            if not z['retested']:
                self.log('RETEST',b.time+STEP)
            z['retested']=True
        if not z['retested'] or b.high==b.low:
            return
        wick = min(b.open,b.close)-b.low if z['side']==1 else b.high-max(b.open,b.close)
        swept = b.low<z['low'] if z['side']==1 else b.high>z['high']
        if swept and wick/(b.high-b.low)>=self.cfg.wick:
            stop=b.low-atr*self.cfg.stop_atr if z['side']==1 else b.high+atr*self.cfg.stop_atr
            ident=f'{self.cfg.symbol}:{b.time}:{z["side"]}'
            self.pending=dict(id=ident,side=z['side'],stop=stop,ready=b.time+STEP)
            self.log('SIGNAL',b.time+STEP,**self.pending)
            self.zone=None

    def feed(self, b, now=None, historical=True):
        b.validate()
        if now is not None and b.time+STEP>now:
            return False  # unfinished candle
        if self.bars and b.time<=self.bars[-1]['time']:
            old=next((x for x in reversed(self.bars) if x['time']==b.time),None)
            if old==asdict(b):
                return False
            raise ValueError('Historique modifie ou bougie desordonnee.')
        gap=bool(self.bars and b.time-self.bars[-1]['time']!=STEP)
        if gap:
            self.log('DATA_GAP',b.time,previous=self.bars[-1]['time'])
            self.cancel(b.time,'data_gap')
            self.highs,self.lows,self.trend=[],[],0
            # Keep full history for audit, but ATR and pivots need contiguous warmup.
            self._warmup_since=b.time
        if historical:
            self.day_check(b.time,b.open,b.open+b.spread)
            self.exit_tick(b.time,b.open,b.open+b.spread) # existing overnight gap
            self.day_check(b.time,b.open,b.open+b.spread)
            if not gap:
                self.enter(b.time,b.open,b.open+b.spread)
            # Worst excursion, even if TP might have occurred first: conservative.
            if self.position:
                p=self.position
                stop_hit=b.low<=p['stop'] if p['side']==1 else b.high+b.spread>=p['stop']
                adverse=max(b.low,p['stop']) if p['side']==1 and stop_hit else b.low
                adverse=min(b.high+b.spread,p['stop'])-b.spread if p['side']==-1 and stop_hit else adverse
                self.day_check(b.time,adverse,adverse+b.spread)
                target_hit=b.high>=p['target'] if p['side']==1 else b.low+b.spread<=p['target']
                if stop_hit:
                    self.close(b.time+STEP,p['stop']-p['side']*self.cfg.slippage,'SL_BOTH' if target_hit else 'SL')
                elif target_hit:
                    self.close(b.time+STEP,p['target'],'TP')
        self.bars.append(asdict(b))
        # Reset indicators' contiguous window by withholding strategy until warmed up.
        warm=getattr(self,'_warmup_since',self.bars[0]['time'])
        if (b.time-warm)//STEP>=max(self.cfg.atr_period,2*self.cfg.pivot):
            self.strategy(b)
        if historical:
            eq=self.day_check(b.time+STEP-0.001,b.close,b.close+b.spread)
            self.equity.append(dict(time=b.time+STEP,equity=eq))
        return True

    def save(self,path):
        path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
        payload=dict(self.__dict__); payload['cfg']=asdict(self.cfg)
        temp=path.with_suffix('.tmp')
        with temp.open('w',encoding='utf8') as f:
            json.dump(dict(version=1,state=payload),f,allow_nan=False)
            f.flush(); os.fsync(f.fileno())
        os.replace(temp,path)

    @classmethod
    def load(cls,path,cfg):
        data=json.loads(Path(path).read_text(encoding='utf8'))
        if data['version']!=1 or data['state']['cfg']!=asdict(cfg):
            raise ValueError('Version/configuration incompatible avec le checkpoint.')
        obj=cls(cfg)
        state=data['state']; state.pop('cfg'); obj.__dict__.update(state)
        return obj

    def report(self,out,label):
        out=Path(out); out.mkdir(parents=True,exist_ok=True)
        pnl=[t['pnl'] for t in self.trades]
        wins=[x for x in pnl if x>0]; losses=[x for x in pnl if x<0]
        groups={}
        for t in self.trades:
            for key in (('BUY' if t['side']==1 else 'SELL'),utc(t['closed'])[:7]):
                g=groups.setdefault(key,dict(trades=0,pnl=0.0)); g['trades']+=1; g['pnl']+=t['pnl']
        stats=dict(label=label,mode='SIMULATION',symbol=self.cfg.symbol,trades=len(pnl),
                   signals=sum(e['event']=='SIGNAL' for e in self.events),
                   cancelled=sum(e['event']=='CANCEL' for e in self.events),
                   rejected=sum(e['event']=='REJECT' for e in self.events),
                   data_gaps=sum(e['event']=='DATA_GAP' for e in self.events),
                   win_rate=len(wins)/len(pnl) if pnl else 0,
                   average_win=sum(wins)/len(wins) if wins else 0,
                   average_loss=sum(losses)/len(losses) if losses else 0,
                   expectancy=sum(pnl)/len(pnl) if pnl else 0,
                   realized_net=sum(pnl),cash=self.cash,open_position=self.position,
                   last_equity=self.equity[-1]["equity"] if self.equity else self.cash,
                   errors=sum(e["event"]=="DATA_ERROR" for e in self.events),
                   max_drawdown=self.max_dd,by_period_and_side=groups,
                   cancelled_pending_at_end=self.pending is not None)
        (out/'summary.json').write_text(json.dumps(stats,indent=2,ensure_ascii=False),encoding='utf8')
        (out/'events.jsonl').write_text(''.join(json.dumps(e,ensure_ascii=False)+'\n' for e in self.events),encoding='utf8')
        for name,rows in [('trades',self.trades),('equity',self.equity)]:
            with (out/f'{name}.csv').open('w',newline='',encoding='utf8') as f:
                fields=list(rows[0]) if rows else (['signal','pnl'] if name=='trades' else ['time','equity'])
                w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
        cards=''.join(f'<article><small>{k}</small><strong>{v}</strong></article>' for k,v in [
            ('Transactions',len(pnl)),('Résultat réalisé',f'{sum(pnl):.2f} USD'),
            ('Réussite',f'{stats["win_rate"]:.1%}'),('Drawdown observé',f'{self.max_dd:.2%}')])
        rows=''.join('<tr>'+''.join(f'<td>{html.escape(str(v))}</td>' for v in
             [utc(t['opened']),'BUY' if t['side']==1 else 'SELL',t['units'],round(t['entry'],6),round(t['pnl'],2),t['reason']])+'</tr>' for t in self.trades)
        page='''<!doctype html><html lang="fr"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Forex Bot V1</title><style>body{background:#101827;color:#e8effa;font:16px system-ui;max-width:1100px;margin:40px auto;padding:20px}h1{font-size:38px}small{color:#9fadc3}section{display:flex;flex-wrap:wrap;gap:16px}article{background:#1c293e;padding:24px;border-radius:12px;flex:1}strong{display:block;font-size:28px;margin-top:12px}table{width:100%;border-collapse:collapse}td,th{text-align:left;padding:12px;border-bottom:1px solid #34425a}p{line-height:1.7}.scroll{overflow:auto}</style><small>BEN DAO · RECHERCHE DE STRATÉGIE</small><h1>Forex Bot V1</h1><p>SIMULATION UNIQUEMENT · EUR/USD · M3</p>'''
        page+=f'<p>{html.escape(label)}</p><section>{cards}</section><p>Résultats après coûts simulés. Les positions ouvertes ne sont pas liquidées artificiellement à la fin. Aucune performance future ne peut être déduite de cet essai.</p><div class="scroll"><table><tr><th>Entrée UTC</th><th>Sens</th><th>Unités</th><th>Prix</th><th>Net USD</th><th>Sortie</th></tr>{rows}</table></div></html>'
        (out/'rapport.html').write_text(page,encoding='utf8')
        return stats


def read_csv(path,cfg):
    with open(path,newline='',encoding='utf-8-sig') as f:
        for line,row in enumerate(csv.DictReader(f),2):
            try:
                raw=row['time']
                if raw.isdigit(): ts=int(raw)
                else:
                    dt=datetime.fromisoformat(raw.replace('Z','+00:00'))
                    if dt.tzinfo is None: raise ValueError('Fuseau UTC explicite requis')
                    ts=int(dt.timestamp())
                    if dt.timestamp()!=ts: raise ValueError("Secondes fractionnaires interdites")
                b=Bar(ts,*(float(row[k]) for k in ('open','high','low','close')),
                      float(row.get('spread') or cfg.spread))
                b.validate(); yield b
            except (KeyError,ValueError,TypeError) as ex:
                raise ValueError(f'CSV ligne {line}: {ex}') from ex


def demo(path):
    rng=random.Random(20261016)
    start=1767600000 # aligned UTC, synthetic only
    start-=start%STEP
    price=1.1
    with open(path,'w',newline='') as f:
        w=csv.writer(f);w.writerow(['time','open','high','low','close','spread'])
        for i in range(2400):
            drift=0.00006*math.sin(i/35)
            close=price+drift+rng.gauss(0,0.00016)
            high=max(price,close)+abs(rng.gauss(0,0.00012))
            low=min(price,close)-abs(rng.gauss(0,0.00012))
            w.writerow([start+i*STEP,price,high,low,close,0.0001]);price=close


def main():
    p=argparse.ArgumentParser(description='Forex Bot V1 — simulation EURUSD M3')
    p.add_argument('command',choices=['demo','backtest','watch'])
    p.add_argument('--csv',default='data.csv')
    p.add_argument('--config',default='config.json')
    p.add_argument('--out',default='resultats')
    p.add_argument('--checkpoint',default='state.json')
    p.add_argument('--resume',action='store_true')
    p.add_argument('--split',type=float,default=0,help='Fraction chronologique apprentissage, ex. 0.7')
    a=p.parse_args()
    cfg=Config(**json.loads(Path(a.config).read_text())) if Path(a.config).exists() else Config()
    if a.split and (a.command!='backtest' or not 0.1<=a.split<=0.9 or a.resume):
        p.error('--split entre 0.1 et 0.9, uniquement backtest sans reprise')
    if a.command=='demo':
        demo(a.csv)
    e=Engine.load(a.checkpoint,cfg) if a.resume else Engine(cfg)
    try:
        while True:
            bars=list(read_csv(a.csv,cfg)) # validate the entire snapshot before execution
            if a.split:
                cut=int(len(bars)*a.split)
                if min(cut,len(bars)-cut)<50: raise ValueError('Au moins 50 bougies par segment')
                for label,part in [('developpement',bars[:cut]),('hors_echantillon',bars[cut:])]:
                    run=Engine(cfg)
                    for b in part: run.feed(b)
                    run.report(Path(a.out)/label,'Historique utilisateur — '+label)
                print('Rapports separes:',a.out);return
            for b in bars:
                e.feed(b,now=time.time())
            e.save(a.checkpoint)
            label='DONNEES SYNTHETIQUES — verification technique, aucun resultat de marche' if a.command=='demo' else 'CSV utilisateur — simulation sur bougies BID, spread constant par bougie'
            stats=e.report(a.out,label)
            print(f'SIMULATION | {len(e.bars)} bougies | {stats["trades"]} transactions | net realise {stats["realized_net"]:.2f} USD',flush=True)
            if a.command!='watch': break
            if bars and time.time()-(bars[-1].time+STEP)>2*STEP:
                e.cancel(int(time.time()),'stale_feed'); e.save(a.checkpoint)
                print('Flux perime: attente de donnees fraiches.',flush=True)
            time.sleep(3)
    except KeyboardInterrupt:
        e.save(a.checkpoint)
        print('Etat sauvegarde.')
    except (ValueError,OSError) as ex:
        e.cancel(int(time.time()),'data_error')
        e.log('DATA_ERROR',int(time.time()),detail=str(ex))
        e.save(a.checkpoint);e.report(a.out,'ARRET SUR ERREUR DE DONNEES')
        raise SystemExit(str(ex))

if __name__=='__main__':
    main()
