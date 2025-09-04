import threading
import time
import os
from datetime import datetime
from fetcher import PriceFetcher
from average import MovingAverage
from strategy import Strategy
from decimal import Decimal, ROUND_DOWN
from bb import BollingerBands
from rsi import RSI

# === 設定 ===
WINDOWS = [25, 75, 200]
PAIR = "USDJPY=X"
INTERVAL = "1m"
HISTORY_PERIOD = "7d"
DEBUG = False # パフォーマンステスト用

# === 共有 ===
latest_price = None          # (ts, price)
latest_ma_snap = None        # (ts, price, {w: ma})
latest_signal = None         # dict
lock = threading.Lock()

# === タスク1: 価格取得（毎秒） ===
def run_price_task(fetcher: PriceFetcher, sleep_sec=1):
    global latest_price
    while True:
        if DEBUG:
            start = time.perf_counter()   # ← 計測開始

        ts, price = fetcher.update()
        with lock:
            latest_price = (ts, price)
        # print(f"[価格] {ts}  {price:.3f}")

        if DEBUG:
            end = time.perf_counter()   # ← 計測終了
            print(f"[task1] 計算時間: {(end - start)*1000:.3f} ms")

        time.sleep(sleep_sec)

# === タスク2:インジケータ（分が切り替わったらだけ更新） ===
def run_ma_task(mas: dict[int, MovingAverage], bb: BollingerBands, rsi: RSI, poll_sec=1):
    global latest_price, latest_ma_snap
    last_min = None
    while True:
        if DEBUG:
            start = time.perf_counter()   # ← 計測開始

        with lock:
            data = latest_price
        if data is None:
            time.sleep(poll_sec); continue

        ts, price = data
        cur_min = ts.replace(second=0, microsecond=0)
        if cur_min != last_min:
            ma_vals = {w: ma.update(price) for w, ma in mas.items()}
            bb_vals = bb.update(price)
            rsi_val = rsi.update(price)

            with lock:
                latest_ma_snap = (ts, price, ma_vals,bb_vals,rsi_val)
            # ログ
            parts = []
            for w in sorted(mas.keys()):
                v = ma_vals[w]
                parts.append(f"MA({w})={v:.3f}" if v is not None else f"MA({w})=nan")
            # print(f"[移動平均] {ts}  " + "  ".join(parts))
            last_min = cur_min

        if DEBUG:
            end = time.perf_counter()   # ← 計測終了
            print(f"[task2] 計算時間: {(end - start)*1000:.3f} ms")
        time.sleep(poll_sec)

# === タスク3: 売買シグナル判定（最新スナップショットで随時） ===
def run_strategy_task(strategy: Strategy, sleep_sec=1):
    global latest_price, latest_ma_snap, latest_signal
    while True:
        if DEBUG:
            start = time.perf_counter()   # ← 計測開始

        with lock:
            px = latest_price
            ma_snap = latest_ma_snap
        if not px or not ma_snap:
            time.sleep(0.1); continue

        ts_px, price = px
        ts_ma, _, ma_dict, bb_vals, rsi_val = ma_snap   # ma_snap = (ts, price, {w:ma})
        datetime = ts_px.strftime("%Y-%m-%d %H:%M:%S")

        # ここでは“分確定のMAに対して”現時点の価格で判定
        res = strategy.generate(price,datetime, ma_dict, bb_vals, rsi_val)

        with lock:
            latest_signal = res

        def fmt(x): return f"{x:.3f}" if x is not None else "nan"
        # print(
        #     f"[シグナル] {ts_px}  価格={price:.3f}  "
        #     f"MA25={fmt(ma_dict.get(25))}  MA75={fmt(ma_dict.get(75))}  MA200={fmt(ma_dict.get(200))}  "
        #     f"→ Signal={res['signal']}"
        # )

        if DEBUG:
            end = time.perf_counter()   # ← 計測終了
            print(f"[task3] 計算時間: {(end - start)*1000:.3f} ms")
        time.sleep(sleep_sec)
        
# === タスク4: 表示タスク ===
def run_view_task(sleep_sec=1):
    # global latest_price, latest_ma_snap, latest_signal
    mod = 0
    while True:
        os.system("cls")
        # if mod == 1:
        #     os.system("cls")
        #     mod = 0
        # else:
        #     mod = 1

        if DEBUG:
            start = time.perf_counter()   # ← 計測開始

        with lock:
            px = latest_price
            ma_snap = latest_ma_snap
        if not px or not ma_snap:
            time.sleep(0.1); continue
        
        ts_px, price = px
        ts_ma, _, ma_dict, bb_vals, rsi_val = ma_snap  # ma_snap = (ts, price, {w:ma})
        date_part = ts_px.strftime("%Y-%m-%d")
        time_part = ts_px.strftime("%H:%M:%S")
        nowprice = Decimal(str(price)).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        ma25 = Decimal(str(ma_dict.get(25))).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        ma75 = Decimal(str(ma_dict.get(75))).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        ma200 = Decimal(str(ma_dict.get(200))).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        bb_upper_1 = Decimal(str(bb_vals['upper_1'])).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        bb_upper_2 = Decimal(str(bb_vals['upper_2'])).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        bb_lower_1 = Decimal(str(bb_vals['lower_1'])).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        bb_lower_2 = Decimal(str(bb_vals['lower_2'])).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        mid = Decimal(str(bb_vals['mid'])).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        rsi = Decimal(str(rsi_val)).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        print("-----------------------------------------------------------")
        print("date:",date_part,"time:",time_part)
        print("\033[31mnow price   :",nowprice,"\033[0m")

        print("\033[33mma 25       :",ma25,"\033[0m")
        print("\033[33mma 75       :",ma75,"\033[0m")
        print("\033[33mma 200      :",ma200,"\033[0m")

        ma200late = Decimal('0.0005')
        ONE = Decimal('1')
        ma200p = Decimal(ma200 * Decimal(ONE + ma200late)).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        ma200m = Decimal(ma200 * Decimal(ONE - ma200late)).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        print("\033[33mspl ma 200 +:",ma200p,"\033[0m")
        print("\033[33mspl ma 200  :",ma200,"\033[0m")
        print("\033[33mspl ma 200 -:",ma200m,"\033[0m")

        print("\033[32mbb +2σ      :",bb_upper_2,"\033[0m")
        print("\033[32mbb +1σ      :",bb_upper_1,"\033[0m")
        print("\033[32mbb mid      :",mid,"\033[0m")
        print("\033[32mbb -1σ      :",bb_lower_1,"\033[0m")
        print("\033[32mbb -2σ      :",bb_lower_2,"\033[0m")

        print("\033[34mrsi         :",rsi,"\033[0m")
        print()
        print()
        print()
        print("-----------------------------------------------------------")
        print("\033[32mresult      :",latest_signal["ret"][0],"\033[0m")
        print("\033[32m            :",latest_signal["ret"][1],"\033[0m")
        print("\033[32m            :",latest_signal["ret"][2],"\033[0m")
        print("\033[32m            :",latest_signal["ret"][3],"\033[0m")
        print("\033[32m            :",latest_signal["ret"][4],"\033[0m")
        print("\033[32m            :",latest_signal["ret"][5],"\033[0m")

        if DEBUG:
            end = time.perf_counter()   # ← 計測終了
            print(f"[task4] 計算時間: {(end - start)*1000:.3f} ms")
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

    bb  = BollingerBands(window=20, k=2.0)
    rsi = RSI(period=14)
    bb.init_prices(initial_prices)
    rsi.init_prices(initial_prices)

    strategy = Strategy()
    STATE_PATH = "strategy_state.json"
    if strategy.import_state(STATE_PATH):
        print(f"[INFO] 前回状態を復元しました: {STATE_PATH}")
    else:
        print(f"[INFO] 前回状態ファイルなし（新規開始）: {STATE_PATH}")

    t1 = threading.Thread(target=run_price_task,   args=(fetcher,), daemon=True)
    t2 = threading.Thread(target=run_ma_task,      args=(mas,bb,rsi),     daemon=True)
    t3 = threading.Thread(target=run_strategy_task,args=(strategy,),daemon=True)
    t4 = threading.Thread(target=run_view_task, daemon=True)

    t1.start()
    t2.start()
    t3.start()
    t4.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        # 停止前に状態を保存
        try:
            strategy.export_state(STATE_PATH)
            print(f"\n[INFO] 状態を保存しました: {STATE_PATH} ")
        finally:
           print("\n[INFO] 手動停止しました")

if __name__ == "__main__":
    main()
