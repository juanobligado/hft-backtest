from abc import ABC, abstractmethod
import numpy as np
from hftbacktest.binding import ROIVectorMarketDepth


class Metric(ABC):
     def __init__(self,window_size: int, cache_size: int = 30_000_000):
         self.window_size = window_size
         #Pre-allocate cache so we don't have to reallocate memory
         self.cache = np.full(cache_size, np.nan, np.float64)
         self.last_index = 0

     @abstractmethod
     def calculate(self, market_data: ROIVectorMarketDepth) -> float:
        pass



class AssetInfo:
    def __init__(self, asset_no, tick_size, lot_size):
        self.asset_no = asset_no
        self.tick_size = tick_size
        self.lot_size = lot_size

class MarketImbalance(Metric):
    def __init__(self, asset: AssetInfo, target_spread=0.025, window_size: int = 60, cache_size: int = 30_000_000):
        print(asset)
        super().__init__(window_size, cache_size)
        self.last_index = None
        self.asset = asset
        # spread target to calculate imbalance
        self.target_spread = target_spread
        self.last_value = None
        self.last_mid = None
        # looking depth to calculate imbalance
        self.mean = None
        self.std = None
        self.alpha = None
        self.fair_price = None

    def update(self, market_data: ROIVectorMarketDepth):
        self.last_value = self.calculate(market_data)
        self.last_index = 0 if self.last_index is None else self.last_index + 1
        self.cache[self.last_index] = self.last_value
        from_index = max(0, self.last_index + 1 - self.window_size )
        to_index = self.last_index + 1
        self.mean = np.nanmean(self.cache[from_index:to_index])
        self.std = np.nanstd(self.cache[from_index:to_index])
        # alpha is imbalance timeseries standardized by the mean and standard deviation. [-1, 1]
        self.alpha = 0 if self.std == 0 else np.divide(self.last_value - self.mean, self.std)

        # we calculate the fair price as the mid price plus the offset spread times the market imbalance
        self.fair_price = self.last_mid*( 1.0 + 10*self.asset.tick_size * self.last_value)

    def calculate(self, market_data: ROIVectorMarketDepth):
        best_ask = market_data.best_ask
        best_bid = market_data.best_bid
        self.last_mid = (best_bid + best_ask) / 2.0

        sum_bid_qty = self.calculate_bid_volume(market_data, self.last_mid)
        sum_ask_qty = self.calculate_ask_volume(market_data, self.last_mid)
        # return the imbalance V_t = (Bid_volume_t - Ask_volume_t) / (Bid_volume_t + Ask_volume_t)
        return (sum_bid_qty - sum_ask_qty) / (sum_bid_qty + sum_ask_qty)

    def get_bid_range(self, market_data, mid_price):
        from_tick = market_data.best_bid_tick
        min_bid_ticks = int(np.ceil(mid_price * (1.0 - self.target_spread) / self.asset.tick_size))
        return range(from_tick, min(min_bid_ticks, from_tick), -1)

    def get_ask_range(self, market_data, mid_price):
        from_tick = market_data.best_ask_tick
        max_ask_ticks = int(np.floor(mid_price * (1.0 + self.target_spread) / self.asset.tick_size))
        upto_tick = max(max_ask_ticks, from_tick)
        return range(from_tick, upto_tick)

    def calculate_bid_volume(self, market_data: ROIVectorMarketDepth, mid_price: float):
        bid_range = self.get_bid_range(market_data, mid_price)
        sum_bid_qty = 0.0
        for price_tick in bid_range:
            sum_bid_qty += market_data.bid_qty_at_tick(price_tick)*price_tick
        return sum_bid_qty

    def calculate_ask_volume(self, market_data: ROIVectorMarketDepth, mid_price: float):
        bid_range = self.get_ask_range(market_data, mid_price)
        sum_ask_qty = 0.0
        for price_tick in bid_range:
            sum_ask_qty += market_data.ask_qty_at_tick(price_tick)*price_tick
        return sum_ask_qty

    # Returns a friendly name for last metric value
    def get_status_description(self):
        if self.last_value is None:
            return "No data"
        elif self.last_value > 0.5:
            return "Strong Buy"
        elif self.last_value > 0.10:
            return "Buy"
        elif self.last_value < -0.5:
            return "Strong Sell"
        elif self.last_value < -0.10:
            return "Sell"
        else:
            return "Neutral"