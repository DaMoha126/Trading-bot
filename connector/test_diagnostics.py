import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from bridge import DemoBridge
from test_bridge import MT


class DiagnosticTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name)
        self.mt=MT();self.b=DemoBridge(self.mt,p/'risk.json',p/'log.jsonl')

    def tearDown(self):self.tmp.cleanup()

    def test_idle_snapshot_does_not_invent_analysis(self):
        d=self.b.snapshot()['diagnostics']
        self.assertIsNone(d['last_cycle_at']);self.assertIsNone(d['last_bar_close'])
        self.assertEqual(d['live_bars'],0);self.assertFalse(self.b.running)

    def test_counts_only_new_closed_bars_and_does_not_send_orders(self):
        now=time.time()
        self.b.command(dict(action='start',id='diagnostic-start',supervision='autonomous'))
        before=self.b.diagnostics()
        self.assertEqual(before['warmup_bars'],80);self.assertEqual(before['live_bars'],0)
        self.b.step();self.assertEqual(self.b.diagnostics()['live_bars'],0)
        with patch('bridge.time.time',return_value=now+180):
            self.b.step();d=self.b.diagnostics()
            self.assertEqual(d['live_bars'],1)
            self.assertEqual(d['last_bar_close'],before['last_bar_close']+180)
            self.assertEqual(d['last_analysis_at'],now+180)
            self.b.step();self.assertEqual(self.b.diagnostics()['live_bars'],1)
        self.assertEqual(self.mt.sent,[])

    def test_stages_reflect_actual_engine_state(self):
        self.b.command(dict(action='start',id='diagnostic-stage'))
        self.assertIn('directionnelle',self.b.diagnostics()['stage'])
        self.b.engine.trend=1;self.assertIn('CHoCH',self.b.diagnostics()['stage'])
        self.b.engine.zone=dict(side=1,low=1,high=2,retested=False)
        self.assertIn('premier retest',self.b.diagnostics()['stage'])
        self.b.engine.zone['retested']=True;self.assertIn('rejet',self.b.diagnostics()['stage'])
        self.b.engine.position=True;self.assertIn('Position',self.b.diagnostics()['stage'])

    def test_stale_tick_does_not_advance_successful_cycle(self):
        self.b.command(dict(action='start',id='diagnostic-error',supervision='autonomous'))
        self.b.step();last=self.b.cycle_at
        tick=self.mt.symbol_info_tick();tick.time-=60
        self.mt.symbol_info_tick=lambda *args:tick
        self.b.step()
        self.assertFalse(self.b.running);self.assertEqual(self.b.cycle_at,last)
        self.assertEqual(self.b.analysis_bars,0)

    def test_live_choch_survives_event_flush_and_zone_removal(self):
        self.b.command(dict(action='start',id='diagnostic-choch',supervision='autonomous'))
        self.assertIsNone(self.b.diagnostics()['last_choch'])
        ts=int(time.time())//180*180
        self.b.engine.log('CHOCH',ts,side=-1,level=1.099,pivot_time=ts-900)
        self.b.step()
        self.assertEqual(self.b.diagnostics()['last_choch']['side'],-1)
        self.assertEqual(self.b.diagnostics()['last_choch']['level'],1.099)
        self.b.engine.zone=None;self.b.step()
        self.assertIsNone(self.b.diagnostics()['zone'])
        self.assertEqual(self.b.diagnostics()['last_choch']['time'],ts)
        self.assertEqual(self.mt.sent,[])

    def test_structure_exposes_confirmed_pivots_without_mutating_engine(self):
        self.b.command(dict(action='start',id='diagnostic-pivots'))
        self.b.engine.highs=[[180,1.12]];self.b.engine.lows=[[360,1.10]]
        d=self.b.diagnostics();self.assertEqual(d['swing_high'],[180,1.12])
        self.assertEqual(d['swing_low'],[360,1.10])
        d['swing_high'][1]=999
        self.assertEqual(self.b.engine.highs[-1][1],1.12)

if __name__=='__main__':unittest.main()
