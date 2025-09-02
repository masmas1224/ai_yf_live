# ai_yf_live.py  （定期再学習 & モデル保存/読み込み & warm-start）
# 7日分で学習 → 毎分予測（BUY/SELL/HOLD） → CSV記録
import time, math, warnings
import numpy as np
import pandas as pd
import yfinance as yf
import joblib  # ★追加：モデル保存/読み込み
warnings.filterwarnings("ignore")

PAIR = "USDJPY=X"
INTERVAL = "1m"
HIST_PERIOD = "7d"      # 学習用
LIVE_PERIOD = "1d"      # 推論用ポーリング
HORIZON = 5             # 何分先で上がったか判定
OUT_CSV = "live_pred.csv"
BUY_TH = 0.58
SELL_TH = 1 - BUY_TH
RETRAIN_SEC = 6 * 3600  # ★追加：6時間ごとに再学習（お好みで）

# ---------- 指標・特徴量 ----------
def _rsi(close, n=14):
    diff = close.diff()
    up = diff.clip(lower=0).rolling(n).mean()
    dn = (-diff.clip(upper=0)).rolling(n).mean()
    rs = up / (dn + 1e-12)
    return 100 - 100 / (1 + rs)

def make_features(df: pd.DataFrame) -> pd.DataFrame:
    c = df["Close"]
    s = pd.DataFrame(index=df.index)
    s["ret1"]  = c.pct_change(1)
    s["ret5"]  = c.pct_change(5)
    ma20 = c.rolling(20).mean()
    std20 = c.rolling(20).std()
    s["z20"]   = (c - ma20) / (std20 + 1e-12)
    s["bb_w"]  = 4.0 * std20          # ≒ Upper2-Lower2
    s["rsi14"] = _rsi(c, 14)
    s["hour"]  = (pd.to_datetime(df.index.tz_convert("Asia/Tokyo"))
                  .strftime("%H").astype(int))
    return s

# ---------- 学習（sklearn→無ければ自作ロジ回帰） ----------
def train_model(pair=PAIR, prev=None):  # ★prevを受け取ってwarm-start可能に
    df = yf.Ticker(pair).history(period=HIST_PERIOD, interval=INTERVAL, auto_adjust=False)
    if df.empty:
        raise RuntimeError("学習データが空でした。period/interval を見直してね。")
    df = df.tz_convert("UTC").dropna(subset=["Close"])

    Xdf = make_features(df).dropna()
    future = df["Close"].shift(-HORIZON).reindex(Xdf.index)
    y = (future > df["Close"].reindex(Xdf.index)).astype(int).dropna()
    Xdf = Xdf.loc[y.index]

    # 標準化
    mu = Xdf.mean(); sd = Xdf.std().replace(0, 1)
    Xn = ((Xdf - mu) / sd).values.astype("float64")
    yv = y.values.astype("float64")

    model = {"mu": mu, "sd": sd, "cols": list(Xdf.columns)}
    try:
        from sklearn.linear_model import SGDClassifier
        # ★前回モデルがあれば重み引き継ぎ（warm-start）
        if prev and prev.get("type") == "sk":
            clf = prev["clf"]
            clf.warm_start = True
            clf.max_iter = 1000
            clf.fit(Xn, yv)
        else:
            clf = SGDClassifier(loss="log_loss", max_iter=2000, random_state=42)
            clf.fit(Xn, yv)
        model["type"] = "sk"; model["clf"] = clf
        print(f"[train] sklearn で学習完了：samples={len(Xn)} (warm-start={bool(prev and prev.get('type')=='sk')})")
    except Exception as e:
        # 自作ロジ回帰（L2正則化付きSGD）
        print(f"[train] sklearn 使わず自作ロジ回帰で学習します ({e})")
        w = np.zeros(Xn.shape[1]); lr = 0.1; l2 = 1e-3; epochs = 300
        for _ in range(epochs):
            z = Xn @ w
            p = 1 / (1 + np.exp(-z))
            grad = (Xn.T @ (p - yv)) / len(yv) + l2 * w
            w -= lr * grad
        model["type"] = "np"; model["w"] = w
        print(f"[train] 自作ロジ回帰で学習完了：samples={len(Xn)}")

    # CSVヘッダ（初回のみ）
    try:
        with open(OUT_CSV, "x", encoding="utf-8") as f:
            f.write("datetime,close,proba_up,signal\n")
    except FileExistsError:
        pass

    # ★学習済みを保存（再起動で引き継ぎ）
    try:
        joblib.dump(model, "ai_meta.pkl")
    except Exception as e:
        print("[train] save skipped:", e)

    return model

def load_or_train(pair=PAIR):
    """★保存済みモデルがあれば読み込み、無ければ学習"""
    try:
        m = joblib.load("ai_meta.pkl")
        print("[load] ai_meta.pkl を読み込みました")
        return m
    except Exception:
        return train_model(pair)

def predict_proba(model, x_row: pd.Series) -> float:
    x = (x_row[model["cols"]] - model["mu"]) / model["sd"]
    xv = x.values.astype("float64").reshape(1, -1)
    if model["type"] == "sk":
        p = float(model["clf"].predict_proba(xv)[0, 1])
    else:
        z = float(xv @ model["w"])
        p = 1.0 / (1.0 + math.exp(-z))
    return p

# ---------- ライブ推論 ----------
def live_loop(model, pair=PAIR, sleep_sec=1, retrain_sec=None, use_warmstart=True):
    last_min = None
    last_train = time.time()

    while True:
        # ★一定間隔で再学習（warm-start=前回重み引き継ぎ）
        if retrain_sec and (time.time() - last_train >= retrain_sec):
            try:
                print("[retrain] start…")
                model = train_model(pair, prev=model if use_warmstart else None)
                last_train = time.time()
                print("[retrain] done")
            except Exception as e:
                print("[retrain] failed:", e)

        # 1d×1m を取得、空なら7d×1mへフォールバック
        df = pd.DataFrame()
        for period in (LIVE_PERIOD, "7d"):
            tmp = yf.Ticker(pair).history(period=period, interval=INTERVAL, auto_adjust=False)
            if not tmp.empty:
                df = tmp; break
        if df.empty:
            print("No data…retry"); time.sleep(2); continue

        df = df.tz_convert("UTC")
        feats = make_features(df).dropna()
        if feats.empty:
            time.sleep(1); continue

        ts = feats.index[-1]  # UTC
        cur_min = ts.strftime("%Y-%m-%d %H:%M")
        # 同じ分を重複して出さない
        if cur_min != last_min:
            p_up = predict_proba(model, feats.iloc[-1])
            jst = ts.tz_convert("Asia/Tokyo")
            close = float(df["Close"].iloc[-1])
            sig = "BUY" if p_up >= BUY_TH else ("SELL" if p_up <= SELL_TH else "HOLD")
            print(f"{jst}  close={close:.6f}  p_up={p_up:.3f}  -> {sig}")

            with open(OUT_CSV, "a", encoding="utf-8") as f:
                f.write(f"{jst.isoformat()},{close:.6f},{p_up:.6f},{sig}\n")

            last_min = cur_min

        time.sleep(sleep_sec)

if __name__ == "__main__":
    model = load_or_train(PAIR)                                   # ★保存があれば継承
    live_loop(model, PAIR, sleep_sec=1, retrain_sec=RETRAIN_SEC)  # ★定期再学習ON
