import unittest
from replay_m1 import ReplayM1
from structure_m1 import Bar

class ReplayTest(unittest.TestCase):
    def test_unfinished_and_past_bar_rejected(self):
        r=ReplayM1(10000)
        with self.assertRaises(ValueError):r.bar_closed(Bar(0,10,11,9,10),59)
        r.tick(180,10,10.1)
        with self.assertRaises(ValueError):r.bar_closed(Bar(0,10,11,9,10),60)
    def test_without_levels_no_entry(self):
        r=ReplayM1(10000)
        r.tick(60,10,10.1);r.tick(61,9.8,9.9)
        self.assertEqual(r.paper.positions,[])
    def test_change_of_structure_invalidates_cross(self):
        r=ReplayM1(10000)
        r.paper.previous_bid=10
        r.bar_closed(Bar(0,10,11,9,10),60)
        self.assertIsNone(r.paper.previous_bid)

if __name__=='__main__': unittest.main()
