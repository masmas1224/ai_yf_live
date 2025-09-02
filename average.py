# average.py
from collections import deque
from typing import Optional, Iterable

class MovingAverage:
    """
    価格は外から渡してね（fetcher担当）。私は“計算だけ”する子。
    ・init_prices() … 起動直後に過去データを流し込み
    ・update()      … 新しい価格を1つ渡すと最新SMAを返す（O(1)）
    ・ready()       … 窓(window)が満タンになったかチェック
    ・latest()      … 直近の移動平均値を返す
    ・reset()       … バッファ初期化
    """

    def __init__(self, window: int = 25):
        if window <= 0:
            raise ValueError("window must be positive")
        self.window = window
        self.buf: deque[float] = deque(maxlen=window)
        self.sum: float = 0.0
        self._latest_ma: Optional[float] = None

    # ---- 起動直後：過去データでウォームアップ ---------------------------------
    def init_prices(self, prices: Iterable[float]) -> Optional[float]:
        """
        過去価格をまとめて投入。最新の window 本だけ使う。
        戻り値は現時点の移動平均（十分な本数が無くても部分平均を返す）。
        """
        self.reset()
        # 直近 window 本だけ反映
        cache = list(prices)[-self.window:]
        for p in cache:
            self.buf.append(p)
            self.sum += p
        n = len(self.buf)
        self._latest_ma = (self.sum / n) if n > 0 else None
        return self._latest_ma

    # ---- ランタイム：1ティックずつ更新 ---------------------------------------
    def update(self, price: float) -> Optional[float]:
        """
        新しい価格を1つ受け取り、最新SMAを返す。
        バッファが満タンなら一番古い値の分だけ合計から引いてから追加。
        """
        if len(self.buf) == self.buf.maxlen:
            # これから自動で左端が落ちるので、その分を先に引く
            self.sum -= self.buf[0]
        self.buf.append(price)
        self.sum += price

        n = len(self.buf)
        self._latest_ma = (self.sum / n) if n > 0 else None
        return self._latest_ma

    # ---- ユーティリティ -------------------------------------------------------
    def ready(self) -> bool:
        """window 本そろって“完全なSMA”になったか？"""
        return len(self.buf) == self.window

    def latest(self) -> Optional[float]:
        """直近の移動平均値（更新済み）を返す"""
        return self._latest_ma

    def reset(self):
        """バッファを空っぽにして再スタート"""
        self.buf.clear()
        self.sum = 0.0
        self._latest_ma = None
