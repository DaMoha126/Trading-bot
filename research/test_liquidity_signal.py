import unittest
from liquidity_signal import signal

class TestSignal(unittest.TestCase):
    def call(self, previous, current, trend='up'):
        return signal(previous, current, 100, 110, trend, 0.1, 0.5)

    def test_buy_only_on_downward_cross(self):
        s = self.call(100, 99.9)
        self.assertEqual((s.side, s.stop, s.target), ('BUY', 99.4, 110))
        self.assertIsNone(self.call(99.9, 99.8))
        self.assertIsNone(self.call(99.8, 100))

    def test_sell_only_on_upward_cross(self):
        s = self.call(110, 110.1, 'down')
        self.assertEqual((s.side, s.stop, s.target), ('SELL', 110.6, 100))
        self.assertIsNone(self.call(110.1, 110.2, 'down'))

    def test_trend_and_bad_data(self):
        self.assertIsNone(self.call(100, 99.9, 'down'))
        self.assertIsNone(self.call(100, 99.9, 'none'))
        with self.assertRaises(ValueError):
            signal(100, float('nan'), 100, 110, 'up', .1, .5)

if __name__ == '__main__':
    unittest.main()
