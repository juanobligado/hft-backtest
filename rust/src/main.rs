mod strategy;

use algo::gridtrading;
use hftbacktest::{
    backtest::{
        assettype::LinearAsset,
        data::{read_npz_file, DataSource},
        models::{
            CommonFees,
            IntpOrderLatency,
            PowerProbQueueFunc3,
            ProbQueueModel,
            TradingValueFeeModel,
        },
        recorder::BacktestRecorder,
        Backtest,
        ExchangeKind,
        L2AssetBuilder,
    },
    prelude::{ApplySnapshot, Bot, HashMapMarketDepth},
};

mod algo;

fn prepare_backtest() -> Backtest<HashMapMarketDepth> {
}

fn main() {
    tracing_subscriber::fmt::init();

    let relative_half_spread = 0.0005;
    let relative_grid_interval = 0.0005;
    let grid_num = 10;
    let min_grid_step = 0.000001; // tick size
    let skew = relative_half_spread / grid_num as f64;
    let order_qty = 1.0;
    let max_position = grid_num as f64 * order_qty;

    let mut hbt = prepare_backtest();
    let mut recorder = BacktestRecorder::new(&hbt);
    gridtrading(
        &mut hbt,
        &mut recorder,
        relative_half_spread,
        relative_grid_interval,
        grid_num,
        min_grid_step,
        skew,
        order_qty,
        max_position,
    )
        .unwrap();
    hbt.close().unwrap();
    recorder.to_csv("gridtrading", ".").unwrap();
}