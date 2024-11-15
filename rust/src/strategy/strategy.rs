use std::{collections::HashMap, fmt::Debug};
use std::time::Instant;
use hftbacktest::prelude::*;
use tracing::{info, warn};

pub fn obi_strategy<MD, I, R>(
    hbt: &mut I,
    recorder: &mut R,
    order_qty: f64,
    max_position: f64,
) -> Result<(), i64>
where
    MD: MarketDepth,
    I: Bot<MD>,
    <I as Bot<MD>>::Error: Debug,
    R: Recorder,
    <R as Recorder>::Error: Debug,
{
    let tick_size = hbt.depth(0).tick_size();
    let mut int = 0;
    info!("[{}] starting wait cycle..", hbt.current_timestamp());
    let mut sw = Instant::now();
    while let Ok(elapsed) = hbt.elapse(10_000_000_000) {
        if int == 0 {
            info!("{} elapsed warming up data...", sw.elapsed().as_secs_f64());
            sw = Instant::now();
        }
        int += 1;
        match recorder.record(hbt) {
            Err(e) => {
                warn!("Failed to record step {}: {:?}", hbt.current_timestamp(), e);
            }
            _ => {}
        }
        if !elapsed {
            break;
        }
        let depth = hbt.depth(0);
        let position = hbt.position(0);


       // Prints every 1-min.

        if depth.best_bid_tick() == INVALID_MIN || depth.best_ask_tick() == INVALID_MAX {
            // Market depth is incomplete.
            continue;
        }

        let mid_price = (depth.best_bid() + depth.best_ask()) as f64 / 2.0;
        let normalized_position = position / order_qty;

        // Calculate market imbalance
        let spread = 0.025;
        // add v_bid and v_ask
        let from_bid_range = depth.best_bid_tick();
        let min_bid_ticks = (mid_price*(1.0-spread) / tick_size ).ceil() as i64;
        let mut v_bid: f64 = 0.0;
        for bid_tick in min_bid_ticks..=from_bid_range {
            v_bid += depth.bid_qty_at_tick(bid_tick);
        }
        let from_ask_range = depth.best_ask_tick();
        let max_ask_ticks = (mid_price*(1.0+spread) / tick_size ).floor() as i64;
        let mut v_ask: f64 = 0.0;
        for ask_tick in from_ask_range..=max_ask_ticks {
            v_ask += depth.ask_qty_at_tick(ask_tick);
        }

        let market_imbalance = (v_bid - v_ask) / (v_bid + v_ask);

        let min_tick = depth.tick_size() as f64;
        let relative_half_spread = 0.00125;
        let skew = 0.0;
        let relative_bid_depth = relative_half_spread + skew * normalized_position;
        let relative_ask_depth = relative_half_spread - skew * normalized_position;
        let alpha = market_imbalance*spread*mid_price;
        let forecast_mid_price = mid_price + alpha;

        let bid_price =
            (forecast_mid_price * (1.0 - relative_bid_depth)).min(depth.best_bid() as f64);
        let ask_price =
            (forecast_mid_price * (1.0 + relative_ask_depth)).max(depth.best_ask() as f64);


        let bid_price = (bid_price / min_tick).floor() * min_tick;
        let ask_price = (ask_price / min_tick).ceil() * min_tick ;

        //--------------------------------------------------------
        // Updates quotes

        hbt.clear_inactive_orders(Some(0));

        {
            let orders = hbt.orders(0);
            let mut new_bid_orders = HashMap::new();
            if position < max_position && bid_price.is_finite() {
                let bid_price_tick = (bid_price / tick_size).round() as u64;
                new_bid_orders.insert(bid_price_tick, bid_price);
            }
            // Cancels if an order is not in the new grid.
            let cancel_order_ids: Vec<u64> = orders
                .values()
                .filter(|order| {
                    order.side == Side::Buy
                        && order.cancellable()
                        && !new_bid_orders.contains_key(&order.order_id)
                })
                .map(|order| order.order_id)
                .collect();
            // Posts an order if it doesn't exist.
            let new_orders: Vec<(u64, f64)> = new_bid_orders
                .into_iter()
                .filter(|(order_id, _)| !orders.contains_key(&order_id))
                .map(|v| v)
                .collect();
            for order_id in cancel_order_ids {
                hbt.cancel(0, order_id, false).unwrap();
            }
            for (order_id, order_price) in new_orders {
                hbt.submit_buy_order(
                    0,
                    order_id,
                    order_price,
                    order_qty,
                    TimeInForce::GTX,
                    OrdType::Limit,
                    false,
                )
                    .unwrap();
            }
        }

        {
            let orders = hbt.orders(0);
            let mut new_ask_orders = HashMap::new();
            if position > -max_position && ask_price.is_finite() {
                let ask_price_tick = (ask_price / tick_size).round() as u64;
                new_ask_orders.insert(ask_price_tick, ask_price);
            }
            // Cancels if an order is not in the new grid.
            let cancel_order_ids: Vec<u64> = orders
                .values()
                .filter(|order| {
                    order.side == Side::Sell
                        && order.cancellable()
                        && !new_ask_orders.contains_key(&order.order_id)
                })
                .map(|order| order.order_id)
                .collect();
            // Posts an order if it doesn't exist.
            let new_orders: Vec<(u64, f64)> = new_ask_orders
                .into_iter()
                .filter(|(order_id, _)| !orders.contains_key(&order_id))
                .map(|v| v)
                .collect();
            for order_id in cancel_order_ids {
                hbt.cancel(0, order_id, false).unwrap();
            }
            for (order_id, order_price) in new_orders {
                hbt.submit_sell_order(
                    0,
                    order_id,
                    order_price,
                    order_qty,
                    TimeInForce::GTX,
                    OrdType::Limit,
                    false,
                )
                    .unwrap();
            }
            if int % 3600 == 0 {
                info!(
                    "[{}] mid_price: {:.2}, bid_price: {:.2}, ask_price: {:.2}, position: {:.2}, v_bid: {:.2}, v_ask: {:.2}, market_imbalance: {:.2}, alpha: {:.2}, forecast_mid_price: {:.2}",
                    hbt.current_timestamp(),
                    mid_price,
                    bid_price,
                    ask_price,
                    position,
                    v_bid,
                    v_ask,
                    market_imbalance,
                    alpha,
                    forecast_mid_price
                );
            }
        }
    }
    info!("Finished backtest. Elapsed time: {}s", sw.elapsed().as_secs_f64());
    Ok(())
}
