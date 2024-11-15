from abc import ABC

from python.scripts.metrics.market_imbalance import AssetInfo


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
