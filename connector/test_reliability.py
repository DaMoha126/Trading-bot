import tempfile,time,unittest
from pathlib import Path
from test_bridge import MT
from bridge import DemoBridge
class ReliabilityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name);self.mt=MT();self.b=DemoBridge(self.mt,p/'state.json',p/'log.jsonl')
 def tearDown(self):self.tmp.cleanup()
 def test_autonomous_continues_without_browser(self):
  self.b.command(dict(action='start',id='command-autonomous',supervision='autonomous'));self.b.last_seen=time.time()-300
  self.b.step();self.assertTrue(self.b.running);self.assertEqual(self.mt.sent,[])
 def test_supervised_still_pauses(self):
  self.b.command(dict(action='start',id='command-supervised'));self.b.last_seen=time.time()-30;self.b.step();self.assertFalse(self.b.running)
 def test_mode_invalid_rejected(self):
  with self.assertRaises(ValueError):self.b.command(dict(action='start',id='command-invalid',supervision='anything'))
 def test_restart_never_autostarts(self):
  self.b.command(dict(action='start',id='command-autonomous',supervision='autonomous'))
  other=DemoBridge(self.mt,self.b.state_path,self.b.journal_path);self.assertFalse(other.running)
 def test_switching_accounts_does_not_reset_daily_halt(self):
  self.b.day_check(self.mt.a);self.mt.a.equity=9800;self.b.day_check(self.mt.a)
  self.mt.a.login=456;self.mt.a.equity=10000;self.b.day_check(self.mt.a)
  self.mt.a.login=123;self.assertTrue(self.b.day_check(self.mt.a))
 def test_candles_closed_only_and_no_orders(self):
  rows=self.b.candles();self.assertEqual(rows['timeframe'],'M3');self.assertTrue(all(b['time']+180<=time.time() for b in rows['bars']));self.assertEqual(self.mt.sent,[])
 def test_real_account_export_forbidden(self):
  self.mt.a.trade_mode=2
  with self.assertRaises(ValueError):self.b.candles()
 def test_old_snapshot_explicitly_marks_history_unavailable(self):
  d=self.b.snapshot();self.assertEqual(d['connector_version'],'4.0');self.assertEqual(d['history']['status'],'unavailable')
 def test_stale_tick_pauses_autonomous(self):
  self.b.command(dict(action='start',id='command-autonomous',supervision='autonomous'))
  tick=self.mt.symbol_info_tick();tick.time=int(time.time())-60;self.mt.symbol_info_tick=lambda *args:tick
  self.b.step();self.assertFalse(self.b.running);self.assertEqual(self.mt.sent,[])
 def test_invalid_broker_volume_step_never_sends(self):
  self.mt.info.volume_step=0;self.b.day_check(self.mt.a)
  with self.assertRaises(ValueError):self.b.submit(dict(id='invalid-vol-step',side=1,stop=1.099,ready=int(time.time())-1),self.mt.symbol_info_tick(),self.mt.info)
  self.assertEqual(self.mt.sent,[])
 def test_future_tick_never_sends(self):
  tick=self.mt.symbol_info_tick();tick.time=int(time.time())+120
  with self.assertRaises(ValueError):self.b.submit(dict(id='future-tick-test',side=1,stop=1.099,ready=int(time.time())-1),tick,self.mt.info)
  self.assertEqual(self.mt.sent,[])
 def test_equity_curve_survives_restart(self):
  self.b.record_equity(self.mt.a)
  other=DemoBridge(self.mt,self.b.state_path,self.b.journal_path)
  self.assertEqual(other.equity_points[-1]['equity'],10000)
  self.assertFalse(other.running)
 def test_equity_curve_does_not_mix_accounts(self):
  self.b.record_equity(self.mt.a);self.mt.a.login=456;self.mt.a.equity=2000;self.b.record_equity(self.mt.a)
  self.assertEqual(len(self.b.equity_points),1);self.assertEqual(self.b.equity_points[-1]['equity'],2000)
if __name__=='__main__':unittest.main()
