# bb.py
from collections import deque
from typing import Optional, Dict
import math

class BollingerBands:
    """
    ボリンジャーバンドを高速に計算するクラス
    last には ±1σ, ±2σ, σ も含める
    """
    def __init__(self, window: int = 20, k: float = 2.0):
        self.window = window
        self.k = k  # デフォルトは ±2σ
        self.buf = deque(maxlen=window)
        self.sum = 0.0
        self.sumsq = 0.0
        self.last: Optional[Dict[str, float]] = None

    def init_prices(self, prices):
        for p in prices[-self.window:]:
            self.buf.append(p)
            self.sum += p
            self.sumsq += p * p
        return self.update(self.buf[-1]) if self.buf else None

    def update(self, price: float) -> Optional[Dict[str, float]]:
        # 古いデータを削除
        if len(self.buf) == self.window:
            old = self.buf[0]
            self.sum -= old
            self.sumsq -= old * old

        # 新しいデータを追加
        self.buf.append(price)
        self.sum += price
        self.sumsq += price * price

        n = len(self.buf)
        if n == 0:
            self.last = None
            return None

        # 平均と標準偏差
        mid = self.sum / n
        var = max(self.sumsq / n - mid * mid, 0.0)
        std = math.sqrt(var)

        # ±1σ, ±2σ
        upper_1 = mid + std
        lower_1 = mid - std
        upper_2 = mid + 2 * std
        lower_2 = mid - 2 * std

        # ±kσ（従来通り）
        upper_k = mid + self.k * std
        lower_k = mid - self.k * std

        # バンド幅と価格の位置
        width = upper_k - lower_k
        pct_b = (price - lower_k) / width if width > 0 else 0.5

        self.last = {
            "mid": mid,
            "std": std,
            "upper_1": upper_1,
            "lower_1": lower_1,
            "upper_2": upper_2,
            "lower_2": lower_2,
            "upper_k": upper_k,
            "lower_k": lower_k,
            "width": width,
            "pct_b": pct_b,
        }
        return self.last
