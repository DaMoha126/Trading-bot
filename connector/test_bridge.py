import tempfile,time,unittest
from pathlib import Path
from types import SimpleNamespace as N
from bridge import DemoBridge
from strategy import Config

class MT:
 ACCOUNT_TRADE_MODE_DEMO=0;ORDER_TYPE_BUY=0;ORDER_TYPE_SELL=1;ORDER_FILLING_FOK=0;ORDER_FILLING_IOC=1;ORDER_FILLING_RETURN=2;TRADE_ACTION_DEAL=1;TRADE_ACTION_SLTP=6;ORDER_TIME_GTC=0;TRADE_RETCODE_DONE=10009;TRADE_RETCODE_DONE_PARTIAL=10010;TIMEFRAME_M3=3
 def __init__(self):
  self.a=N(login=123,server='Demo',trade_mode=0,currency='USD',trade_allowed=True,trade_expert=True,equity=10000,balance=10000,profit=0,margin=0,margin_free=10000)
  self.info=N(currency_base='EUR',currency_profit='USD',trade_tick_size=.00001,point=.00001,digits=5,trade_stops_level=10,volume_step=.01,volume_min=.01,volume_max=100,filling_mode=1)
  self.sent=[];self.positions=[];self.orders=[];self.mode_on_check=None;self.fail_send=False
 def account_info(self):return self.a
 def terminal_info(self):return N(connected=True,trade_allowed=True,tradeapi_disabled=False)
 def symbol_select(self,*args):return True
 def symbol_info(self,*args):return self.info
 def symbol_info_tick(self,*args):return N(time=int(time.time()),bid=1.1,ask=1.1001)
 def positions_get(self,**kwargs):return self.positions
 def orders_get(self):return self.orders
 def order_calc_profit(self,kind,symbol,lot,entry,sl):return (sl-entry)*(1 if kind==0 else -1)*100000*lot
 def order_calc_margin(self,*args):return 3000
 def order_check(self,r):
  if self.mode_on_check is not None:self.a.trade_mode=self.mode_on_check
  return N(retcode=0,comment='OK')
 def order_send(self,r):
  self.sent.append(r)
  return None if self.fail_send else N(retcode=10009,price=r.get('price',1.1))
 def copy_rates_from_pos(self,*args):
  end=int(time.time())//180*180
  return [dict(time=end-i*180,open=1.1,high=1.101,low=1.099,close=1.1,spread=10) for i in range(80,0,-1)]

class Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();p=Path(self.tmp.name);self.mt=MT();self.b=DemoBridge(self.mt,p/'risk.json',p/'log.jsonl');self.b.day_check(self.mt.a)
 def tearDown(self):self.tmp.cleanup()
 def signal(self,side=1):return dict(id='signal-123',side=side,stop=1.099 if side==1 else 1.101,ready=int(time.time())-2)
 def send(self,side=1):self.b.submit(self.signal(side),self.mt.symbol_info_tick(),self.mt.info)
 def test_real_account_refused(self):
  self.mt.a.trade_mode=2
  with self.assertRaises(ValueError):self.send()
  self.assertEqual(self.mt.sent,[])
 def test_contest_refused(self):
  self.mt.a.trade_mode=1
  with self.assertRaises(ValueError):self.b.command(dict(action='start',id='command-123'))
  self.assertEqual(self.mt.sent,[])
 def test_mode_change_immediately_before_send(self):
  self.mt.mode_on_check=2
  with self.assertRaises(ValueError):self.send()
  self.assertEqual(self.mt.sent,[])
 def test_stop_does_not_close(self):
  self.b.running=True;self.b.command(dict(action='stop',id='command-123'))
  self.assertFalse(self.b.running);self.assertEqual(self.mt.sent,[])
 def test_start_has_no_retroactive_order(self):
  self.b.command(dict(action='start',id='command-123'))
  self.assertTrue(self.b.running);self.assertIsNone(self.b.engine.pending);self.assertEqual(self.mt.sent,[])
 def test_stale_dashboard_pauses(self):
  self.b.running=True;self.b.last_seen=time.time()-30;self.b.step();self.assertFalse(self.b.running)
 def test_one_position(self):
  self.mt.positions=[N()];self.send();self.assertEqual(self.mt.sent,[])
 def test_one_pending_order(self):
  self.mt.orders=[N()];self.send();self.assertEqual(self.mt.sent,[])
 def test_rounding_risk_and_protections(self):
  self.send();r=self.mt.sent[0];self.assertGreater(r['volume'],0);self.assertLess(r['sl'],r['price']);self.assertGreater(r['tp'],r['price'])
  loss=abs(self.mt.order_calc_profit(0,'EURUSD',r['volume'],r['price'],r['sl']-.00012))+7*r['volume'];self.assertLessEqual(loss,50.00001)
 def test_sell_protections(self):
  self.send(-1);r=self.mt.sent[0];self.assertGreater(r['sl'],r['price']);self.assertLess(r['tp'],r['price'])
 def test_duplicate_signal_not_retried(self):
  self.send();self.send();self.assertEqual(len(self.mt.sent),1)
 def test_uncertain_order_pauses_no_retry(self):
  self.mt.fail_send=True;self.b.running=True;self.send();self.send();self.assertFalse(self.b.running);self.assertEqual(len(self.mt.sent),1)
 def test_restart_remembers_signal(self):
  self.send();b=DemoBridge(self.mt,self.b.state_path,self.b.journal_path);b.submit(self.signal(),self.mt.symbol_info_tick(),self.mt.info);self.assertEqual(len(self.mt.sent),1)
 def test_daily_limit_persisted(self):
  self.mt.a.equity=9890;self.assertTrue(self.b.day_check(self.mt.a));b=DemoBridge(self.mt,self.b.state_path,self.b.journal_path);self.mt.a.equity=10000;self.assertTrue(b.day_check(self.mt.a))
 def test_risk_cap(self):
  with self.assertRaises(ValueError):self.b.command(dict(action='start',id='command-123',config=dict(risk=.02,daily_loss=.03)))
 def test_currency_rejected(self):
  self.mt.a.currency='EUR'
  with self.assertRaises(ValueError):self.b.account()
 def test_account_switch(self):
  self.b.pin=(123,'Demo');self.mt.a.login=456
  with self.assertRaises(ValueError):self.send()
 def test_no_snapshot_real_account_data(self):
  self.mt.a.trade_mode=2;d=self.b.snapshot();self.assertFalse(d['connected']);self.assertNotIn('account',d)
if __name__=='__main__':unittest.main()
