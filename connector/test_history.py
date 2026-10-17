import unittest
from types import SimpleNamespace as N
from trade_history import aggregate_deals
from bridge import MAGIC

def deal(ticket,entry,volume,price,profit=0,commission=0,swap=0,fee=0,magic=MAGIC,pid=10,kind=0,reason=0,when=None):
 return N(ticket=ticket,entry=entry,volume=volume,price=price,profit=profit,commission=commission,swap=swap,fee=fee,magic=magic,position_id=pid,type=kind,reason=reason,time=when or ticket,time_msc=(when or ticket)*1000,symbol='EURUSD')
class HistoryTests(unittest.TestCase):
 def test_net_includes_entry_exit_costs(self):
  rows=[deal(1,0,.1,1.1,commission=-.35),deal(2,1,.1,1.102,profit=20,commission=-.35,swap=-1,fee=-.1,kind=1,reason=5)]
  h=aggregate_deals(rows,MAGIC);t=h['trades'][0];self.assertAlmostEqual(t['net'],18.2);self.assertEqual(t['reason'],'TP');self.assertEqual(h['stats']['count'],1)
 def test_partial_close_aggregates_only_when_complete(self):
  rows=[deal(1,0,.1,1.1),deal(2,1,.04,1.101,profit=4,kind=1)]
  self.assertEqual(aggregate_deals(rows,MAGIC)['trades'],[])
  rows.append(deal(3,1,.06,1.102,profit=12,kind=1));h=aggregate_deals(rows,MAGIC);self.assertEqual(len(h['trades']),1);self.assertEqual(h['trades'][0]['exit_deals'],2);self.assertAlmostEqual(h['trades'][0]['exit'],1.1016)
 def test_duplicates_do_not_double_count(self):
  rows=[deal(1,0,.1,1.1),deal(2,1,.1,1.101,profit=10,kind=1)]
  self.assertEqual(aggregate_deals(rows+rows,MAGIC)['stats']['net'],10)
 def test_manual_close_included(self):
  rows=[deal(1,0,.1,1.1),deal(2,1,.1,1.101,profit=10,kind=1,magic=0)]
  self.assertEqual(aggregate_deals(rows,MAGIC)['stats']['net'],10)
 def test_manual_addition_excluded(self):
  rows=[deal(1,0,.1,1.1),deal(2,0,.1,1.1,magic=0),deal(3,1,.2,1.101,profit=20,kind=1)]
  h=aggregate_deals(rows,MAGIC);self.assertEqual(h['excluded_mixed'],1);self.assertEqual(h['stats']['count'],0)
 def test_open_position_not_reported_closed(self):
  rows=[deal(1,0,.1,1.1),deal(2,1,.1,1.101,profit=10,kind=1)]
  self.assertEqual(aggregate_deals(rows,MAGIC,[10])['trades'],[])
 def test_missing_entry_and_reversal_not_invented(self):
  self.assertEqual(aggregate_deals([deal(2,1,.1,1.1)],MAGIC)['excluded_incomplete'],1)
  self.assertEqual(aggregate_deals([deal(2,2,.1,1.1)],MAGIC)['excluded_mixed'],1)
 def test_side_win_rate_and_expectancy(self):
  rows=[deal(1,0,.1,1.1),deal(2,1,.1,1.101,profit=10,kind=1),deal(3,0,.1,1.1,pid=11,kind=1),deal(4,1,.1,1.101,profit=-5,pid=11)]
  s=aggregate_deals(rows,MAGIC)['stats'];self.assertEqual(s['count'],2);self.assertEqual(s['win_rate'],.5);self.assertEqual(s['expectancy'],2.5);self.assertEqual(s['profit_factor'],2)
if __name__=='__main__':unittest.main()
