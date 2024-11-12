from abc import ABC, abstractmethod
import numpy as np
from numba import types
from numba.typed import Dict
from python.scripts.metrics.market_imbalance import MarketImbalance, AssetInfo
from hftbacktest import (
    BUY,
    SELL,
    GTX,
    LIMIT
)

class RiskManager(ABC):
    def __init__(self, asset: AssetInfo, bet_size = 50_000, max_usd_position = 1_000_000):
        self.asset = asset
        self.position = None
        self.orders = None
        self.bet_size = bet_size
        self.max_usd_position = max_usd_position

    def update_portfolio(self, hbt):
        self.position = hbt.position(self.asset.asset_no)
        self.orders = hbt.orders(self.asset.asset_no)

    def quote_to_base(self, quote_amount, price):
        # round to the nearest lot size
        rounded_base = round(( quote_amount / price) / self.asset.lot_size) * self.asset.lot_size
        # make sure it is at least the lot size
        return max(rounded_base, self.asset.lot_size)

    def calculate_max_allowed_quantity(self, price):
        return self.quote_to_base(self.max_usd_position, price)

    # Returns the current position as a percentage of the max allowed position
    def get_current_position_pct(self, price):
        if self.position is None:
            return None
        return self.position / self.calculate_max_allowed_quantity(price)

    def value_position(self, price):
        return 0 if self.position is None else self.position * price


class MarketImbalanceStrategy(ABC):
    def __init__(self, asset: AssetInfo, risk_manager: RiskManager, period_in_ns = 10_000_000_000, window_size = 3_600_000_000_000):
        self.period_in_ns = period_in_ns
        self.asset = asset
        self.risk_manager = risk_manager
        window = int(window_size / period_in_ns)
        self.imbalance_metric = MarketImbalance(window_size=window, asset=self.asset)

    def run(self, hbt, stat):
        while hbt.elapse(self.period_in_ns) == 0:
            asset_no = self.asset.asset_no
            hbt.clear_inactive_orders(asset_no)
            self.risk_manager.update_portfolio(hbt)
            # get the current depth
            market_data = hbt.depth(asset_no)
            # update the imbalance metric
            self.imbalance_metric.update(market_data)

            #--------------------------------------------------------
            # Computes bid price and ask price.
            mid_price = (market_data.best_bid + market_data.best_ask) / 2.0
            lot_size = self.asset.lot_size
            tick_size = self.asset.tick_size

            # Calculate the max position in terms of quantity
            normalized_position = self.risk_manager.get_current_position_pct(mid_price)

            # Calculate the max position in terms of quantity
            # adjust the fair price by some skew based on opened position %

            adjusted_fair_price = mid_price + 60*self.imbalance_metric.alpha - 3.5 * normalized_position
            half_spread = 30

            bid_price = min(np.round(adjusted_fair_price - half_spread), market_data.best_bid)
            bid_price = np.floor(bid_price / tick_size) * tick_size

            ask_price = max(np.round(adjusted_fair_price + half_spread), market_data.best_ask)
            ask_price = np.ceil(ask_price / tick_size) * tick_size

            #--------------------------------------------------------
            current_position_value = self.risk_manager.value_position(mid_price)
            max_position_value = self.risk_manager.max_usd_position

            # Creates a new grid for buy orders.
            new_bid_orders = Dict.empty(types.uint64, types.float64)


            if current_position_value < max_position_value and np.isfinite(bid_price):
                bid_price_tick = round(bid_price / tick_size)
                # order price in tick is used as order id.
                new_bid_orders[types.uint64(bid_price_tick)] = bid_price


            # Creates a new grid for sell orders.
            new_ask_orders = Dict.empty(types.uint64, types.float64)
            if current_position_value > -max_position_value and np.isfinite(ask_price):
                ask_price_tick = round(ask_price / tick_size)
                # order price in tick is used as order id.
                new_ask_orders[types.uint64(ask_price_tick)] = ask_price

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

            order_qty = max(round((self.risk_manager.bet_size / mid_price) / lot_size) * lot_size, lot_size)
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





