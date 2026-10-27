"""Prototype de recherche XAUUSD : simulation locale, aucun accès MT5.

Prix Bid/Ask, taille en unités de métal, capital en USD. Paramètres indicatifs,
non calibrés. Les niveaux et la tendance doivent être calculés sans données futures.
"""
from dataclasses import dataclass
from datetime import datetime, timezone
from math import floor, isfinite
from liquidity_signal import signal

@dataclass(frozen=True)
class Settings:
    penetration: float = 0.10
    stop_distance: float = 1.0
    risk_fraction: float = 0.005
    daily_loss: float = 0.02
    cooldown_seconds: int = 60
    max_positions: int = 3
    unit_step: float = 0.01
    min_units: float = 0.01
    max_spread: float = 0.5
    commission_per_unit_side: float = 0.0
    slippage: float = 0.0

    def __post_init__(self):
        vals = (self.penetration, self.stop_distance, self.risk_fraction, self.daily_loss,
                self.unit_step, self.min_units, self.max_spread, self.commission_per_unit_side, self.slippage)
        if not all(isfinite(x) for x in vals) or min(self.penetration, self.stop_distance, self.unit_step, self.min_units, self.max_spread) <= 0:
            raise ValueError('Paramètres invalides')
        if not 0 < self.risk_fraction <= self.daily_loss < 1 or self.commission_per_unit_side < 0 or self.slippage < 0:
            raise ValueError('Risque ou frais invalides')
        if type(self.max_positions) is not int or not 1 <= self.max_positions <= 3 or self.cooldown_seconds < 0:
            raise ValueError('Limites invalides')


@dataclass
class Position:
    side: str
    entry: float
    stop: float
    target: float
    units: float
    break_even: bool = False

class PaperScalper:
    def __init__(self, equity, settings=Settings()):
        if not isfinite(equity) or equity <= 0: raise ValueError('Capital invalide')
        self.cash = equity
        self.cfg = settings
        self.positions = []
        self.previous_bid = None
        self.last_time = None
        self.day = None
        self.day_start = equity
        self.halted = False
        self.resume_after = 0
        self.events = []

    def equity(self, bid, ask):
        return self.cash + sum(((bid-p.entry) if p.side == 'BUY' else (p.entry-ask))*p.units
                               - self.cfg.commission_per_unit_side*p.units for p in self.positions)

    def close_all(self, now, bid, ask, reason):
        for p in self.positions:
            exit_price = bid-self.cfg.slippage if p.side == 'BUY' else ask+self.cfg.slippage
            pnl = ((exit_price-p.entry) if p.side == 'BUY' else (p.entry-exit_price))*p.units
            self.cash += pnl - self.cfg.commission_per_unit_side*p.units
            self.events.append(('close', reason, pnl))
        if self.positions: self.resume_after = now+self.cfg.cooldown_seconds
        self.positions.clear()

    def quote(self, now, bid, ask, support, resistance, trend, choch=False, trading_hours=True):
        if not all(isfinite(v) for v in (now, bid, ask, support, resistance)) or bid <= 0 or ask < bid:
            raise ValueError('Cotation invalide')
        if self.last_time is not None and now <= self.last_time: raise ValueError('Ticks désordonnés')
        self.last_time = now
        day = datetime.fromtimestamp(now, timezone.utc).date()
        if day != self.day:
            self.day = day
            self.day_start = self.equity(bid, ask)
            self.halted = False
        if self.equity(bid, ask) <= self.day_start*(1-self.cfg.daily_loss):
            self.halted = True
            self.close_all(now, bid, ask, 'limite quotidienne')
        # Stops and targets execute at observed quote, not at the requested price.
        for p in self.positions[:]:
            exit_quote = bid if p.side == 'BUY' else ask
            hit_stop = exit_quote <= p.stop if p.side == 'BUY' else exit_quote >= p.stop
            hit_target = exit_quote >= p.target if p.side == 'BUY' else exit_quote <= p.target
            if hit_stop or hit_target:
                price = exit_quote-self.cfg.slippage if p.side == 'BUY' else exit_quote+self.cfg.slippage
                pnl = ((price-p.entry) if p.side == 'BUY' else (p.entry-price))*p.units
                self.cash += pnl-self.cfg.commission_per_unit_side*p.units
                self.positions.remove(p)
                self.events.append(('close', 'stop' if hit_stop else 'objectif', pnl))
                if not self.positions: self.resume_after=now+self.cfg.cooldown_seconds
                continue
            midpoint = (p.entry+p.target)/2
            if not p.break_even and ((p.side == 'BUY' and bid >= midpoint) or (p.side == 'SELL' and ask <= midpoint)):
                offset = 2*self.cfg.commission_per_unit_side+self.cfg.slippage
                p.stop = p.entry+offset if p.side == 'BUY' else p.entry-offset
                p.break_even = True
                self.events.append(('break_even', p.side))
        if self.equity(bid, ask) <= self.day_start*(1-self.cfg.daily_loss):
            self.halted = True
            self.close_all(now, bid, ask, 'limite quotidienne')
        if choch and self.positions:
            self.close_all(now, bid, ask, 'CHoCH')
        prev = self.previous_bid
        self.previous_bid = bid
        if (prev is None or self.positions or self.halted or now < self.resume_after or not trading_hours
                or ask-bid > self.cfg.max_spread): return
        s = signal(prev, bid, support, resistance, trend, self.cfg.penetration, self.cfg.stop_distance)
        if s is None: return
        entry = ask+self.cfg.slippage if s.side == 'BUY' else bid-self.cfg.slippage
        stop = bid-self.cfg.stop_distance if s.side == 'BUY' else bid+self.cfg.stop_distance
        target = resistance if s.side == 'BUY' else support
        if (s.side == 'BUY' and not stop < entry < target) or (s.side == 'SELL' and not target < entry < stop):
            self.events.append(('reject', 'stop ou objectif invalide')); return
        per_unit = abs(entry-stop)+self.cfg.slippage+2*self.cfg.commission_per_unit_side
        budget = min(self.equity(bid,ask)*self.cfg.risk_fraction,
                     self.equity(bid,ask)-self.day_start*(1-self.cfg.daily_loss))
        each = floor(max(0,budget)/per_unit/self.cfg.max_positions/self.cfg.unit_step+1e-10)*self.cfg.unit_step
        if each < self.cfg.min_units:
            self.events.append(('reject','volume minimal')); return
        for _ in range(self.cfg.max_positions):
            self.cash -= each*self.cfg.commission_per_unit_side
            self.positions.append(Position(s.side,entry,stop,target,each))
        self.events.append(('open',s.side,len(self.positions),each,per_unit*each*len(self.positions)))
