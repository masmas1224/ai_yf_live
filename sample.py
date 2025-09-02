import yfinance as yf

pair = "USDJPY=X"                 # 例: EURUSD=X, GBPJPY=X もOK
df = yf.Ticker(pair).history(
    period="7d",                  # 直近7日
    interval="1m",                # 1分足（1mは7日まで）
    auto_adjust=False             # 終値いじらない
)

# タイムゾーンを日本時間に
df = df.tz_convert("Asia/Tokyo")

print(df.tail())
df.to_csv("USDJPY_1m_7d.csv", index_label="datetime")
print("Saved: USDJPY_1m_7d.csv  rows=", len(df))

# poll_yf_1m.py
import time, yfinance as yf

pair = "USDJPY=X"
while True:
    df = yf.Ticker(pair).history(period="1d", interval="1m", auto_adjust=False)
    last = df.tail(1)  # 直近1本
    ts = last.index[-1].tz_convert("Asia/Tokyo")
    close = float(last["Close"].iloc[-1])
    print(ts, close)
    time.sleep(1)


    