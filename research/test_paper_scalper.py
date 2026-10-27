import unittest
from paper_scalper import PaperScalper, Settings

class PaperTests(unittest.TestCase):
    def setUp(self):
        self.s = PaperScalper(10000, Settings(stop_distance=1, max_spread=.5))
    def q(self, time, bid, ask, **kwargs):
        self.s.quote(time,bid,ask,100,110,'up',**kwargs)
    def test_three_positions_share_risk(self):
        self.q(1,100.1,100.3); self.q(2,99.9,100.1)
        self.assertEqual(len(self.s.positions),3)
        self.assertLessEqual(self.s.events[-1][-1],50)
        self.q(3,99.8,100)
        self.assertEqual(len(self.s.positions),3)
    def test_choch_closes_and_cooldown(self):
        self.q(1,100.1,100.3);self.q(2,99.9,100.1)
        self.q(3,100.2,100.4,choch=True)
        self.assertEqual(len(self.s.positions),0)
        self.q(4,100.1,100.3);self.q(5,99.9,100.1)
        self.assertEqual(len(self.s.positions),0)
    def test_break_even_and_target(self):
        self.q(1,100.1,100.3);self.q(2,99.9,100.1)
        self.q(3,105.2,105.4)
        self.assertTrue(all(p.break_even for p in self.s.positions))
        self.q(4,110,110.2)
        self.assertEqual(len(self.s.positions),0)
    def test_spread_and_hours_block(self):
        self.q(1,100.1,100.3);self.q(2,99.9,100.6)
        self.assertFalse(self.s.positions)
        self.q(3,100.1,100.2);self.q(4,99.9,100.1,trading_hours=False)
        self.assertFalse(self.s.positions)
    def test_small_account_does_not_exceed_risk(self):
        self.s=PaperScalper(1)
        self.q(1,100.1,100.3);self.q(2,99.9,100.1)
        self.assertFalse(self.s.positions)
    def test_reject_out_of_order(self):
        self.q(1,100.1,100.3)
        with self.assertRaises(ValueError): self.q(1,99.9,100.1)

if __name__ == '__main__': unittest.main()
