import unittest
from structure_m1 import Bar, StructureM1

def bar(t, high, low, close):
    return Bar(t,close,high,low,close)

class StructureTest(unittest.TestCase):
    def test_pivot_requires_future_closed_neighbours(self):
        s=StructureM1(1)
        s.feed(bar(0,11,9,10));s.feed(bar(60,12,8,10))
        self.assertEqual(s.highs,[]); self.assertEqual(s.lows,[])
        state=s.feed(bar(120,11,9,10))
        self.assertEqual(state['support'],8);self.assertEqual(state['resistance'],12)
        self.assertEqual(state['bar_close'],180)
    def test_choch_uses_close_not_wick(self):
        s=StructureM1(1);s.trend='up';s.lows=[(0,9)];s.highs=[(0,11)]
        self.assertIsNone(s.feed(bar(0,11,8,10))['event'])
        state=s.feed(bar(60,10,8,8.5))
        self.assertEqual(state['event'],'choch_down'); self.assertEqual(state['trend'],'down')
    def test_gap_clears_structure(self):
        s=StructureM1(1);s.feed(bar(0,11,9,10));s.trend='up';s.lows=[(0,9)]
        state=s.feed(bar(120,11,9,10))
        self.assertEqual(state['trend'],'none');self.assertIsNone(state['support'])
    def test_no_duplicate_bars(self):
        s=StructureM1();s.feed(bar(0,11,9,10))
        with self.assertRaises(ValueError):s.feed(bar(0,11,9,10))

if __name__=='__main__': unittest.main()
