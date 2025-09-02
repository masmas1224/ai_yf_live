# analyze_live_pred.py
# live_pred.csv（datetime, close, proba_up, signal）を採点＆可視化
import json, math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

CSV = "live_pred.csv"
HORIZON_MIN = 5          # ai_yf_live.py の HORIZON に合わせる
BUY_TH = 0.58            # 同じく合わせる
ROUND_TRIP_COST_PIPS = 0.6  # 往復コスト（ざっくり）。JPYペアの1pip=0.01

def load_data(path=CSV):
    df = pd.read_csv(path)
    df["datetime"] = pd.to_datetime(df["datetime"], utc=True)
    df = df.sort_values("datetime").drop_duplicates("datetime")
    # JST列（見やすさ用）
    df["jst"] = df["datetime"].dt.tz_convert("Asia/Tokyo")
    return df

def realized_future_close(df):
    # タイムスタンプ+HORIZON分後のcloseを結合（等間隔前提）
    target_time = df["datetime"] + pd.to_timedelta(HORIZON_MIN, "min")
    future = df.set_index("datetime")["close"].reindex(target_time).to_numpy()
    return pd.Series(future, index=df.index, name="close_future")

def label_up(close_now, close_future):
    # 5分後に上がっていれば1、下がっていれば0（同値は0.5で除外）
    y = np.where(close_future > close_now, 1.0,
        np.where(close_future < close_now, 0.0, np.nan))
    return pd.Series(y, index=close_now.index, name="y_up")

def decide_signal(proba_up, buy_th=BUY_TH):
    # BUY / SELL / HOLD の再計算（csvのsignalと一致するはず）
    sell_th = 1.0 - buy_th
    s = np.where(proba_up >= buy_th, "BUY",
        np.where(proba_up <= sell_th, "SELL", "HOLD"))
    return pd.Series(s, index=proba_up.index, name="signal_calc")

def trade_return(row):
    # 売買方向にHORIZON分保持して手仕舞い（単純化）。
    # リターンは close_future/close_now -1（BUY）、反転（SELL）。
    if row["signal"] == "BUY":
        r = row["close_future"]/row["close"] - 1.0
    elif row["signal"] == "SELL":
        r = row["close"]/row["close_future"] - 1.0
    else:
        return np.nan
    # 簡易コスト（往復スプレッド）を差し引き
    # USDJPY想定：1pip=0.01 → 価格で割ってreturn化（近似）
    cost = (ROUND_TRIP_COST_PIPS * 0.01) / row["close"]
    return r - cost

def main():
    df = load_data(CSV)
    if df.empty or len(df) < HORIZON_MIN + 2:
        raise SystemExit("データが少ないよ。もう少し走らせてから来てね！")

    df["close_future"] = realized_future_close(df)
    df["y_up"] = label_up(df["close"], df["close_future"])
    df["signal_calc"] = decide_signal(df["proba_up"])
    # 念のためCSVのsignalを優先（手動調整してる可能性）
    df["signal"] = np.where(df["signal"].isin(["BUY","SELL","HOLD"]),
                            df["signal"], df["signal_calc"])

    # 採点対象：HOLD以外 & 未来値があるところ
    eval_df = df[(df["signal"]!="HOLD") & df["close_future"].notna()].copy()
    if eval_df.empty:
        raise SystemExit("HOLD以外のシグナルが無い/未来データが足りないよ。")

    # 命中判定（方向が合ったか）
    eval_df["hit"] = np.where(
        (eval_df["signal"]=="BUY") & (eval_df["y_up"]==1.0), 1,
        np.where((eval_df["signal"]=="SELL") & (eval_df["y_up"]==0.0), 1, 0)
    )

    # シンプル損益（HORIZONでクローズ）
    eval_df["ret"] = eval_df.apply(trade_return, axis=1)
    eval_df["eq"]  = eval_df["ret"].cumsum()  # 累積リターン（近似）

    # 概況
    total = len(eval_df)
    wins  = int(eval_df["hit"].sum())
    acc   = wins/total
    buy_df  = eval_df[eval_df["signal"]=="BUY"]
    sell_df = eval_df[eval_df["signal"]=="SELL"]
    buy_acc  = float(buy_df["hit"].mean()) if len(buy_df) else float("nan")
    sell_acc = float(sell_df["hit"].mean()) if len(sell_df) else float("nan")
    avg_ret  = float(eval_df["ret"].mean())
    std_ret  = float(eval_df["ret"].std())
    sharpe   = (avg_ret/std_ret*np.sqrt(60)) if std_ret>0 else float("nan") # 60 trades≈時間基準の近似

    # 確率の当たり具合（校正）：p_upを10分位に分けて実際の上昇率を計測
    bins = np.linspace(0,1,11)
    df["bin"] = pd.cut(df["proba_up"], bins, include_lowest=True)
    cal = df.dropna(subset=["y_up"]).groupby("bin").agg(
        mean_p=("proba_up","mean"),
        rate_up=("y_up","mean"),
        n=("y_up","count")
    ).reset_index()

    # 出力：テキスト要約
    summary = {
        "trades": total,
        "win_rate_overall": round(acc,4),
        "win_rate_buy": round(buy_acc,4) if not math.isnan(buy_acc) else None,
        "win_rate_sell": round(sell_acc,4) if not math.isnan(sell_acc) else None,
        "avg_return_per_trade": round(avg_ret,6),
        "std_return": round(std_ret,6) if not math.isnan(std_ret) else None,
        "sharpe_like": round(sharpe,3) if not math.isnan(sharpe) else None,
        "cumulative_return": round(float(eval_df["eq"].iloc[-1]),6),
        "horizon_min": HORIZON_MIN,
        "buy_threshold": BUY_TH,
        "round_trip_cost_pips": ROUND_TRIP_COST_PIPS
    }
    with open("eval_summary.json","w",encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    eval_df.to_csv("trades_detail.csv", index=False)
    cal.to_csv("calibration.csv", index=False)

    print("=== SUMMARY ===")
    for k,v in summary.items():
        print(f"{k}: {v}")

    # 図1: エクイティカーブ
    plt.figure()
    plt.plot(eval_df["jst"], eval_df["eq"])
    plt.title("Equity Curve (HORIZON hold)")
    plt.xlabel("Time (JST)"); plt.ylabel("Cumulative Return")
    plt.tight_layout(); plt.savefig("equity_curve.png", dpi=150)

    # 図2: 校正（確率の当たり具合）
    plt.figure()
    plt.plot([0,1],[0,1], linestyle="--")        # 完全校正ライン
    plt.scatter(cal["mean_p"], cal["rate_up"])
    plt.title("Calibration: predicted p_up vs. realized up-rate")
    plt.xlabel("Predicted probability"); plt.ylabel("Realized up-rate")
    plt.tight_layout(); plt.savefig("calibration.png", dpi=150)

    print("Saved: eval_summary.json, trades_detail.csv, calibration.csv, equity_curve.png, calibration.png")

if __name__ == "__main__":
    main()
