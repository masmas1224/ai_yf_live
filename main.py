import threading
import time
from datetime import datetime
from fetcher import PriceFetcher
from average import MovingAverage
from strategy import Strategy

# === 設定 ===
WINDOWS = [25, 75, 200]
PAIR = "USDJPY=X"
INTERVAL = "1m"
HISTORY_PERIOD = "7d"

# === 共有スナップショット ===
latest_price = None          # (ts, price)
latest_ma_snap = None        # (ts, price, {w: ma})
latest_signal = None         # dict
lock = threading.Lock()

# === タスク1: 価格取得（毎秒） ===
def run_price_task(fetcher: PriceFetcher, sleep_sec=1):
    global latest_price
    while True:
        ts, price = fetcher.update()
        with lock:
            latest_price = (ts, price)
        print(f"[価格] {ts}  {price:.3f}")
        time.sleep(sleep_sec)

# === タスク2: 移動平均計算（分が切り替わったらだけ更新） ===
def run_ma_task(mas: dict[int, MovingAverage], poll_sec=0.1):
    global latest_price, latest_ma_snap
    last_min = None
    while True:
        with lock:
            data = latest_price
        if data is None:
            time.sleep(poll_sec); continue

        ts, price = data
        cur_min = ts.replace(second=0, microsecond=0)
        if cur_min != last_min:
            ma_vals = {w: ma.update(price) for w, ma in mas.items()}
            with lock:
                latest_ma_snap = (ts, price, ma_vals)
            # ログ
            parts = []
            for w in sorted(mas.keys()):
                v = ma_vals[w]
                parts.append(f"MA({w})={v:.3f}" if v is not None else f"MA({w})=nan")
            print(f"[移動平均] {ts}  " + "  ".join(parts))
            last_min = cur_min
        time.sleep(poll_sec)

# === タスク3: 売買シグナル判定（最新スナップショットで随時） ===
def run_strategy_task(strategy: Strategy, sleep_sec=1):
    global latest_price, latest_ma_snap, latest_signal
    while True:
        with lock:
            px = latest_price
            ma_snap = latest_ma_snap
        if not px or not ma_snap:
            time.sleep(0.1); continue

        ts_px, price = px
        ts_ma, _, ma_dict = ma_snap  # ma_snap = (ts, price, {w:ma})

        # ここでは“分確定のMAに対して”現時点の価格で判定
        res = strategy.generate(price, ma_dict)

        with lock:
            latest_signal = res

        def fmt(x): return f"{x:.3f}" if x is not None else "nan"
        print(
            f"[シグナル] {ts_px}  価格={price:.3f}  "
            f"MA25={fmt(ma_dict.get(25))}  MA75={fmt(ma_dict.get(75))}  MA200={fmt(ma_dict.get(200))}  "
            f"→ Signal={res['signal']}"
        )
        time.sleep(sleep_sec)

def main():
    fetcher = PriceFetcher(pair=PAIR, interval=INTERVAL)

    print("[INFO] 過去データ取得中...")
    initial_prices = fetcher.get_initial_prices(period=HISTORY_PERIOD)
    print(f"[INFO] 過去データ取得完了: {len(initial_prices)}本")

    mas = {w: MovingAverage(window=w) for w in WINDOWS}
    for w, ma in mas.items():
        ma.init_prices(initial_prices)
        print(f"[INFO] MA({w}) 初期化完了 最新値={ma.latest():.3f}")

    strategy = Strategy()

    t1 = threading.Thread(target=run_price_task,   args=(fetcher,), daemon=True)
    t2 = threading.Thread(target=run_ma_task,      args=(mas,),     daemon=True)
    t3 = threading.Thread(target=run_strategy_task,args=(strategy,),daemon=True)

    t1.start()
    t2.start()
    t3.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[INFO] 手動停止しました🦴")

if __name__ == "__main__":
    main()
