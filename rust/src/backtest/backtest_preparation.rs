use hftbacktest::{
    backtest::{
        assettype::LinearAsset,
        data::{read_npz_file, DataSource},
        models::{CommonFees, ConstantLatency, RiskAdverseQueueModel, TradingValueFeeModel},
        Backtest, ExchangeKind, L2AssetBuilder,
    },
    prelude::{ApplySnapshot, HashMapMarketDepth},
};
use tracing::{debug, error, info};

pub fn prepare_backtest() -> Result<Backtest<HashMapMarketDepth>, Box<dyn std::error::Error>> {
    let asset_type = LinearAsset::new(1.0);
    let queue_model = RiskAdverseQueueModel::new();
    let data_references = vec![DataSource::File(
        "../data/usdm/ethusdt_20240731.npz".to_string(),
    )];
    debug!("Reading snapshot file...");
    let depth = || {
        let mut depth = HashMapMarketDepth::new(0.01, 0.001);
        match read_npz_file("../data/usdm/ethusdt_20240730_eod_snapshot.npz", "data") {
            Ok(snapshot) => {
                depth.apply_snapshot(&snapshot);
            }
            Err(e) => {
                error!("Failed to read snapshot file: {}", e);
            }
        }
        depth
    };
    debug!("Building L2Asset...");
    let asset = L2AssetBuilder::new()
        .latency_offset(0)
        .latency_model(ConstantLatency::new(0, 0))
        .asset_type(asset_type)
        .fee_model(TradingValueFeeModel::new(CommonFees::new(-0.00005, 0.0007)))
        .exchange(ExchangeKind::NoPartialFillExchange)
        .queue_model(queue_model) // Ensure queue_model is provided
        .depth(depth)
        .data(data_references.clone())
        .build()
        .map_err(|e| {
            error!("Failed to build asset: {:?}", e);
            e
        })?;
    debug!(
        "L2Asset built successfully with data: {:?}",
        data_references
    );

    let hbt = Backtest::builder().add_asset(asset).build().map_err(|e| {
        error!("Failed to build backtest: {:?}", e);
        e
    })?;
    debug!("Backtest built successfully.");
    Ok(hbt)
}
