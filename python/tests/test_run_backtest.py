import numpy as np
import unittest
from hftbacktest import BacktestAsset
from python.scripts.strategy.market_imbalance import MarketImbalanceStrategy,AssetInfo, RiskManager
from hftbacktest import (
    Recorder
)
from hftbacktest.stats import LinearAssetRecord
from hftbacktest import HashMapMarketDepthBacktest


class TestRunBackTest(unittest.TestCase):

    def test_run_backtest(self):
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
        recorder = Recorder(1, 30_000_000)

        depth = hbt.depth(0)
        asset_info = AssetInfo(0,depth.tick_size,depth.lot_size)
        risk_manager = RiskManager(asset_info, 1_000_000)
        interval = 1_000_000_000 # 1s
        window = 3_600_000_000_000 / interval # 1hour
        strategy = MarketImbalanceStrategy(asset_info, risk_manager, interval)
        strategy.run(hbt,recorder.recorder)

        hbt.close()


if __name__ == '__main__':
    unittest.main()