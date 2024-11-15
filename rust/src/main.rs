use strategy::strategy::obi_strategy;
use backtest::backtest_preparation::prepare_backtest;
use hftbacktest::{
    backtest::{
        recorder::BacktestRecorder,
    },
};
use tracing::{error, info};

mod strategy;
mod backtest;

fn main() {
    tracing_subscriber::fmt::init();
    let order_qty = 1.0;
    let max_position = 2.5;
    match prepare_backtest() {
        Ok(mut hbt) => {
            let mut recorder = BacktestRecorder::new(&hbt);
            info!("Running OBI strategy... initial data...");
            obi_strategy(
                &mut hbt,
                &mut recorder,
                order_qty,
                max_position,
            ).unwrap();
            recorder.to_csv("rust_output.csv", "../output").unwrap();
        },
        Err(e) => {
            error!("Failed to prepare backtest data: {:?}", e);
            return;
        }
    }


}