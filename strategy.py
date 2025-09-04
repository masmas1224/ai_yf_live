# strategy.py
import json, os, threading

from typing import Optional, Dict
from dataclasses import dataclass, asdict 
from decimal import Decimal, ROUND_DOWN

#固有変数
@dataclass
class SignalResult:
    win:int = 0 #勝ち回数
    los:int = 0 #負け回数
    cnt:int = 0 #トレード回数
    sum:float  = 500000.0#総資産
    hold:int = 0 #ポジション総数(通貨単位)
    calc_sum:float = 0.0 #ポジション総数(計算結果=レート*通貨単位)
    holdjudge:int = 0 #(0:no/1:buy/2:sell)
    end_time_stamp:str = ""
    ma200p_Profit:float = None #利確ライン
    ma200m_Profit:float = None #利確ライン

#受け渡し展開用変数
price = None
ma25 = None
ma75 = None
ma200 = None
rsi = None
bb_up2 = None
bb_up1 = None
bb_mid = None
bb_dn1 = None
bb_dn2 = None

rsi_old = None
ret1 = SignalResult()
ret2 = SignalResult()
ret3 = SignalResult()
ret4 = SignalResult() 
ret5 = SignalResult()
ret6 = SignalResult()

class Strategy:
    def __init__(self):
        # ret1 などの読み書き競合を避けるためのロック
        self._lock = threading.RLock()
    # --- 追加: 状態のスナップショット/保存/復元 ---
    def snapshot(self) -> dict:
        with self._lock:
            return {
                "ret1": asdict(ret1),
                "ret2": asdict(ret2),
                "ret3": asdict(ret3),
                "ret4": asdict(ret4),
                "ret5": asdict(ret5),
                "ret6": asdict(ret6),
            }

    def restore(self, state: dict) -> None:
        global ret1, ret2, ret3, ret4, ret5, ret6
        if not state: 
            return
        with self._lock:
            for key, obj in [("ret1", ret1), ("ret2", ret2), ("ret3", ret3),
                             ("ret4", ret4), ("ret5", ret5), ("ret6", ret6)]:
                data = state.get(key)
                if isinstance(data, dict):
                    for k, v in data.items():
                        setattr(obj, k, v)

    def export_state(self, path: str) -> None:
        try:
            with self._lock:
                state = self.snapshot()
            with open(path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception as e:
            print(f"[WARN] 状態保存に失敗: {e}")

    def import_state(self, path: str) -> bool:
        if not os.path.exists(path):
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                state = json.load(f)
            self.restore(state)
            return True
        except Exception as e:
            print(f"[WARN] 状態復元に失敗: {e}")
            return False

    @staticmethod
    def to_decimal(val, digits=3, as_float=True):
        if val is None:
            return None
        d = Decimal(str(val)).quantize(Decimal("0." + "0"*digits), rounding=ROUND_DOWN)
        return float(d) if as_float else d

    def generate(
            self,
            now_price: float,
            time:str,
            ma_dict: Dict[int, Optional[float]],
            bb_vals: dict,
            rsi_val: float
        ) -> dict:
        global price,ma25,ma75,ma200,rsi,bb_up2,bb_up1,bb_mid,bb_dn1,bb_dn2
        global rsi_old,ret1,ret2,ret3,ret4,ret5,ret6

        #変数展開用
        price = self.to_decimal(now_price)
        ma25 = self.to_decimal(ma_dict.get(25))
        ma75 = self.to_decimal(ma_dict.get(75))
        ma200 = self.to_decimal(ma_dict.get(200))
        rsi = self.to_decimal(rsi_val)
        bb_up2 = self.to_decimal(bb_vals['upper_2'])
        bb_up1 = self.to_decimal(bb_vals['upper_1'])
        bb_mid = self.to_decimal(bb_vals['mid'])
        bb_dn1 = self.to_decimal(bb_vals['lower_1'])
        bb_dn2 = self.to_decimal(bb_vals['lower_2'])
        if rsi_old is None:
            rsi_old = rsi

        #戦術1
        #START
        if ret1.end_time_stamp != time:
            if rsi_old < 20:
                if rsi >= 20:
                    if ret1.hold == 0:
                        ret1.hold = 10000
                        ret1.calc_sum += (ret1.hold * price)

                        ret1.holdjudge = 1
                        ret1.end_time_stamp = time
                    elif ret1.hold == 10000:
                        ret1.hold += ret1.hold * 2 # ドルコスト
                        ret1.calc_sum += (ret1.hold * price)

                        ret1.holdjudge = 1
                        ret1.end_time_stamp = time
                    elif ret1.hold == 30000:
                        ret1.hold += ret1.hold * 2 # ドルコスト
                        ret1.calc_sum += (ret1.hold * price)

                        ret1.holdjudge = 1
                        ret1.end_time_stamp = time
            if rsi_old > 80:
                if rsi <= 80:
                    if ret1.hold == 0:
                        ret1.hold = 10000
                        ret1.calc_sum += (ret1.hold * price)

                        ret1.holdjudge = 2
                        ret1.end_time_stamp = time
                    elif ret1.hold == 10000:
                        ret1.hold += ret1.hold * 2 # ドルコスト
                        ret1.calc_sum += (ret1.hold * price)

                        ret1.holdjudge = 2
                        ret1.end_time_stamp = time
                    elif ret1.hold == 30000:
                        ret1.hold += ret1.hold * 2 # ドルコスト
                        ret1.calc_sum += (ret1.hold * price)

                        ret1.holdjudge = 2
                        ret1.end_time_stamp = time
        #EXSIT
        #決済条件
        if ret1.hold != 0:# 保有している時
            if ret1.holdjudge == 1:# 買いポジの時
                if rsi >= 75:
                    ProfitAndLoss = ((ret1.hold * now_price) - ret1.calc_sum) #保有総数 - 現在価値
                    if ProfitAndLoss > 0:
                        ret1.win += 1
                    elif ProfitAndLoss < 0:
                        ret1.los += 1
                    ret1.cnt += 1
                    ret1.sum = ret1.sum + ProfitAndLoss
                    ret1.hold = 0
                    ret1.calc_sum = 0.0

                    ret1.holdjudge = 0
                    ret1.end_time_stamp = time
            if ret1.holdjudge == 2:# 売りポジの時
                if rsi <= 25:
                    ProfitAndLoss = (ret1.calc_sum - (ret1.hold * now_price)) #現在価値 - 保有総数
                    if ProfitAndLoss > 0:
                        ret1.win += 1
                    elif ProfitAndLoss < 0:
                        ret1.los += 1
                    ret1.cnt += 1
                    ret1.sum = ret1.sum + ProfitAndLoss
                    ret1.hold = 0
                    ret1.calc_sum = 0.0

                    ret1.holdjudge = 0
                    ret1.end_time_stamp = time
        if ret1.hold != 0:# 保有している時
            if ret1.holdjudge == 1:# 買いポジの時
                cutLossRate = ret1.sum * 0.016
                if (ret1.sum + cutLossRate) <= (ret1.sum + ((ret1.hold * now_price) - ret1.calc_sum)):#利確〇%で強制利確
                    ProfitAndLoss = ((ret1.hold * now_price) - ret1.calc_sum) #保有総数 - 現在価値
                    if ProfitAndLoss > 0:
                        ret1.win += 1
                    elif ProfitAndLoss < 0:
                        ret1.los += 1
                    ret1.cnt += 1
                    ret1.sum = ret1.sum + ProfitAndLoss
                    ret1.hold = 0
                    ret1.calc_sum = 0.0

                    ret1.holdjudge = 0
                    ret1.end_time_stamp = time
            if ret1.holdjudge == 2:# 売りポジの時
                cutLossRate = ret1.sum * 0.016
                if (ret1.sum + cutLossRate) <= (ret1.sum + (ret1.calc_sum - (ret1.hold * now_price))):#利確〇%で強制利確
                    ProfitAndLoss = (ret1.calc_sum - (ret1.hold * now_price)) #現在価値 - 保有総数
                    if ProfitAndLoss > 0:
                        ret1.win += 1
                    elif ProfitAndLoss < 0:
                        ret1.los += 1
                    ret1.cnt += 1
                    ret1.sum = ret1.sum + ProfitAndLoss
                    ret1.hold = 0
                    ret1.calc_sum = 0.0

                    ret1.holdjudge = 0
                    ret1.end_time_stamp = time

        #想定外の決済条件（基本的に損切想定）
        if ret1.hold != 0:# 保有している時
            if ret1.holdjudge == 1:# 買いポジの時
                cutLossRate = ret1.sum * 0.013
                if (ret1.sum - cutLossRate) >= (ret1.sum + ((ret1.hold * now_price) - ret1.calc_sum)):#損切りラインを下回ったら
                    ProfitAndLoss = ((ret1.hold * now_price) - ret1.calc_sum) #保有総数 - 現在価値
                    if ProfitAndLoss > 0:
                        ret1.win += 1
                    elif ProfitAndLoss < 0:
                        ret1.los += 1
                    ret1.cnt += 1
                    ret1.sum = ret1.sum + ProfitAndLoss
                    ret1.hold = 0
                    ret1.calc_sum = 0.0

                    ret1.holdjudge = 0
                    ret1.end_time_stamp = time
            if ret1.holdjudge == 2:# 売りポジの時
                cutLossRate = ret1.sum * 0.013
                if (ret1.sum - cutLossRate) >= (ret1.sum + (ret1.calc_sum - (ret1.hold * now_price))):#損切りラインを下回ったら
                    ProfitAndLoss = (ret1.calc_sum - (ret1.hold * now_price)) #現在価値 - 保有総数
                    if ProfitAndLoss > 0:
                        ret1.win += 1
                    elif ProfitAndLoss < 0:
                        ret1.los += 1
                    ret1.cnt += 1
                    ret1.sum = ret1.sum + ProfitAndLoss
                    ret1.hold = 0
                    ret1.calc_sum = 0.0

                    ret1.holdjudge = 0
                    ret1.end_time_stamp = time

        if ret1.end_time_stamp != time:
            if ret1.holdjudge == 1:# 買いポジの時
                if rsi_old < 20:
                    if rsi >= 20:
                        if ret1.hold == 70000:# 4回目の買い入れの時
                            ProfitAndLoss = ((ret1.hold * now_price) - ret1.calc_sum) #保有総数 - 現在価値
                            if ProfitAndLoss > 0:
                                ret1.win += 1
                            elif ProfitAndLoss < 0:
                                ret1.los += 1
                            ret1.cnt += 1
                            ret1.sum = ret1.sum + ProfitAndLoss
                            ret1.hold = 0
                            ret1.calc_sum = 0.0

                            ret1.holdjudge = 0
                            ret1.end_time_stamp = time
            if ret1.holdjudge == 2:# 売りポジの時
                if rsi_old > 80:
                    if rsi <= 80:
                        if ret1.hold == 70000:# 4回目の売り入れの時
                            ProfitAndLoss = (ret1.calc_sum - (ret1.hold * now_price)) #現在価値 - 保有総数
                            if ProfitAndLoss > 0:
                                ret1.win += 1
                            elif ProfitAndLoss < 0:
                                ret1.los += 1
                            ret1.cnt += 1
                            ret1.sum = ret1.sum + ProfitAndLoss
                            ret1.hold = 0
                            ret1.calc_sum = 0.0

                            ret1.holdjudge = 0
                            ret1.end_time_stamp = time

        #戦術2
        ma200late = float('0.0005')
        ONE = float('1')
        ma200p = Decimal(ma200 * float(ONE + ma200late)).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        ma200m = Decimal(ma200 * float(ONE - ma200late)).quantize(Decimal("0.000"), rounding=ROUND_DOWN)
        
        #START
        if ret2.hold == 0:
            if ma200p <= price:
                ret2.hold += 30000
                ret2.calc_sum += (ret2.hold * price)
                ret2.holdjudge = 1
                ret2.end_time_stamp = time
                ret2.ma200p_Profit = ma200p + ((ma200p - ma200)*1.2)
            if ma200m >= price:
                ret2.hold += 30000
                ret2.calc_sum += (ret2.hold * price)

                ret2.holdjudge = 2
                ret2.end_time_stamp = time
                ret2.ma200m_Profit = ma200m + ((ma200m - ma200)*1.2)

        #EXSIT
        #想定外の決済条件（基本的に損切想定）
        if ret2.hold != 0:# 保有している時
            if ret2.holdjudge == 1:# 買いポジの時
                cutLossRate = ret2.sum * 0.013
                if (ret2.sum - cutLossRate) >= (ret2.sum + ((ret2.hold * now_price) - ret2.calc_sum)):#損切りラインを下回ったら
                    ProfitAndLoss = ((ret2.hold * now_price) - ret2.calc_sum) #保有総数 - 現在価値
                    if ProfitAndLoss > 0:
                        ret2.win += 1
                    elif ProfitAndLoss < 0:
                        ret2.los += 1
                    ret2.cnt += 1
                    ret2.sum = ret2.sum + ProfitAndLoss
                    ret2.hold = 0
                    ret2.calc_sum = 0.0

                    ret2.holdjudge = 0
                    ret2.end_time_stamp = time
            if ret2.holdjudge == 2:# 売りポジの時
                cutLossRate = ret2.sum * 0.013
                if (ret2.sum - cutLossRate) >= (ret2.sum + (ret2.calc_sum - (ret2.hold * now_price))):#損切りラインを下回ったら
                    ProfitAndLoss = (ret2.calc_sum - (ret2.hold * now_price)) #現在価値 - 保有総数
                    if ProfitAndLoss > 0:
                        ret2.win += 1
                    elif ProfitAndLoss < 0:
                        ret2.los += 1
                    ret2.cnt += 1
                    ret2.sum = ret2.sum + ProfitAndLoss
                    ret2.hold = 0
                    ret2.calc_sum = 0.0

                    ret2.holdjudge = 0
                    ret2.end_time_stamp = time

        if ret2.hold != 0:# 保有している時
            if ret2.holdjudge == 1:# 買いポジの時
                cutLossRate = ret2.sum * 0.016
                if (ret2.sum + cutLossRate) <= (ret2.sum + ((ret2.hold * now_price) - ret2.calc_sum)):#利確〇%で強制利確
                    ProfitAndLoss = ((ret2.hold * now_price) - ret2.calc_sum) #保有総数 - 現在価値
                    if ProfitAndLoss > 0:
                        ret2.win += 1
                    elif ProfitAndLoss < 0:
                        ret2.los += 1
                    ret2.cnt += 1
                    ret2.sum = ret2.sum + ProfitAndLoss
                    ret2.hold = 0
                    ret2.calc_sum = 0.0

                    ret2.holdjudge = 0
                    ret2.end_time_stamp = time
            if ret2.holdjudge == 2:# 売りポジの時
                cutLossRate = ret2.sum * 0.016
                if (ret2.sum + cutLossRate) <= (ret2.sum + (ret2.calc_sum - (ret2.hold * now_price))):#利確〇%で強制利確
                    ProfitAndLoss = (ret2.calc_sum - (ret2.hold * now_price)) #現在価値 - 保有総数
                    if ProfitAndLoss > 0:
                        ret2.win += 1
                    elif ProfitAndLoss < 0:
                        ret2.los += 1
                    ret2.cnt += 1
                    ret2.sum = ret2.sum + ProfitAndLoss
                    ret2.hold = 0
                    ret2.calc_sum = 0.0

                    ret2.holdjudge = 0
                    ret2.end_time_stamp = time
            if ret2.holdjudge == 1:# 買いポジの時
                if ret2.ma200p_Profit is not None:
                    if ret2.ma200p_Profit <= now_price:
                        ProfitAndLoss = ((ret2.hold * now_price) - ret2.calc_sum) #保有総数 - 現在価値
                        if ProfitAndLoss > 0:
                            ret2.win += 1
                        elif ProfitAndLoss < 0:
                            ret2.los += 1
                        ret2.cnt += 1
                        ret2.sum = ret2.sum + ProfitAndLoss
                        ret2.hold = 0
                        ret2.calc_sum = 0.0

                        ret2.holdjudge = 0
                        ret2.end_time_stamp = time
            if ret2.holdjudge == 2:# 売りポジの時
                if ret2.ma200m_Profit is not None:
                    if ret2.ma200m_Profit >= now_price:
                        ProfitAndLoss = (ret2.calc_sum - (ret2.hold * now_price)) #現在価値 - 保有総数
                        if ProfitAndLoss > 0:
                            ret2.win += 1
                        elif ProfitAndLoss < 0:
                            ret2.los += 1
                        ret2.cnt += 1
                        ret2.sum = ret2.sum + ProfitAndLoss
                        ret2.hold = 0
                        ret2.calc_sum = 0.0

                        ret2.holdjudge = 0
                        ret2.end_time_stamp = time
        if ret2.hold != 0:# 保有している時
            if ret2.holdjudge == 1:# 買いポジの時
                if price <= ma200:
                    ProfitAndLoss = ((ret2.hold * now_price) - ret2.calc_sum) #保有総数 - 現在価値
                    if ProfitAndLoss > 0:
                        ret2.win += 1
                    elif ProfitAndLoss < 0:
                        ret2.los += 1
                    ret2.cnt += 1
                    ret2.sum = ret2.sum + ProfitAndLoss
                    ret2.hold = 0
                    ret2.calc_sum = 0.0

                    ret2.holdjudge = 0
                    ret2.end_time_stamp = time
            if ret2.holdjudge == 2:# 売りポジの時
                if price >= ma200:
                    ProfitAndLoss = (ret2.calc_sum - (ret2.hold * now_price)) #現在価値 - 保有総数
                    if ProfitAndLoss > 0:
                        ret2.win += 1
                    elif ProfitAndLoss < 0:
                        ret2.los += 1
                    ret2.cnt += 1
                    ret2.sum = ret2.sum + ProfitAndLoss
                    ret2.hold = 0
                    ret2.calc_sum = 0.0

                    ret2.holdjudge = 0
                    ret2.end_time_stamp = time
        #戦術3
        #戦術4
        #戦術5
        #戦術6

        #前回値作成
        rsi_old = rsi

        ret = [asdict(ret1), asdict(ret2), asdict(ret3),
        asdict(ret4), asdict(ret5), asdict(ret6)]
        return { "price": price, "ret": ret}
