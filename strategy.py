# strategy.py
from typing import Optional, Dict

class Strategy:
    def generate(self, price: float, ma_dict: Dict[int, Optional[float]]) -> dict:
        """
        ma_dict は {25: ma25, 75: ma75, 200: ma200} みたいな辞書
        ここでは MA(25) を基準にシンプル判定。
        ついでに MA(25) と MA(75) が両方あるときはクロス気味の判定も例示。
        """
        ma25 = ma_dict.get(25)
        ma75 = ma_dict.get(75)

        signal = "WAIT"
        if ma25 is not None:
            if price > ma25:
                signal = "BUY"
            elif price < ma25:
                signal = "SELL"
            else:
                signal = "HOLD"

        # 参考：短期/長期が両方そろってたら、こっちを優先してもOK
        if ma25 is not None and ma75 is not None:
            if price > ma25 > ma75:
                signal = "BUY"
            elif price < ma25 < ma75:
                signal = "SELL"

        return {"signal": signal, "price": price, "ma": ma_dict}
