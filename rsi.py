# rsi.py
from typing import Optional

class RSI:
    """
    Wilderの平滑化で O(1) 更新
    last: float (0-100) / 初期化前は None
    """
    def __init__(self, period: int = 14):
        self.period = period
        self.avg_gain: Optional[float] = None
        self.avg_loss: Optional[float] = None
        self.prev_price: Optional[float] = None
        self.last: Optional[float] = None

    def init_prices(self, prices):
        # 最初の period+1 本で平均ゲイン/ロスを作る
        pts = prices[-(self.period+1):] if len(prices) >= self.period+1 else prices[:]
        gains = losses = 0.0
        for i in range(1, len(pts)):
            d = pts[i] - pts[i-1]
            if d >= 0: gains += d
            else:      losses -= d
        n = max(1, min(self.period, len(pts)-1))
        self.avg_gain = gains / n
        self.avg_loss = losses / n
        self.prev_price = pts[-1] if pts else None
        return self.update(self.prev_price) if self.prev_price is not None else None

    def update(self, price: float) -> Optional[float]:
        if self.prev_price is None:
            self.prev_price = price
            self.last = None
            return None
        change = price - self.prev_price
        gain = change if change > 0 else 0.0
        loss = -change if change < 0 else 0.0
        p = self.period
        if self.avg_gain is None: self.avg_gain = gain
        else: self.avg_gain = (self.avg_gain*(p-1) + gain)/p
        if self.avg_loss is None: self.avg_loss = loss
        else: self.avg_loss = (self.avg_loss*(p-1) + loss)/p
        self.prev_price = price

        if self.avg_loss == 0:
            self.last = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            self.last = 100.0 - 100.0/(1.0+rs)
        return self.last
