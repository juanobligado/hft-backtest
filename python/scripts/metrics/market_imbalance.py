from abc import ABC, abstractmethod
import numpy as np
from hftbacktest.binding import ROIVectorMarketDepth
from numba import float32


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
    def __init__(self, window_size: int, asset: AssetInfo, target_spread=0.025, cache_size: int = 30_000_000):
        super().__init__(window_size, cache_size)
        self.last_index = None
        self.asset = asset
        # spread target to calculate imbalance
        self.target_spread = target_spread
        # looking depth to calculate imbalance
        self.fair_offset_spread = None
        self.mean = None
        self.std = None
        self.alpha = None
        self.fair_price = None

    def update(self, market_data: ROIVectorMarketDepth):
        new_value = self.calculate(market_data)
        self.last_index = 0 if self.last_index is None else self.last_index + 1
        self.cache[self.last_index] = new_value
        from_index = max(0, self.last_index + 1 - self.window_size )
        to_index = self.last_index + 1
        self.mean = np.nanmean(self.cache[from_index:to_index])
        self.std = np.nanstd(self.cache[from_index:to_index])
        # alpha is imbalance timeseries standardized by the mean and standard deviation. [-1, 1]
        self.alpha = 0 if self.std == 0 else np.divide(new_value - self.mean, self.std)
        mid_price = (market_data.best_bid + market_data.best_ask) / 2.0
        self.fair_offset_spread = self.target_spread*mid_price
        self.fair_price = (market_data.best_bid + market_data.best_ask) / 2.0 + self.fair_offset_spread * self.alpha

    def calculate(self, market_data: ROIVectorMarketDepth):
        tick_size = self.asset.tick_size
        best_ask = market_data.best_ask
        best_bid = market_data.best_bid
        mid_price = (best_bid + best_ask) / 2.0
        sum_ask_qty = 0.0
        # calculate range in ticks to sum up ask qty
        from_tick = market_data.best_ask_tick
        # 2.5% + mid price (should be greater than best ask unless has a very large spread)
        upto_tick = max(int(np.floor(mid_price * (1 + self.target_spread) / tick_size)), from_tick)
        for price_tick in range(from_tick, upto_tick):
            sum_ask_qty += market_data.ask_qty_at_tick(price_tick)

        sum_bid_qty = 0.0
        from_tick = market_data.best_bid_tick
        complement = 1 - self.target_spread # 100% - self.looking depth
        upto_tick = min(int(np.ceil(mid_price * complement / tick_size)), from_tick)
        for price_tick in range(from_tick, upto_tick, -1):
            sum_bid_qty += market_data.bid_qty_at_tick(price_tick)

        return sum_bid_qty - sum_ask_qty
