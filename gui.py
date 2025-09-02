# live_plot_yf.py
import time, datetime as dt
import yfinance as yf
import matplotlib.pyplot as plt
from collections import deque

PAIR   = "USDJPY=X"
WINDOW = 180  # 表示する最新データ点数（180分）

times, closes = deque(maxlen=WINDOW), deque(maxlen=WINDOW)
plt.ion()
fig, ax = plt.subplots()
(line,) = ax.plot([], [])
ax.set_title(f"{PAIR} last price (1m)")
ax.set_xlabel("Time (JST)")
ax.set_ylabel("Close")

last_ts = None
while True:
    df   = yf.Ticker(PAIR).history(period="1d", interval="1m", auto_adjust=False)
    last = df.tail(1)
    ts   = last.index[-1].tz_convert("Asia/Tokyo").to_pydatetime()
    px   = float(last["Close"].iloc[-1])

    if ts != last_ts:
        times.append(ts)
        closes.append(px)
        line.set_data(times, closes)
        ax.relim(); ax.autoscale_view()
        fig.autofmt_xdate()
        plt.pause(0.01)  # 再描画
        last_ts = ts

    time.sleep(1)
