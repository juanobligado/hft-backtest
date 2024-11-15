import unittest
from hftbacktest import (BacktestAsset, HashMapMarketDepthBacktest)
import numpy as np

from python.scripts.metrics.market_imbalance import MarketImbalance, AssetInfo
from unittest.mock import MagicMock, patch, PropertyMock


class TestRunBackTest(unittest.TestCase):
    def setUp(self):
        self.asset = AssetInfo(0, 0.01, 0.001)
        self.expected_spread = 0.025
        self.metric = MarketImbalance(self.asset, self.expected_spread, 60)

    def test_calc_ask_range(self):
        with patch('hftbacktest.binding.HashMapMarketDepthBacktest') as MockHashMapMarketDepth:
            market_data = MockHashMapMarketDepth.return_value
            type(market_data).best_bid = PropertyMock(return_value=990.0)
            type(market_data).best_ask = PropertyMock(return_value=1000.0)
            type(market_data).best_ask_tick = PropertyMock(return_value=int(1010.0 / self.asset.tick_size))
            expected_range = range(101000,102500)
            actual_range = self.metric.get_ask_range(market_data, 1000.0)
            self.assertEqual(list(actual_range), list(expected_range) )

    def test_calc_bid_range(self):
        with patch('hftbacktest.binding.HashMapMarketDepthBacktest') as MockHashMapMarketDepth:
            market_data = MockHashMapMarketDepth.return_value
            type(market_data).best_bid = PropertyMock(return_value=990.0)
            type(market_data).best_ask = PropertyMock(return_value=1000.0)
            type(market_data).best_ask_tick = PropertyMock(return_value=int(1010.0 / self.asset.tick_size))
            type(market_data).best_bid_tick = PropertyMock(return_value=int(990.0 / self.asset.tick_size))
            expected_range = range(99000,97500,-1)
            actual_range = self.metric.get_bid_range(market_data, 1000.0)
            self.assertEqual(list(actual_range), list(expected_range) )


    def test_market_imbalance(self):
        ethusdt_20240731 = np.load('../../data/usdm/ethusdt_20240731.npz')['data']
        ethusdt_20240730_eod = np.load('../../data/usdm/ethusdt_20240730_eod_snapshot.npz')['data']

        #TODO: Implement a better latency model

        constant_latency_ns = 10_000_000
        asset = (
            BacktestAsset()
                .data([ethusdt_20240731])
                .initial_snapshot(ethusdt_20240730_eod)
                .linear_asset(1.0)
                .constant_latency(constant_latency_ns, constant_latency_ns)
                .risk_adverse_queue_model()
                .no_partial_fill_exchange()
                .trading_value_fee_model(0.0002, 0.0007)
                .tick_size(0.01)
                .lot_size(0.001)
        )
        hbt = HashMapMarketDepthBacktest([asset])
        market_data = hbt.depth(0)
        asset_info = AssetInfo(0, market_data.tick_size, market_data.lot_size)
        metric = MarketImbalance(asset_info)
        result = metric.calculate(market_data)
        self.assertLess(result, 1)
        self.assertGreater(result,-1)
        hbt.close()