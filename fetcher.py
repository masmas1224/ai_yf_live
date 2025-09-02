# fetcher.py
import time
from typing import List, Tuple, Optional
import pandas as pd
import yfinance as yf

class PriceFetcher:
    """
    価格取得専任クラス（yfinance）
      - get_initial_prices(): 初期の履歴データ（終値リスト）を取得
      - update(): 最新1本を取得して (ts, price) を返す
      - stream(): 差分だけ連続で流すジェネレータ（任意）
    """
    def __init__(self, pair: str = "USDJPY=X", interval: str = "1m"):
        self.pair = pair
        self.interval = interval
        self.df = pd.DataFrame()
        self.latest_price: Optional[float] = None
        self.latest_ts: Optional[pd.Timestamp] = None

    # ------- 初回：履歴一括取得 -------
    def get_initial_prices(self, period: str = "7d") -> List[float]:
        """
        履歴を一気に取得して、内部キャッシュに格納しつつ終値リストを返す
        例) interval=1m の場合、取得可能なのは最大7日
        """
        df = yf.Ticker(self.pair).history(
            period=period, interval=self.interval, auto_adjust=False
        )
        if df.empty:
            raise ValueError("履歴データが取得できませんでした。period/interval を見直してください。")

        df = df.tz_convert("Asia/Tokyo")
        self.df = df.copy()

        # 直近の状態も更新しておく
        self.latest_ts = df.index[-1]
        self.latest_price = float(df["Close"].iloc[-1])

        return df["Close"].astype(float).tolist()

    # ------- 2回目以降：差分1本だけ取得 -------
    def update(self) -> Tuple[pd.Timestamp, float]:
        """
        最新1本を取得してキャッシュに追記。 (ts, price) を返す
        既に取り込み済みの時刻なら、最後の1本をそのまま返す（無駄な重複追記を防止）
        """
        new_df = yf.Ticker(self.pair).history(
            period="1d", interval=self.interval, auto_adjust=False
        )
        if new_df.empty:
            # 通信や市場休場などで取れない場合は直近値を返す
            if self.latest_ts is not None and self.latest_price is not None:
                return self.latest_ts, self.latest_price
            raise RuntimeError("最新データの取得に失敗しました。")

        new_df = new_df.tz_convert("Asia/Tokyo")
        last = new_df.tail(1)
        ts = last.index[-1]
        price = float(last["Close"].iloc[-1])

        # まだ取り込んでいなければ追記
        if self.df.empty or ts not in self.df.index:
            self.df = pd.concat([self.df, last]).drop_duplicates()
        # 状態を更新
        self.latest_ts, self.latest_price = ts, price
        return ts, price

    # ------- 連続取得（任意で使えるジェネレータ） -------
    def stream(self, sleep_sec: float = 1.0):
        """
        差分だけを流し続けるイテレータ。forで回すと (ts, price) が届く。
        """
        while True:
            ts, price = self.update()
            yield ts, price
            time.sleep(sleep_sec)
