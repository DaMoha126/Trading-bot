"""Lien expérimental structure M1 / simulateur ; aucun envoi d'ordres."""
from datetime import datetime, timezone
from paper_scalper import PaperScalper
from structure_m1 import StructureM1

class ReplayM1:
    def __init__(self, capital, settings=None, pivot=2):
        self.structure=StructureM1(pivot)
        self.paper=PaperScalper(capital,settings) if settings else PaperScalper(capital)
        self.state=None
        self.pending_choch=False
        self.last_tick=None
        self.last_event=None

    def bar_closed(self, bar, received_at):
        if received_at < bar.time+60: raise ValueError('Bougie non clôturée')
        if self.last_event is not None and received_at < self.last_event: raise ValueError('Événement désordonné')
        self.last_event=received_at
        self.state=self.structure.feed(bar)
        self.pending_choch = self.pending_choch or self.state['event'] in ('choch_up','choch_down')
        # A signal may not span a level or structure change.
        self.paper.previous_bid=None

    def tick(self, now, bid, ask):
        if self.last_tick is not None and now <= self.last_tick: raise ValueError('Tick désordonné')
        if self.last_event is not None and now < self.last_event: raise ValueError('Événement désordonné')
        if self.state and now < self.state['bar_close']: raise ValueError('Tick antérieur à la bougie')
        self.last_tick=now
        self.last_event=now
        # UTC is a temporary assumption pending confirmation of the user's timezone.
        hour=datetime.fromtimestamp(now,timezone.utc).hour
        hours=13 <= hour < 17 or 0 <= hour < 5
        s=self.state or {}
        low=s.get('support'); high=s.get('resistance')
        valid=low is not None and high is not None and low < high
        # Existing paper positions must still be monitored while structure is absent.
        if not valid:
            low,high = bid*.5,bid*1.5
        self.paper.quote(now,bid,ask,low,high,s.get('trend','none') if valid else 'none',
                         choch=self.pending_choch,trading_hours=hours and valid)
        self.pending_choch=False
