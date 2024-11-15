import numpy as np
from hftbacktest import (
    BacktestAsset,
    HashMapMarketDepthBacktest,
    Recorder
)
import os
import sys
# Set the project root directory
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
print(f"Project root: {project_root}")
sys.path.insert(0, project_root)

from strategy.market_imbalance import (
    MarketImbalanceStrategy,
    AssetInfo,
    RiskManager
)

def read_backtest_asset(mkt_data_files, mkt_data_initial_snapshot, latency_files = None):
    asset = None
    if latency_files is not None:
        print("Initializing backtest asset with latency")
        asset = (
            BacktestAsset()
                .data(mkt_data_files)
                .initial_snapshot(mkt_data_initial_snapshot)
                .linear_asset(1.0)
                .intp_order_latency(latency_files)
                .risk_adverse_queue_model()
                .no_partial_fill_exchange()
                .trading_value_fee_model(-0.00005, 0.0007)
                .tick_size(0.01)
                .lot_size(0.001)
        )
    else:
        print("Initializing backtest asset without latency")
        asset = (
            BacktestAsset()
            .data(mkt_data_files)
            .initial_snapshot(mkt_data_initial_snapshot)
            .linear_asset(1.0)
            .risk_adverse_queue_model()
            .no_partial_fill_exchange()
            .trading_value_fee_model(-0.00005, 0.0007)
            .tick_size(0.01)
            .lot_size(0.001)
        )
    return asset

def run_backtest(mkt_data_initial_snapshot, mkt_data_files, latency_files=None, output_filename='output.npz'):
    print("Initializing backtest asset")

    asset = read_backtest_asset( mkt_data_files, mkt_data_initial_snapshot ,latency_files)
    hbt = HashMapMarketDepthBacktest([asset])
    recorder = Recorder(1, 30_000_000)
    depth = hbt.depth(0)
    asset_info = AssetInfo(0, depth.tick_size, depth.lot_size)
    risk_manager = RiskManager(asset_info, 1_000,1_000_000)
    interval = 1_000_000_000  # 1s
    strategy = MarketImbalanceStrategy(asset_info, risk_manager, interval, window_size=120)
    print("Running backtest...")
    strategy.run(hbt, recorder)
    print("Backtest Run completed...")
    hbt.close()
    print(f"Saving output to {output_filename}")
    recorder.to_npz(output_filename)
    recorder.stats()
    return recorder

if __name__ == "__main__":
    mkt_data_initial_snapshot = np.load('../data/usdm/ethusdt_20240730_eod_snapshot.npz')['data']
    mkt_data_files = [
        '../data/usdm/ethusdt_20240731.npz',
    ]
    latency_files = [
        '../latency/ethusdt_20240731_latency.npz',
    ]
    run_backtest(mkt_data_initial_snapshot, mkt_data_files, None, '../output/backtest_run_no_latency.npz')
    #run_backtest(mkt_data_initial_snapshot, mkt_data_files, latency_files, '../../output/backtest_run_with_latency.npz')