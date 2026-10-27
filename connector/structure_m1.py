"""Structure M1 de recherche, construite à partir des seules bougies clôturées.

Hypothèse provisoire : pivots stricts sur deux bougies de chaque côté ;
le dernier pivot opposé cassé en clôture constitue le CHoCH. Les niveaux
peuvent être indisponibles ou inadaptés comme cible ; aucune exécution MT5.
"""
from dataclasses import dataclass
from math import isfinite

@dataclass(frozen=True)
class Bar:
    time: int
    open: float
    high: float
    low: float
    close: float

class StructureM1:
    def __init__(self, pivot=2):
        if type(pivot) is not int or pivot < 1: raise ValueError('Pivot invalide')
        self.pivot = pivot
        self.bars = []
        self.highs = []
        self.lows = []
        self.trend = 'none'
        self.consumed = set()

    def feed(self, bar):
        if (type(bar.time) is not int or bar.time % 60 or
            not all(isfinite(x) and x > 0 for x in (bar.open,bar.high,bar.low,bar.close)) or
            not bar.low <= min(bar.open,bar.close) <= max(bar.open,bar.close) <= bar.high):
            raise ValueError('Bougie M1 invalide')
        if self.bars and bar.time <= self.bars[-1].time: raise ValueError('Bougie désordonnée')
        if self.bars and bar.time != self.bars[-1].time+60:
            self.bars.clear(); self.highs.clear(); self.lows.clear(); self.consumed.clear(); self.trend='none'
        self.bars.append(bar)
        n=self.pivot
        # A break uses only pivots known before this bar closes.
        event=None
        if self.trend == 'up' and self.lows and bar.close < self.lows[-1][1]:
            key=('down',self.lows[-1][0])
            if key not in self.consumed:
                self.consumed.add(key); self.trend='down'; event='choch_down'
        elif self.trend == 'down' and self.highs and bar.close > self.highs[-1][1]:
            key=('up',self.highs[-1][0])
            if key not in self.consumed:
                self.consumed.add(key); self.trend='up'; event='choch_up'
        elif self.trend == 'up' and self.highs and bar.close > self.highs[-1][1]:
            key=('bos_up',self.highs[-1][0])
            if key not in self.consumed: self.consumed.add(key); event='bos_up'
        elif self.trend == 'down' and self.lows and bar.close < self.lows[-1][1]:
            key=('bos_down',self.lows[-1][0])
            if key not in self.consumed: self.consumed.add(key); event='bos_down'
        if len(self.bars) >= 2*n+1:
            window=self.bars[-(2*n+1):]; mid=window[n]; neighbors=window[:n]+window[n+1:]
            if all(mid.high > b.high for b in neighbors): self.highs.append((mid.time,mid.high))
            if all(mid.low < b.low for b in neighbors): self.lows.append((mid.time,mid.low))
            self.highs=self.highs[-2:];self.lows=self.lows[-2:]
        if self.trend == 'none' and len(self.highs)==len(self.lows)==2:
            if self.highs[-1][1]>self.highs[-2][1] and self.lows[-1][1]>self.lows[-2][1]: self.trend='up'
            elif self.highs[-1][1]<self.highs[-2][1] and self.lows[-1][1]<self.lows[-2][1]: self.trend='down'
        self.bars=self.bars[-max(2*n+1,100):]
        self.consumed={x for x in self.consumed if x[1] >= self.bars[0].time}
        support=self.lows[-1][1] if self.lows else None
        resistance=self.highs[-1][1] if self.highs else None
        return dict(trend=self.trend,support=support,resistance=resistance,event=event,bar_close=bar.time+60)
