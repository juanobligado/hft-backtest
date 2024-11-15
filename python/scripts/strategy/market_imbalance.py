import time
from abc import ABC

import hftbacktest
import numpy as np
from debugpy.common.timestamp import current
from numba import types
from numba.typed import Dict
from python.scripts.metrics.market_imbalance import MarketImbalance, AssetInfo
from python.scripts.helper.helper import nanosecond_timestamp_to_date
from hftbacktest import (
    BUY,
    SELL,
    GTX,
    LIMIT
)
from python.scripts.strategy.risk_manager import RiskManager




class MarketImbalanceStrategy(ABC):
    def __init__(self, asset: AssetInfo, risk_manager: RiskManager, period_in_ns = 10_000_000_000, window_size = 60):
        self.period_in_ns = period_in_ns
        self.asset = asset
        self.risk_manager = risk_manager
        self.imbalance_metric = MarketImbalance(self.asset,0.025, window_size)

    def run(self, hbt, recorder: hftbacktest.Recorder):
        stat = recorder.recorder
        lot_size = self.asset.lot_size
        tick_size = self.asset.tick_size
        asset_no = self.asset.asset_no
        start_time = time.time()
        print(f"[{hbt.current_timestamp}] Starting backtest with period")
        while hbt.elapse(self.period_in_ns) == 0:
            hbt.clear_inactive_orders(asset_no)
            self.risk_manager.update_portfolio(hbt)
            # get the current depth
            market_data = hbt.depth(asset_no)
            # update the imbalance metric
            self.imbalance_metric.update(market_data)

            #--------------------------------------------------------
            # Computes bid price and ask price.
            mid_price = (market_data.best_bid + market_data.best_ask) / 2.0


            # 0 - 1 with 0 being 100
            normalized_position = self.risk_manager.get_current_position_pct(mid_price)

            # Calculate the max position in terms of quantity
            # adjust the fair price by some skew based on opened position %

            adjusted_fair_price = self.imbalance_metric.fair_price - 3.5 * normalized_position
            half_spread = 0.0125*3000

            bid_price = min(np.round(adjusted_fair_price - half_spread), market_data.best_bid)
            bid_price = np.floor(bid_price / tick_size) * tick_size

            ask_price = max(np.round(adjusted_fair_price + half_spread), market_data.best_ask)
            ask_price = np.ceil(ask_price / tick_size) * tick_size


            #--------------------------------------------------------
            current_position_value = self.risk_manager.value_position(mid_price)
            max_position_value = self.risk_manager.max_usd_position

            # Creates a new grid for buy orders.
            new_bid_orders = Dict.empty(types.int64, types.float64)


            if current_position_value < max_position_value and np.isfinite(bid_price):
                bid_price_tick = round(bid_price / tick_size)
                # order price in tick is used as order id.
                new_bid_orders[types.int64(bid_price_tick)] = bid_price


            # Creates a new grid for sell orders.
            new_ask_orders = Dict.empty(types.int64, types.float64)
            if current_position_value > -max_position_value and np.isfinite(ask_price):
                ask_price_tick = round(ask_price / tick_size)
                # order price in tick is used as order id.
                new_ask_orders[types.int64(ask_price_tick)] = ask_price

            orders = self.risk_manager.orders
            order_values = orders.values()
            while order_values.has_next():
                order = order_values.get()
                # Cancels if a working order is not in the new grid.
                if order.cancellable:
                    if (
                        (order.side == BUY and order.order_id not in new_bid_orders)
                        or (order.side == SELL and order.order_id not in new_ask_orders)
                    ):
                        hbt.cancel(asset_no, order.order_id, False)

            order_qty = max( lot_size*round((self.risk_manager.bet_size / mid_price) / lot_size), lot_size)
            if stat.i % 100 == 0:
                current_time = nanosecond_timestamp_to_date(hbt.current_timestamp)
                print(f" [{current_time}]  mkt_status: {self.imbalance_metric.get_status_description()} order_size:{order_qty}  position: {self.risk_manager.position} normalized_position: {normalized_position}  mid_price: {mid_price}, fair_price: {self.imbalance_metric.fair_price} bid_order_price: {bid_price}, ask_order_price: {ask_price}")
            for order_id, order_price in new_bid_orders.items():
                # Posts a new buy order if there is no working order at the price on the new grid.
                if order_id not in orders:
                    hbt.submit_buy_order(asset_no, order_id, order_price, order_qty, GTX, LIMIT, False)

            for order_id, order_price in new_ask_orders.items():
                # Posts a new sell order if there is no working order at the price on the new grid.
                if order_id not in orders:
                    order_qty = self.risk_manager.calculate_max_allowed_quantity(order_price)
                    hbt.submit_sell_order(asset_no, order_id, order_price, order_qty, GTX, LIMIT, False)
            #
            stat.record(hbt)
        print(f"Backtest took {time.time() - start_time} seconds")




