import tempfile,time,unittest
from unittest.mock import patch
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace as N
from test_bridge import MT
from scalping_bridge import ScalpingBridge, MAGIC_SCALP

class GoldMT(MT):
 ACCOUNT_MARGIN_MODE_RETAIL_HEDGING=2
 TIMEFRAME_M1=1
 def __init__(self):
  super().__init__()
  self.a.margin_mode=2
  self.info=N(currency_base='XAU',currency_profit='USD',trade_tick_size=.01,point=.01,digits=2,trade_stops_level=1,trade_freeze_level=0,volume_step=.01,volume_min=.01,volume_max=100,filling_mode=1)
  self.tick=N(time=int(time.time()),time_msc=int(time.time()*1000),bid=100,ask=100.1)
 def symbol_info_tick(self,*args):return self.tick
 def order_calc_profit(self,kind,symbol,lot,entry,sl):return (sl-entry)*(1 if kind==0 else -1)*100*lot
 def order_calc_margin(self,*args):return 100
 def order_send(self,r):
  self.sent.append(r)
  if self.fail_send:return None
  if r['action']==self.TRADE_ACTION_DEAL and 'position' not in r:
   self.positions.append(N(ticket=len(self.sent),symbol='XAUUSD',magic=MAGIC_SCALP,type=r['type'],volume=r['volume'],price_open=r['price'],price_current=r['price'],sl=r['sl'],tp=r['tp'],profit=0))
  if 'position' in r and r['action']==self.TRADE_ACTION_DEAL:
   self.positions=[p for p in self.positions if p.ticket!=r['position']]
  return N(retcode=10009,price=r.get('price',100))
 def copy_rates_from_pos(self,*args):
  end=int(time.time())//60*60
  return [dict(time=end-i*60,open=100,high=101,low=99,close=100,spread=10) for i in range(80,0,-1)]

class TestScalp(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.mt=GoldMT();p=Path(self.tmp.name)
  self.b=ScalpingBridge(self.mt,p/'risk.json',p/'journal.jsonl');self.b.symbol='XAUUSD';self.b.day_check(self.mt.a)
 def tearDown(self):self.tmp.cleanup()
 def submit(self):self.b.submit_scalp('BUY',99,110,self.mt.tick,self.mt.info,'test-signal')
 def test_three_orders_share_risk_and_have_protection(self):
  self.submit();self.assertEqual(len(self.mt.sent),3)
  self.assertTrue(all(x['sl']<100 and x['tp']==110 for x in self.mt.sent))
  volume=sum(r['volume'] for r in self.mt.sent)
  worst=abs(self.mt.order_calc_profit(0,'XAUUSD',volume,100.2,98.9))+7*volume
  self.assertLessEqual(worst,50.00001)
 def test_real_and_netting_rejected(self):
  self.mt.a.trade_mode=2
  with self.assertRaises(ValueError):self.submit()
  self.mt.a.trade_mode=0;self.mt.a.margin_mode=0
  with self.assertRaises(ValueError):self.submit()
  self.assertEqual(self.mt.sent,[])
 def test_existing_position_and_tiny_balance_rejected(self):
  self.mt.positions=[N(magic=100,symbol='XAUUSD')];self.submit();self.assertFalse(self.mt.sent)
  self.mt.positions=[];self.mt.a.equity=1;self.b.risk['baseline']=1;self.submit();self.assertFalse(self.mt.sent)
 def test_uncertain_send_never_retried(self):
  self.mt.fail_send=True
  with self.assertRaises(ValueError):self.submit()
  self.mt.fail_send=False;self.submit()
  self.assertEqual(len(self.mt.sent),1)
 def test_close_only_owned_positions(self):
  self.submit(); foreign=N(ticket=100,magic=999,symbol='XAUUSD',type=0,volume=.01)
  self.mt.positions.append(foreign)
  self.b.close_owned(list(self.mt.positions),self.mt.tick,self.mt.info)
  self.assertEqual([p.ticket for p in self.mt.positions],[100])
 def test_mode_change_at_check_prevents_order(self):
  self.mt.mode_on_check=2
  with self.assertRaises(ValueError):self.submit()
  self.assertEqual(self.mt.sent,[])
 def test_signal_opens_during_market_cycle(self):
  class Clock(datetime):
   @classmethod
   def now(cls,tz=None):return datetime(2026,10,27,14,tzinfo=timezone.utc)
  self.b.command(dict(action='start',id='command-123',symbol='XAUUSD',supervision='autonomous'))
  self.b.last_structure=dict(trend='up',support=100,resistance=110,event=None)
  self.b.previous_bid=100.2;self.mt.tick=N(time=int(time.time()),time_msc=int(time.time()*1000),bid=99.9,ask=100)
  with patch('scalping_bridge.datetime',Clock):self.b.step()
  self.assertTrue(self.b.running,self.b.last_error);self.assertEqual(len(self.mt.sent),3)
 def test_break_even_moves_only_owned_stops(self):
  self.submit();self.mt.tick=N(time=int(time.time()),bid=106,ask=106.1)
  self.b.manage_break_even(self.mt.positions,self.mt.tick,self.mt.info)
  changes=[r for r in self.mt.sent if r['action']==self.mt.TRADE_ACTION_SLTP]
  self.assertEqual(len(changes),3)
  self.assertTrue(all(r['sl']>=100.1 for r in changes))
 def test_uncertain_close_is_not_treated_as_success(self):
  self.submit(); self.mt.fail_send=True
  with self.assertRaises(ValueError):self.b.close_owned(self.mt.positions,self.mt.tick,self.mt.info)
  self.assertEqual(len(self.mt.positions),3)
 def test_start_no_order(self):
  self.b.command(dict(action='start',id='command-123',symbol='XAUUSD'))
  self.assertTrue(self.b.running);self.assertEqual(self.mt.sent,[])

if __name__=='__main__':unittest.main()
