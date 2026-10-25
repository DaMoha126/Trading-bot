"""Gold contract and execution guards, using a simulated MT5 API only."""
import math
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace as N
from bridge import DemoBridge
from strategy import Config, Engine
from test_bridge import MT


class GoldMT(MT):
    def __init__(self):
        super().__init__()
        self.info=N(currency_base='XAU',currency_profit='USD',trade_tick_size=.05,
                    point=.01,digits=2,trade_stops_level=20,volume_step=.01,
                    volume_min=.01,volume_max=20,filling_mode=1)
        self.stale=False

    def symbol_info_tick(self,*args):
        return N(time=int(time.time())-(60 if self.stale else 0),bid=2700.,ask=2700.30)

    def order_calc_profit(self,kind,symbol,lot,entry,sl):
        return (sl-entry)*(1 if kind==0 else -1)*100*lot

    def copy_rates_from_pos(self,*args):
        end=int(time.time())//180*180
        return [dict(time=end-i*180,open=2700.,high=2702.,low=2698.,close=2700.,spread=30)
                for i in range(80,0,-1)]


class GoldTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();p=Path(self.temp.name)
        self.mt=GoldMT();self.b=DemoBridge(self.mt,p/'risk.json',p/'journal.jsonl',instrument='XAUUSD')
        self.b.day_check(self.mt.a)

    def tearDown(self):
        self.temp.cleanup()

    def test_gold_start_and_suffix_without_order(self):
        self.b.command(dict(action='start',id='gold-start-001',symbol='XAUUSD.a'))
        self.assertTrue(self.b.running);self.assertEqual(self.b.cfg.symbol,'XAUUSD')
        self.assertEqual(self.b.snapshot()['price_digits'],2);self.assertEqual(self.mt.sent,[])

    def test_forex_and_silver_rejected(self):
        for base in ('EUR','XAG'):
            self.mt.info.currency_base=base
            with self.assertRaises(ValueError):self.b.command(dict(action='start',id='gold-wrong-001'))
        self.assertEqual(self.mt.sent,[])

    def test_stale_quote_rejected(self):
        self.mt.stale=True
        with self.assertRaisesRegex(ValueError,'Cotation'):self.b.command(dict(action='start',id='gold-stale-001'))
        self.assertFalse(self.b.running);self.assertEqual(self.mt.sent,[])

    def test_buy_sell_budget_and_tick_rounding(self):
        for side in (1,-1):
            self.mt.sent.clear()
            self.b.submit(dict(id='gold-signal-'+str(side),side=side,stop=2695.03 if side==1 else 2705.02,
                               ready=int(time.time())-2),self.mt.symbol_info_tick(),self.mt.info)
            r=self.mt.sent[0]
            self.assertAlmostEqual(r['sl']/.05,round(r['sl']/.05))
            self.assertAlmostEqual(r['tp']/.05,round(r['tp']/.05))
            self.assertGreater(side*(r['price']-r['sl']),0)
            self.assertGreater(side*(r['tp']-r['price']),0)
            worst=r['sl']-side*(.10+10*self.mt.info.point)
            loss=abs(self.mt.order_calc_profit(r['type'],self.b.symbol,r['volume'],r['price'],worst))+7*r['volume']
            self.assertLessEqual(loss,50.00001)

    def test_minimum_lot_over_budget_refused(self):
        self.mt.info.volume_min=5
        self.b.submit(dict(id='gold-minimum-001',side=1,stop=2695.,ready=int(time.time())-2),self.mt.symbol_info_tick(),self.mt.info)
        self.assertEqual(self.mt.sent,[])

    def test_nan_risk_calculation_refused(self):
        self.mt.order_calc_profit=lambda *args:math.nan
        with self.assertRaises(ValueError):
            self.b.submit(dict(id='gold-nan-001',side=1,stop=2695.,ready=int(time.time())-2),self.mt.symbol_info_tick(),self.mt.info)
        self.assertEqual(self.mt.sent,[])

    def test_gold_candles_and_simulator_guard(self):
        result=self.b.candles()
        self.assertEqual(result['symbol'],'XAUUSD');self.assertAlmostEqual(result['bars'][0]['spread'],.30)
        with self.assertRaises(ValueError):Engine(Config(mode='mt5',symbol='XAUUSD')).feed(None)
        with self.assertRaises(ValueError):Config(symbol='XAUUSD')

if __name__=='__main__':unittest.main()
