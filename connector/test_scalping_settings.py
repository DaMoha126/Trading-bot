import math,unittest
from scalping_settings import validate_settings,session_open,DEFAULTS
import test_scalping_bridge as fixtures
from scalping_bridge import ScalpingBridge

class ValidationTest(unittest.TestCase):
 def test_invalid_and_unknown_inputs(self):
  for cfg in ({'risk':float('nan')},{'risk':.02},{'positions':True},{'positions':4},{'cooldown':-1},{'break_even':1},{'other':1},{'risk':.01,'daily_loss':.005}):
   with self.subTest(cfg=cfg),self.assertRaises(ValueError):validate_settings(cfg)
 def test_utc_and_midnight_sessions(self):
  s=validate_settings({'start1':22,'end1':2})
  self.assertTrue(session_open(23,s));self.assertTrue(session_open(1,s));self.assertFalse(session_open(5,s))
  s=validate_settings({'use_sessions':False});self.assertTrue(session_open(11,s))
 def test_defaults_unchanged(self):self.assertEqual(validate_settings({}),DEFAULTS)

class SettingsTest(unittest.TestCase):
 def setUp(self):fixtures.TestScalp.setUp(self)
 def tearDown(self):fixtures.TestScalp.tearDown(self)
 def submit(self):fixtures.TestScalp.submit(self)
 # Reuse authenticated broker fixture; these tests issue only simulated orders.
 def save(self,**values):
  return self.b.command(dict(action='settings',id='settings-command-123',config=values))
 def test_settings_persist_only_for_this_account(self):
  d=self.save(positions=2,risk=.003,cooldown=120)
  self.assertEqual(d['strategy_settings']['positions'],2)
  again=ScalpingBridge(self.mt,self.b.state_path,self.b.journal_path)
  self.assertEqual(again.options['cooldown'],120)
  self.mt.a.login=999
  other=ScalpingBridge(self.mt,self.b.state_path,self.b.journal_path)
  self.assertEqual(other.options,DEFAULTS)
  self.assertEqual(self.mt.sent,[])
 def test_running_settings_rejected(self):
  self.b.running=True
  with self.assertRaises(ValueError):self.save(positions=1)
  self.assertEqual(self.b.options['positions'],3)
 def test_position_count_and_risk_apply_to_orders(self):
  self.save(positions=2,risk=.003)
  self.submit();self.assertEqual(len(self.mt.sent),2)
  cost=sum(abs(self.mt.order_calc_profit(0,'XAUUSD',r['volume'],100.3,98.9))+7*r['volume'] for r in self.mt.sent)
  self.assertLessEqual(cost,30)
 def test_break_even_can_be_disabled(self):
  self.save(break_even=False);self.submit()
  self.mt.tick.bid=106;self.mt.tick.ask=106.1
  self.b.manage_break_even(self.mt.positions,self.mt.tick,self.mt.info)
  self.assertEqual(len(self.mt.sent),3)
 def test_break_even_trigger_customized(self):
  self.save(be_trigger=.8);self.submit()
  self.mt.tick.bid=106;self.mt.tick.ask=106.1
  self.b.manage_break_even(self.mt.positions,self.mt.tick,self.mt.info)
  self.assertEqual(len(self.mt.sent),3)
 def test_daily_halt_not_reset_by_save(self):
  self.mt.a.equity=9700;self.b.day_check(self.mt.a)
  self.save(daily_loss=.03)
  self.assertTrue(self.b.risk['halted'])
