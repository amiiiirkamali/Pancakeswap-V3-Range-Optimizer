"""
پروژه بهینه‌سازی استخر نقدینگی V3 - PancakeSwap BSC
جفت‌ارز: CAKE/BNB
═══════════════════════════════════════════════════════════
نسخه ۳: رفع باگ‌های ریبالانسینگ + بازه ۱ ساله + تقسیم ۵۰/۵۰
═══════════════════════════════════════════════════════════

تغییرات نسبت به نسخه ۲:
────────────────────────
1. بازه زمانی: اصلاح دریافت داده برای پوشش کامل ۱ ساله (8760 ساعت)
2. ریبالانسینگ: وقتی قیمت از بازه خارج شد، فوراً و مکرراً ریبالانس شود
   (نه فقط لحظه اول خروج)
3. تقسیم ۵۰/۵۰: وقتی خارج بازه‌ایم، مثلاً همه CAKE داریم →
   ۳۵۰ CAKE نگه می‌داریم + ۳۵۰ CAKE → BNB تبدیل می‌شود
   (۵۰/۵۰ بر حسب دلار)

فرمول‌ها:
─────────
1. HODL Value:
   initial_cake = (capital/2) / cake_price_start
   initial_bnb  = (capital/2) / bnb_price_start
   HODL(t) = initial_cake × cake_price(t) + initial_bnb × bnb_price(t)

2. V3 Concentrated Liquidity:
   اگر P_lower ≤ P ≤ P_upper:
       amount0 = L × (√P_upper - √P) / (√P × √P_upper)
       amount1 = L × (√P - √P_lower)
   اگر P < P_lower:  → همه token0 (CAKE)
   اگر P > P_upper:  → همه token1 (BNB)

3. ریبالانسینگ:
   وقتی P خارج [P_lower, P_upper]:
   - ارزش دلاری فعلی محاسبه شود
   - هزینه gas و slippage کسر شود
   - ۵۰/۵۰ دلاری تقسیم شود
   - بازه جدید حول قیمت فعلی CAKE/BNB ساخته شود
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import warnings
from datetime import datetime, timedelta
import time as time_module

warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════
# بخش ۱: دریافت داده‌های CAKE/BNB - اصلاح‌شده برای ۱ سال کامل
# ═══════════════════════════════════════════════════════════

def get_pancakeswap_pair_data(target_days=365):
    """
    دریافت داده‌های CAKE/BNB برای PancakeSwap - حداقل ۱ سال

    تغییرات:
    - تعداد دورهای درخواست افزایش یافته تا ۱ سال پوشش دهد
    - هر درخواست ۱۰۰۰ کندل ساعتی = ~۴۱.۶ روز
    - برای ۳۶۵ روز: حداقل ۹ درخواست (۹ × ۱۰۰۰ = ۹۰۰۰ ساعت = ۳۷۵ روز)
    - ۱۲ درخواست می‌زنیم تا مطمئن شویم (≈۵۰۰ روز پوشش)
    """
    print("📥 دریافت داده‌های CAKE/BNB برای PancakeSwap...")
    print(f"   🎯 هدف: {target_days} روز ({target_days * 24} کندل ساعتی)")

    url = 'https://api.binance.com/api/v3/klines'

    # تعداد کندل مورد نیاز
    target_candles = target_days * 24
    # تعداد دورهای لازم (هر دور ۱۰۰۰ کندل)
    num_batches = (target_candles // 1000) + 2  # +2 برای اطمینان

    print(f"   📡 تعداد درخواست‌ها: {num_batches} (هر کدام ۱۰۰۰ کندل)")

    # ─── دریافت CAKE/USDT ───
    all_cake = []
    current_end_time = int(datetime.now().timestamp() * 1000)

    print(f"\n   دریافت CAKE/USDT...")
    for i in range(num_batches):
        params = {
            'symbol': 'CAKEUSDT',
            'interval': '1h',
            'limit': 1000,
            'endTime': current_end_time
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if not data or len(data) == 0:
                print(f"      ⚠ بخش {i + 1}: داده‌ای نیست، توقف")
                break
            all_cake = data + all_cake
            # زمان پایان بعدی = زمان شروع اولین کندل دریافتی - ۱ms
            current_end_time = data[0][0] - 1
            print(f"      ✓ بخش {i + 1}/{num_batches} "
                  f"({len(data)} کندل، مجموع: {len(all_cake)})")
            time_module.sleep(0.1)  # احترام به rate limit
        except Exception as e:
            print(f"      ✗ خطا در بخش {i + 1}: {e}")
            time_module.sleep(1)
            continue

    # ─── دریافت BNB/USDT ───
    all_bnb = []
    current_end_time = int(datetime.now().timestamp() * 1000)

    print(f"\n   دریافت BNB/USDT...")
    for i in range(num_batches):
        params = {
            'symbol': 'BNBUSDT',
            'interval': '1h',
            'limit': 1000,
            'endTime': current_end_time
        }
        try:
            response = requests.get(url, params=params, timeout=15)
            response.raise_for_status()
            data = response.json()
            if not data or len(data) == 0:
                print(f"      ⚠ بخش {i + 1}: داده‌ای نیست، توقف")
                break
            all_bnb = data + all_bnb
            current_end_time = data[0][0] - 1
            print(f"      ✓ بخش {i + 1}/{num_batches} "
                  f"({len(data)} کندل، مجموع: {len(all_bnb)})")
            time_module.sleep(0.1)
        except Exception as e:
            print(f"      ✗ خطا در بخش {i + 1}: {e}")
            time_module.sleep(1)
            continue

    if len(all_cake) == 0 or len(all_bnb) == 0:
        raise ValueError("❌ داده‌ای دریافت نشد! اتصال اینترنت را بررسی کنید.")

    # ─── ساخت DataFrame ───
    cols = [
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ]

    df_cake = pd.DataFrame(all_cake, columns=cols)
    df_bnb = pd.DataFrame(all_bnb, columns=cols)

    for df_temp in [df_cake, df_bnb]:
        df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], unit='ms')
        for col in ['close', 'high', 'low', 'volume', 'quote_volume']:
            df_temp[col] = df_temp[col].astype(float)

    # حذف تکراری‌ها
    df_cake = df_cake.drop_duplicates(subset='timestamp').set_index('timestamp')
    df_bnb = df_bnb.drop_duplicates(subset='timestamp').set_index('timestamp')

    # ترکیب
    df = pd.DataFrame()
    df['cake_usdt'] = df_cake['close']
    df['bnb_usdt'] = df_bnb['close']
    df['cake_volume'] = df_cake['quote_volume']
    df['bnb_volume'] = df_bnb['quote_volume']
    df = df.dropna()

    # ─── برش به بازه مورد نظر (آخرین target_days روز) ───
    total_available_hours = len(df)
    needed_hours = target_days * 24

    if total_available_hours > needed_hours:
        df = df.iloc[-needed_hours:]
        print(f"\n   ✂️ برش به {target_days} روز اخیر "
              f"(از {total_available_hours} ساعت → {needed_hours} ساعت)")
    elif total_available_hours < needed_hours:
        actual_days = total_available_hours / 24
        print(f"\n   ⚠️ فقط {actual_days:.0f} روز داده موجود است "
              f"(درخواست: {target_days} روز)")

    # نسبت CAKE/BNB
    df['close'] = df['cake_usdt'] / df['bnb_usdt']
    df['quote_volume'] = (df['cake_volume'] + df['bnb_volume']) / 2

    df = df.reset_index()

    # ─── گزارش ───
    days = len(df) / 24
    print(f"\n✅ داده‌های CAKE/BNB آماده شد")
    print(f"   📊 تعداد کندل: {len(df):,} ({days:.0f} روز ≈ {days / 30:.1f} ماه)")
    print(f"   📅 از: {df['timestamp'].iloc[0]}")
    print(f"   📅 تا: {df['timestamp'].iloc[-1]}")
    print(f"   💰 CAKE/BNB شروع: {df['close'].iloc[0]:.6f}")
    print(f"   💰 CAKE/BNB پایان: {df['close'].iloc[-1]:.6f}")
    print(f"   💰 CAKE شروع: ${df['cake_usdt'].iloc[0]:.2f}")
    print(f"   💰 BNB شروع:  ${df['bnb_usdt'].iloc[0]:.2f}")
    print(f"   💰 CAKE پایان: ${df['cake_usdt'].iloc[-1]:.2f}")
    print(f"   💰 BNB پایان:  ${df['bnb_usdt'].iloc[-1]:.2f}")

    # اعتبارسنجی
    if days < 300:
        print(f"\n   ⚠️ هشدار: داده کمتر از ۳۰۰ روز ({days:.0f} روز)")
        print(f"      نتایج ممکن است دقیق نباشد")
    else:
        print(f"\n   ✅ بازه زمانی کافی: {days:.0f} روز")

    return df


# ═══════════════════════════════════════════════════════════
# بخش ۲: کلاس استخر V3 - بدون تغییر
# ═══════════════════════════════════════════════════════════

class LiquidityPositionV3:
    """
    پوزیشن Concentrated Liquidity در V3.

    token0 = CAKE
    token1 = BNB
    قیمت = CAKE/BNB (چند BNB برای یک CAKE)

    فرمول‌ها:
    ─────────
    L0 = amount0 × (√P × √P_upper) / (√P_upper - √P)
    L1 = amount1 / (√P - √P_lower)
    L = min(L0, L1)

    در قیمت P:
        amount0 = L × (√P_upper - √P) / (√P × √P_upper)    [CAKE]
        amount1 = L × (√P - √P_lower)                       [BNB]
    """

    def __init__(self):
        self.L = 0
        self.price_lower = 0
        self.price_upper = 0
        self.center_price = 0
        self.range_percent = 0

    def open_position(self, capital_usd, center_price, range_percent,
                      cake_usdt_price, bnb_usdt_price):
        """
        باز کردن پوزیشن جدید.

        سرمایه ۵۰/۵۰ دلاری تقسیم می‌شود:
        - نصف دلاری → CAKE خریداری
        - نصف دلاری → BNB خریداری
        """
        self.center_price = center_price
        self.range_percent = range_percent
        self.price_lower = center_price * (1 - range_percent / 100)
        self.price_upper = center_price * (1 + range_percent / 100)

        # تقسیم ۵۰/۵۰ دلاری
        usd_per_side = capital_usd / 2
        amount0_cake = usd_per_side / cake_usdt_price  # تعداد CAKE
        amount1_bnb = usd_per_side / bnb_usdt_price    # تعداد BNB

        sqrt_p = np.sqrt(center_price)
        sqrt_pa = np.sqrt(self.price_lower)
        sqrt_pb = np.sqrt(self.price_upper)

        # محاسبه L
        if sqrt_pb - sqrt_p > 1e-15:
            L0 = amount0_cake * (sqrt_p * sqrt_pb) / (sqrt_pb - sqrt_p)
        else:
            L0 = 0

        if sqrt_p - sqrt_pa > 1e-15:
            L1 = amount1_bnb / (sqrt_p - sqrt_pa)
        else:
            L1 = 0

        if L0 > 0 and L1 > 0:
            self.L = min(L0, L1)
        else:
            self.L = max(L0, L1)

        self.capital_usd = capital_usd

    def is_in_range(self, price):
        """آیا قیمت CAKE/BNB در بازه [price_lower, price_upper] است؟"""
        return self.price_lower <= price <= self.price_upper

    def get_amounts(self, current_price_cake_bnb):
        """
        محاسبه مقدار CAKE و BNB در پوزیشن.

        Returns: (amount_cake, amount_bnb)
        """
        P = current_price_cake_bnb
        sqrt_p = np.sqrt(max(P, 1e-18))
        sqrt_pa = np.sqrt(max(self.price_lower, 1e-18))
        sqrt_pb = np.sqrt(max(self.price_upper, 1e-18))

        if P <= self.price_lower:
            # قیمت زیر بازه → همه CAKE شده
            denom = sqrt_pa * sqrt_pb
            if denom > 1e-18:
                amount0 = self.L * (sqrt_pb - sqrt_pa) / denom
            else:
                amount0 = 0
            amount1 = 0

        elif P >= self.price_upper:
            # قیمت بالای بازه → همه BNB شده
            amount0 = 0
            amount1 = self.L * (sqrt_pb - sqrt_pa)

        else:
            # در بازه
            denom = sqrt_p * sqrt_pb
            if denom > 1e-18:
                amount0 = self.L * (sqrt_pb - sqrt_p) / denom
            else:
                amount0 = 0
            amount1 = self.L * (sqrt_p - sqrt_pa)

        return max(amount0, 0), max(amount1, 0)

    def get_value_usd(self, cake_bnb_price, cake_usdt, bnb_usdt):
        """
        ارزش دلاری پوزیشن.

        = amount_cake × cake_usdt + amount_bnb × bnb_usdt
        """
        amount_cake, amount_bnb = self.get_amounts(cake_bnb_price)
        return amount_cake * cake_usdt + amount_bnb * bnb_usdt


# ═══════════════════════════════════════════════════════════
# بخش ۳: بک‌تست با ریبالانسینگ اصلاح‌شده
# ═══════════════════════════════════════════════════════════

def run_backtest_with_rebalance(price_data, range_percent,
                                 initial_capital=10000, fee_tier=0.25,
                                 gas_cost_usd=0.30, slippage_pct=0.1):
    """
    بک‌تست با ریبالانسینگ اصلاح‌شده.

    تغییرات کلیدی نسبت به نسخه ۲:
    ─────────────────────────────────
    1. ریبالانس هر بار که قیمت خارج بازه فعلی است (نه فقط لحظه اول)
       → شرط قبلی: `not in_range and was_in_range` (فقط لبه)
       → شرط جدید: `not in_range` (همیشه)
       ولی: برای جلوگیری از ریبالانس مکرر، بعد از هر ریبالانس
       بررسی می‌کنیم آیا بازه جدید شامل قیمت فعلی هست یا نه.

    2. تقسیم ۵۰/۵۰ دلاری:
       وقتی از پایین خارج شد → همه CAKE داریم (مثلاً ۷۰۰ CAKE)
       → ارزش دلاری محاسبه: ۷۰۰ × cake_price = total_usd
       → نصف CAKE نگه، نصف → BNB (با کسر slippage روی نصف swap‌شده)
       → capital_for_new_position = total_usd - gas - slippage_on_swap

    3. مرکز بازه جدید = قیمت فعلی CAKE/BNB (نه حد بازه قبلی)
       → اینطوری بازه جدید حتماً شامل قیمت فعلی خواهد بود
    """
    fee_rate = fee_tier / 100

    # ─── HODL ───
    initial_cake_usdt = price_data['cake_usdt'].iloc[0]
    initial_bnb_usdt = price_data['bnb_usdt'].iloc[0]
    hodl_cake_amount = (initial_capital / 2) / initial_cake_usdt
    hodl_bnb_amount = (initial_capital / 2) / initial_bnb_usdt

    # ─── پوزیشن اولیه ───
    position = LiquidityPositionV3()
    entry_price = price_data['close'].iloc[0]
    position.open_position(
        initial_capital, entry_price, range_percent,
        initial_cake_usdt, initial_bnb_usdt
    )

    # ─── متغیرها ───
    total_fees_usd = 0
    total_gas_costs = 0
    total_slippage_costs = 0
    rebalance_count = 0
    periods_in_range = 0
    periods_out_of_range = 0

    fee_history = []
    pool_value_history = []
    hodl_value_history = []
    total_value_history = []
    rebalance_timestamps = []
    range_history = []

    # تخمین سهم ما از حجم
    avg_daily_volume = price_data['quote_volume'].mean() * 24
    estimated_tvl = avg_daily_volume * 5
    our_share = min(initial_capital / estimated_tvl, 0.1)

    for idx in range(len(price_data)):
        row = price_data.iloc[idx]
        price_cake_bnb = row['close']
        cake_usdt = row['cake_usdt']
        bnb_usdt = row['bnb_usdt']
        volume = row['quote_volume']

        in_range = position.is_in_range(price_cake_bnb)

        # ─── ریبالانسینگ ───
        if not in_range:
            # قیمت خارج بازه فعلی → ریبالانس
            # 1. ارزش دلاری فعلی
            current_pool_value = position.get_value_usd(
                price_cake_bnb, cake_usdt, bnb_usdt
            )

            # 2. مشخص کردن وضعیت خروج
            if price_cake_bnb >= position.price_upper:
                exit_side = 'upper'
                # همه BNB شده → باید نصف را به CAKE تبدیل کنیم
                _, amount_bnb = position.get_amounts(price_cake_bnb)
                # ارزش دلاری: amount_bnb × bnb_usdt
                # نصف این مقدار BNB باید swap شود به CAKE
                swap_value_usd = current_pool_value / 2
            else:
                exit_side = 'lower'
                # همه CAKE شده → باید نصف را به BNB تبدیل کنیم
                amount_cake, _ = position.get_amounts(price_cake_bnb)
                swap_value_usd = current_pool_value / 2

            # 3. هزینه‌ها
            gas = gas_cost_usd
            # slippage فقط روی مقداری که swap می‌شود
            slippage = swap_value_usd * (slippage_pct / 100)
            total_gas_costs += gas
            total_slippage_costs += slippage

            # 4. سرمایه خالص برای پوزیشن جدید
            rebalance_capital = current_pool_value - gas - slippage

            # 5. مرکز جدید = قیمت فعلی (نه حد بازه!)
            #    اینطوری بازه جدید حتماً شامل قیمت فعلی خواهد بود
            new_center = price_cake_bnb

            # 6. باز کردن پوزیشن جدید (۵۰/۵۰ دلاری)
            position = LiquidityPositionV3()
            position.open_position(
                max(rebalance_capital, 0),
                new_center,
                range_percent,
                cake_usdt,
                bnb_usdt
            )

            rebalance_count += 1
            rebalance_timestamps.append(row['timestamp'])

            # بازبررسی (باید در بازه جدید باشد)
            in_range = position.is_in_range(price_cake_bnb)
            if not in_range:
                # این نباید اتفاق بیفتد اگر center = current price
                print(f"   ⚠️ هشدار: بعد از ریبالانس هنوز خارج بازه! "
                      f"idx={idx}, price={price_cake_bnb:.6f}, "
                      f"range=[{position.price_lower:.6f}, {position.price_upper:.6f}]")

        # ─── کارمزد ───
        if in_range:
            periods_in_range += 1
            concentration_factor = 100 / range_percent
            fee = volume * fee_rate * our_share * concentration_factor
            fee = min(fee, volume * fee_rate * 0.5)
            total_fees_usd += fee
            fee_history.append(fee)
        else:
            periods_out_of_range += 1
            fee_history.append(0)

        # ─── ثبت ───
        pool_val = position.get_value_usd(price_cake_bnb, cake_usdt, bnb_usdt)
        hodl_val = hodl_cake_amount * cake_usdt + hodl_bnb_amount * bnb_usdt
        total_val = pool_val + total_fees_usd

        pool_value_history.append(pool_val)
        hodl_value_history.append(hodl_val)
        total_value_history.append(total_val)

        range_history.append({
            'lower': position.price_lower,
            'upper': position.price_upper,
            'center': position.center_price
        })

    # ─── نتایج ───
    final_cake_bnb = price_data['close'].iloc[-1]
    final_cake_usdt = price_data['cake_usdt'].iloc[-1]
    final_bnb_usdt = price_data['bnb_usdt'].iloc[-1]

    final_pool_value = position.get_value_usd(
        final_cake_bnb, final_cake_usdt, final_bnb_usdt
    )
    final_hodl_value = hodl_cake_amount * final_cake_usdt + \
                       hodl_bnb_amount * final_bnb_usdt

    net_fees = total_fees_usd - total_gas_costs - total_slippage_costs
    final_total_value = final_pool_value + net_fees

    # IL
    il_percent = (final_pool_value / final_hodl_value - 1) * 100 \
        if final_hodl_value > 0 else 0

    total_periods = len(price_data)
    active_percent = (periods_in_range / total_periods) * 100
    days = total_periods / 24

    total_return = ((final_total_value - initial_capital) / initial_capital) * 100
    fee_apr = (net_fees / initial_capital) * (365 / max(days, 1)) * 100
    vs_hodl = ((final_total_value - final_hodl_value) / final_hodl_value) * 100 \
        if final_hodl_value > 0 else 0

    results = {
        'range_percent': range_percent,
        'entry_price': entry_price,
        'price_lower': position.price_lower,
        'price_upper': position.price_upper,
        'active_percent': active_percent,
        'periods_in_range': periods_in_range,
        'periods_out_of_range': periods_out_of_range,
        'rebalance_count': rebalance_count,
        'total_gas_costs': total_gas_costs,
        'total_slippage_costs': total_slippage_costs,
        'rebalance_timestamps': rebalance_timestamps,
        'total_fees_gross': total_fees_usd,
        'total_fees_net': net_fees,
        'fee_apr': fee_apr,
        'final_pool_value': final_pool_value,
        'final_hodl_value': final_hodl_value,
        'final_total_value': final_total_value,
        'impermanent_loss': il_percent,
        'total_return': total_return,
        'vs_hodl': vs_hodl,
        'fee_history': fee_history,
        'pool_value_history': pool_value_history,
        'hodl_value_history': hodl_value_history,
        'total_value_history': total_value_history,
        'range_history': range_history,
        'days': days,
    }

    return results


def run_all_scenarios(price_data, scenarios, initial_capital=10000):
    """اجرای بک‌تست برای همه بازه‌ها"""
    days = len(price_data) / 24
    print("\n" + "═" * 90)
    print(f"🚀 شروع بک‌تست - PancakeSwap V3 - CAKE/BNB ({days:.0f} روز)")
    print("═" * 90)
    print(f"{'بازه':^8} │ {'فعال%':^8} │ {'ریبالانس':^10} │ "
          f"{'کارمزد خالص':^14} │ {'APR':^8} │ {'بازده':^10}")
    print("─" * 90)

    all_results = {}
    for range_pct in scenarios:
        result = run_backtest_with_rebalance(
            price_data, range_pct, initial_capital
        )
        all_results[range_pct] = result

        status = "✅" if result['total_return'] > 0 else "❌"
        print(f"  ±{range_pct:2d}%   │ {result['active_percent']:6.1f}% │ "
              f"{result['rebalance_count']:8d}  │ "
              f"${result['total_fees_net']:10.0f}   │ "
              f"{result['fee_apr']:6.1f}% │ "
              f"{result['total_return']:+8.2f}% {status}")

    print("─" * 90)
    return all_results


# ═══════════════════════════════════════════════════════════
# بخش ۴: نمودارها - اصلاح‌شده با بازه ۱ ساله
# ═══════════════════════════════════════════════════════════

def create_all_charts(all_results, price_data, initial_capital=10000):
    """ساخت همه نمودارها"""

    ranges = sorted(all_results.keys())
    sorted_results = sorted(
        all_results.items(),
        key=lambda x: x[1]['total_return'], reverse=True
    )
    top3 = [r[0] for r in sorted_results[:3]]
    days = len(price_data) / 24

    # ═══════════════════════════════════════════════════════════
    # نمودار ۱: بهینه‌سازی کلی
    # ═══════════════════════════════════════════════════════════
    print("\n📊 ساخت نمودار ۱: بهینه‌سازی کلی...")

    fig1, axes1 = plt.subplots(2, 3, figsize=(20, 13))
    fig1.suptitle(
        f'PancakeSwap V3 - CAKE/BNB - Optimization with Rebalancing\n'
        f'(Initial: ${initial_capital:,} | Fee: 0.25% | '
        f'Period: {days:.0f} days ≈ {days/30:.1f} months)',
        fontsize=15, fontweight='bold'
    )

    # 1-1: قیمت CAKE/BNB
    ax = axes1[0, 0]
    ax.plot(price_data['timestamp'], price_data['close'],
            color='#F0B90B', linewidth=0.8)
    ax.set_title('CAKE/BNB Price', fontsize=11, fontweight='bold')
    ax.set_ylabel('CAKE/BNB')
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=30)

    # 1-2: بازده کل
    ax = axes1[0, 1]
    returns = [all_results[r]['total_return'] for r in ranges]
    colors_bar = ['#27ae60' if r > 0 else '#e74c3c' for r in returns]
    bars = ax.bar([f'±{r}%' for r in ranges], returns, color=colors_bar)
    ax.axhline(y=0, color='black', linewidth=1)
    ax.set_title(
        'Total Return (with Rebalancing)\n'
        '= (Final Value - Initial) / Initial × 100',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Return (%)')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')
    if returns:
        best_idx = returns.index(max(returns))
        bars[best_idx].set_edgecolor('gold')
        bars[best_idx].set_linewidth(3)

    # 1-3: درصد فعال
    ax = axes1[0, 2]
    active = [all_results[r]['active_percent'] for r in ranges]
    ax.plot(ranges, active, 'o-', color='#3498db', linewidth=2, markersize=8)
    ax.fill_between(ranges, active, alpha=0.2, color='#3498db')
    ax.set_title(
        'Time In Range (with Rebalancing)\n'
        'Since rebalance recenters, this should be high',
        fontsize=10, fontweight='bold'
    )
    ax.set_xlabel('Range Width (±%)')
    ax.set_ylabel('Active %')
    ax.grid(True, alpha=0.3)

    # 1-4: تعداد ریبالانس
    ax = axes1[1, 0]
    rebalances = [all_results[r]['rebalance_count'] for r in ranges]
    ax.bar([f'±{r}%' for r in ranges], rebalances, color='#e74c3c', alpha=0.8)
    ax.set_title(
        'Number of Rebalances\n'
        '(Narrower range → More rebalances)',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Count')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')

    # 1-5: Fee APR
    ax = axes1[1, 1]
    aprs = [all_results[r]['fee_apr'] for r in ranges]
    ax.plot(ranges, aprs, 's-', color='#9b59b6', linewidth=2, markersize=8)
    ax.set_title(
        'Net Fee APR\n'
        '= Net Fees / Capital × 365/days × 100',
        fontsize=10, fontweight='bold'
    )
    ax.set_xlabel('Range Width (±%)')
    ax.set_ylabel('APR %')
    ax.grid(True, alpha=0.3)

    # 1-6: Trade-off
    ax = axes1[1, 2]
    scatter = ax.scatter(active, returns, c=ranges, cmap='RdYlGn',
                         s=200, edgecolors='black', zorder=5)
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (active[i], returns[i]),
                    textcoords="offset points", xytext=(0, 12),
                    ha='center', fontsize=9, fontweight='bold')
    ax.set_title('Return vs Active Time', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time Active (%)')
    ax.set_ylabel('Total Return (%)')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range Width (%)')

    plt.tight_layout()
    plt.savefig('pancakeswap_optimization_v3.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_optimization_v3.png")
    plt.close(fig1)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۲: مقایسه ۳ بازه برتر
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۲: مقایسه ۳ برتر...")

    fig2, axes2 = plt.subplots(2, 2, figsize=(16, 12))
    fig2.suptitle(
        f'PancakeSwap V3 - Top 3 Ranges Comparison\n'
        f'({days:.0f} days with Rebalancing)',
        fontsize=15, fontweight='bold'
    )

    colors_top3 = {}
    palette = ['#27ae60', '#3498db', '#f39c12']
    for i, r in enumerate(top3):
        colors_top3[r] = palette[i]

    # 2-1: ارزش کل
    ax = axes2[0, 0]
    for r in top3:
        result = all_results[r]
        ax.plot(price_data['timestamp'], result['total_value_history'],
                label=f'±{r}% (rebal: {result["rebalance_count"]}x)',
                color=colors_top3[r], linewidth=1.5)
    ax.plot(price_data['timestamp'],
            all_results[top3[0]]['hodl_value_history'],
            label='HODL', color='gray', linewidth=2, linestyle='--')
    ax.axhline(y=initial_capital, color='red', linestyle=':',
               alpha=0.5, label=f'Initial: ${initial_capital:,}')
    ax.set_title('Portfolio Value Over Time', fontsize=10, fontweight='bold')
    ax.set_ylabel('Value ($)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=30)

    # 2-2: تجمعی کارمزد
    ax = axes2[0, 1]
    for r in top3:
        result = all_results[r]
        cum_fees = np.cumsum(result['fee_history'])
        ax.plot(price_data['timestamp'], cum_fees,
                label=f'±{r}% (${result["total_fees_gross"]:,.0f})',
                color=colors_top3[r], linewidth=1.5)
    ax.set_title('Cumulative Fees (Gross)', fontsize=10, fontweight='bold')
    ax.set_ylabel('Fees ($)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.tick_params(axis='x', rotation=30)

    # 2-3: مقایسه بار
    ax = axes2[1, 0]
    x = np.arange(len(top3))
    width = 0.2

    pool_vals = [all_results[r]['final_pool_value'] for r in top3]
    total_vals = [all_results[r]['final_total_value'] for r in top3]
    hodl_vals = [all_results[r]['final_hodl_value'] for r in top3]

    ax.bar(x - width, pool_vals, width,
           label='Pool Value (with IL)', color='#3498db', alpha=0.8)
    ax.bar(x, total_vals, width,
           label='Total Value (YOUR MONEY)', color='#27ae60', alpha=0.8)
    ax.bar(x + width, hodl_vals, width,
           label='HODL Value', color='#95a5a6', alpha=0.8)
    ax.axhline(y=initial_capital, color='red', linestyle='--',
               alpha=0.7, linewidth=2, label=f'Initial: ${initial_capital:,}')

    for i, (p, t, h) in enumerate(zip(pool_vals, total_vals, hodl_vals)):
        ax.text(x[i] - width, p + 100, f'${p:,.0f}',
                ha='center', va='bottom', fontsize=7, fontweight='bold')
        ax.text(x[i], t + 100, f'${t:,.0f}',
                ha='center', va='bottom', fontsize=7, fontweight='bold',
                color='darkgreen')
        ax.text(x[i] + width, h + 100, f'${h:,.0f}',
                ha='center', va='bottom', fontsize=7, fontweight='bold')

    ax.set_title('Final Value Comparison', fontsize=10, fontweight='bold')
    ax.set_ylabel('Value ($)')
    ax.set_xticks(x)
    ax.set_xticklabels([f'±{r}%' for r in top3])
    ax.legend(fontsize=7, loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')

    # 2-4: جدول
    ax = axes2[1, 1]
    ax.axis('off')

    headers = [
        'Range', 'Active%', 'Rebal',
        'Gross Fees', 'Costs', 'Net Fees',
        'APR', 'IL%', 'Return', 'vs HODL'
    ]
    table_data = []
    for r in top3:
        res = all_results[r]
        costs = res['total_gas_costs'] + res['total_slippage_costs']
        table_data.append([
            f'±{r}%',
            f"{res['active_percent']:.1f}%",
            f"{res['rebalance_count']}",
            f"${res['total_fees_gross']:,.0f}",
            f"${costs:,.0f}",
            f"${res['total_fees_net']:,.0f}",
            f"{res['fee_apr']:.1f}%",
            f"{res['impermanent_loss']:.2f}%",
            f"{res['total_return']:+.2f}%",
            f"{res['vs_hodl']:+.2f}%"
        ])

    table = ax.table(cellText=table_data, colLabels=headers,
                     loc='center', cellLoc='center')
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.3, 2.2)
    for j in range(len(headers)):
        table[(0, j)].set_facecolor('#F0B90B')
        table[(0, j)].set_text_props(fontweight='bold', fontsize=7)
        table[(1, j)].set_facecolor('#d5f5e3')
    ax.set_title('Top 3 Summary', fontsize=11, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig('pancakeswap_top3_v3.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_top3_v3.png")
    plt.close(fig2)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۳: تحلیل ریبالانسینگ
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۳: تحلیل ریبالانسینگ...")

    fig3, axes3 = plt.subplots(2, 2, figsize=(16, 12))
    fig3.suptitle(
        f'Rebalancing Analysis ({days:.0f} days)',
        fontsize=14, fontweight='bold'
    )

    # 3-1
    ax = axes3[0, 0]
    rebalances = [all_results[r]['rebalance_count'] for r in ranges]
    returns_list = [all_results[r]['total_return'] for r in ranges]
    scatter = ax.scatter(rebalances, returns_list, c=ranges,
                         cmap='viridis', s=200, edgecolors='black', zorder=5)
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (rebalances[i], returns_list[i]),
                    textcoords="offset points", xytext=(5, 8), fontsize=9)
    ax.set_title('Return vs Rebalance Count', fontsize=11, fontweight='bold')
    ax.set_xlabel('Rebalances')
    ax.set_ylabel('Return (%)')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    # 3-2
    ax = axes3[0, 1]
    gas_costs = [all_results[r]['total_gas_costs'] for r in ranges]
    slip_costs = [all_results[r]['total_slippage_costs'] for r in ranges]
    x_pos = np.arange(len(ranges))
    ax.bar(x_pos, gas_costs, 0.4, label='Gas', color='#e74c3c')
    ax.bar(x_pos, slip_costs, 0.4, bottom=gas_costs,
           label='Slippage', color='#f39c12')
    ax.set_title('Rebalancing Costs', fontsize=10, fontweight='bold')
    ax.set_ylabel('Cost ($)')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'±{r}%' for r in ranges], fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # 3-3
    ax = axes3[1, 0]
    gross_fees = [all_results[r]['total_fees_gross'] for r in ranges]
    net_fees_list = [all_results[r]['total_fees_net'] for r in ranges]
    ax.bar(x_pos - 0.2, gross_fees, 0.35, label='Gross', color='#3498db')
    ax.bar(x_pos + 0.2, net_fees_list, 0.35, label='Net', color='#27ae60')
    ax.set_title('Gross vs Net Fees', fontsize=10, fontweight='bold')
    ax.set_ylabel('Fees ($)')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'±{r}%' for r in ranges], fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # 3-4
    ax = axes3[1, 1]
    aprs = [all_results[r]['fee_apr'] for r in ranges]
    scatter = ax.scatter(rebalances, aprs, c=ranges,
                         cmap='plasma', s=200, edgecolors='black', zorder=5)
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (rebalances[i], aprs[i]),
                    textcoords="offset points", xytext=(5, 8), fontsize=9)
    ax.set_title('Net Fee APR vs Rebalances', fontsize=11, fontweight='bold')
    ax.set_xlabel('Rebalances')
    ax.set_ylabel('APR %')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    plt.tight_layout()
    plt.savefig('pancakeswap_rebalancing_v3.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_rebalancing_v3.png")
    plt.close(fig3)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۴: نمایش بصری ریبالانسینگ بهترین بازه
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۴: نمایش بصری ریبالانسینگ...")

    best_range = top3[0]
    best_result = all_results[best_range]

    fig4, axes4 = plt.subplots(3, 1, figsize=(18, 14),
                                gridspec_kw={'height_ratios': [3, 2, 2]})
    fig4.suptitle(
        f'Rebalancing Visualization - ±{best_range}%\n'
        f'({best_result["rebalance_count"]} rebalances, '
        f'{days:.0f} days)',
        fontsize=14, fontweight='bold'
    )

    timestamps = price_data['timestamp']
    prices = price_data['close']

    # 4-1: قیمت با بازه‌ها
    ax = axes4[0]
    ax.plot(timestamps, prices, color='#2c3e50', linewidth=0.8,
            label='CAKE/BNB', zorder=3)

    range_lowers = [rh['lower'] for rh in best_result['range_history']]
    range_uppers = [rh['upper'] for rh in best_result['range_history']]

    ax.fill_between(timestamps, range_lowers, range_uppers,
                    alpha=0.15, color='green', label='Active Range')
    ax.plot(timestamps, range_lowers, color='green', linewidth=0.5, alpha=0.5)
    ax.plot(timestamps, range_uppers, color='green', linewidth=0.5, alpha=0.5)

    # نقاط ریبالانس (حداکثر ۱۰۰ خط)
    max_lines = min(100, len(best_result['rebalance_timestamps']))
    for ts in best_result['rebalance_timestamps'][:max_lines]:
        ax.axvline(x=ts, color='red', alpha=0.2, linewidth=0.5)

    ax.set_title(
        f'Price with Dynamic Range ±{best_range}%\n'
        'Red lines = Rebalances | Green = Active range',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('CAKE/BNB')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # 4-2: مقایسه ارزش
    ax = axes4[1]
    ax.plot(timestamps, best_result['total_value_history'],
            color='#27ae60', linewidth=1.5,
            label=f'LP (±{best_range}%): '
                  f'${best_result["final_total_value"]:,.0f}')
    ax.plot(timestamps, best_result['hodl_value_history'],
            color='#95a5a6', linewidth=1.5, linestyle='--',
            label=f'HODL: ${best_result["final_hodl_value"]:,.0f}')
    ax.axhline(y=initial_capital, color='red', linestyle=':',
               alpha=0.5, label=f'Initial: ${initial_capital:,}')
    ax.set_title('Portfolio Value: LP vs HODL', fontsize=10, fontweight='bold')
    ax.set_ylabel('Value ($)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4-3: کارمزد تجمعی
    ax = axes4[2]
    cum_fees = np.cumsum(best_result['fee_history'])
    ax.plot(timestamps, cum_fees, color='#F0B90B', linewidth=1.5,
            label=f'Cumulative Fees: ${best_result["total_fees_gross"]:,.0f}')
    total_costs = best_result['total_gas_costs'] + \
                  best_result['total_slippage_costs']
    ax.axhline(y=total_costs, color='red', linestyle='--', alpha=0.7,
               label=f'Total Costs: ${total_costs:,.0f}')
    ax.set_title('Cumulative Fees', fontsize=10, fontweight='bold')
    ax.set_ylabel('Fees ($)')
    ax.set_xlabel('Date')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('pancakeswap_rebalance_visual_v3.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_rebalance_visual_v3.png")
    plt.close(fig4)

    print("\n✅ همه نمودارها ساخته شدند!")
    return top3


# ═══════════════════════════════════════════════════════════
# بخش ۵: جدول نتایج
# ═══════════════════════════════════════════════════════════

def print_results(all_results):
    """چاپ جدول کامل"""
    print("\n" + "═" * 140)
    print("📋 جدول کامل نتایج - PancakeSwap V3 - CAKE/BNB")
    print("═" * 140)

    sorted_results = sorted(
        all_results.items(),
        key=lambda x: x[1]['total_return'], reverse=True
    )

    header = (f"{'':^4} {'بازه':^6} │ {'فعال%':^7} │ {'ریبالانس':^9} │ "
              f"{'کارمزد ناخالص':^14} │ {'هزینه‌ها':^10} │ "
              f"{'کارمزد خالص':^12} │ {'APR':^7} │ {'IL%':^8} │ "
              f"{'بازده':^9} │ {'vs HODL':^9}")
    print(header)
    print("─" * 140)

    for i, (range_pct, r) in enumerate(sorted_results):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "  "
        costs = r['total_gas_costs'] + r['total_slippage_costs']
        print(
            f"{medal} ±{range_pct:2d}%  │ "
            f"{r['active_percent']:5.1f}% │ "
            f"{r['rebalance_count']:7d}  │ "
            f"${r['total_fees_gross']:10.0f}   │ "
            f"${costs:8.0f} │ "
            f"${r['total_fees_net']:9.0f}  │ "
            f"{r['fee_apr']:5.1f}% │ "
            f"{r['impermanent_loss']:+6.2f}% │ "
            f"{r['total_return']:+7.2f}% │ "
            f"{r['vs_hodl']:+7.2f}%"
        )

    print("═" * 140)

    print("\n📐 توضیح فرمول‌ها:")
    print("─" * 60)
    print("""
    HODL Value = cake_initial × cake_price_now + bnb_initial × bnb_price_now

    Pool Value = cake_in_pool × cake_price + bnb_in_pool × bnb_price
                 (شامل IL)

    IL% = (Pool Value / HODL Value - 1) × 100

    Net Fees = Gross Fees - Gas Costs - Slippage Costs

    Total Value = Pool Value + Net Fees = آنچه واقعاً دارید

    Total Return = (Total Value - Initial) / Initial × 100

    Fee APR = (Net Fees / Capital) × (365 / days) × 100

    vs HODL = (Total Value - HODL Value) / HODL Value × 100

    ریبالانسینگ:
    ─────────────
    وقتی قیمت از بازه خارج شد:
    1. ارزش دلاری پوزیشن فعلی محاسبه
    2. هزینه gas ($0.30) کسر
    3. نصف دارایی swap (slippage 0.1% روی نصف swap‌شده)
    4. مرکز جدید = قیمت فعلی CAKE/BNB
    5. بازه جدید = مرکز ± range%
    6. پوزیشن جدید ۵۰/۵۰ دلاری باز می‌شود
    """)

    return sorted_results


# ═══════════════════════════════════════════════════════════
# بخش ۶: تابع اصلی
# ═══════════════════════════════════════════════════════════

initial_capital = 10000


def main():
    global initial_capital

    print("╔" + "═" * 65 + "╗")
    print("║  🥞 PancakeSwap V3 - Concentrated Liquidity Optimization     ║")
    print("║  📊 Pair: CAKE/BNB on BSC                                    ║")
    print("║  🔄 Version 3: Fixed Rebalancing + 1 Year Data               ║")
    print("╚" + "═" * 65 + "╝")

    INITIAL_CAPITAL = initial_capital
    FEE_TIER = 0.25
    SCENARIOS = [2, 3, 4, 5, 7, 10, 15, 20, 25, 30, 40, 50]
    GAS_COST = 0.30
    SLIPPAGE = 0.1
    TARGET_DAYS = 365

    print(f"\n⚙️ Settings:")
    print(f"   • DEX: PancakeSwap V3")
    print(f"   • Chain: BNB Smart Chain (BSC)")
    print(f"   • Pair: CAKE/BNB")
    print(f"   • Capital: ${INITIAL_CAPITAL:,}")
    print(f"   • Fee Tier: {FEE_TIER}%")
    print(f"   • Gas Cost: ${GAS_COST}/rebalance")
    print(f"   • Slippage: {SLIPPAGE}% on swapped portion")
    print(f"   • Target Period: {TARGET_DAYS} days")
    print(f"   • Ranges: {SCENARIOS}")
    print(f"\n   🔄 Rebalance Strategy:")
    print(f"      When price exits range:")
    print(f"      1. Calculate current USD value")
    print(f"      2. Deduct gas + slippage (on swap half)")
    print(f"      3. New center = CURRENT price (not boundary)")
    print(f"      4. Split 50/50 in USD")
    print(f"      5. Open new position")

    # دریافت داده
    print("\n" + "─" * 65)
    print("📥 Step 1: Fetching 1 Year CAKE/BNB Data")
    print("─" * 65)
    price_data = get_pancakeswap_pair_data(target_days=TARGET_DAYS)

    # آمار
    days = len(price_data) / 24
    price_change = (
        (price_data['close'].iloc[-1] / price_data['close'].iloc[0]) - 1
    ) * 100
    volatility = price_data['close'].pct_change().std() * \
                 np.sqrt(24 * 365) * 100
    cake_change = (
        (price_data['cake_usdt'].iloc[-1] / price_data['cake_usdt'].iloc[0]) - 1
    ) * 100
    bnb_change = (
        (price_data['bnb_usdt'].iloc[-1] / price_data['bnb_usdt'].iloc[0]) - 1
    ) * 100

    print(f"\n📊 Market Stats ({days:.0f} days):")
    print(f"   • CAKE/BNB Change: {price_change:+.2f}%")
    print(f"   • CAKE/USD Change: {cake_change:+.2f}%")
    print(f"   • BNB/USD Change:  {bnb_change:+.2f}%")
    print(f"   • Volatility (Annual): {volatility:.1f}%")

    hodl_cake_amt = (INITIAL_CAPITAL / 2) / price_data['cake_usdt'].iloc[0]
    hodl_bnb_amt = (INITIAL_CAPITAL / 2) / price_data['bnb_usdt'].iloc[0]
    hodl_final = (hodl_cake_amt * price_data['cake_usdt'].iloc[-1] +
                  hodl_bnb_amt * price_data['bnb_usdt'].iloc[-1])
    print(f"\n💰 HODL Benchmark:")
    print(f"   • CAKE bought: {hodl_cake_amt:.2f} @ "
          f"${price_data['cake_usdt'].iloc[0]:.2f}")
    print(f"   • BNB bought:  {hodl_bnb_amt:.4f} @ "
          f"${price_data['bnb_usdt'].iloc[0]:.2f}")
    print(f"   • Final HODL: ${hodl_final:,.2f} "
          f"({((hodl_final / INITIAL_CAPITAL) - 1) * 100:+.2f}%)")

    # بک‌تست
    print("\n" + "─" * 65)
    print("🔬 Step 2: Running Backtest")
    print("─" * 65)
    all_results = run_all_scenarios(price_data, SCENARIOS, INITIAL_CAPITAL)

    # نتایج
    print("\n" + "─" * 65)
    print("📊 Step 3: Results")
    print("─" * 65)
    sorted_results = print_results(all_results)

    # نمودارها
    print("\n" + "─" * 65)
    print("📈 Step 4: Charts")
    print("─" * 65)
    top3 = create_all_charts(all_results, price_data, INITIAL_CAPITAL)

    # CSV
    rows = []
    for r in sorted(all_results.keys()):
        res = all_results[r]
        costs = res['total_gas_costs'] + res['total_slippage_costs']
        rows.append({
            'Range': f'±{r}%',
            'Days': f"{res['days']:.0f}",
            'Active %': f"{res['active_percent']:.1f}%",
            'Rebalances': res['rebalance_count'],
            'Gross Fees ($)': f"${res['total_fees_gross']:,.0f}",
            'Gas+Slippage ($)': f"${costs:,.0f}",
            'Net Fees ($)': f"${res['total_fees_net']:,.0f}",
            'Fee APR': f"{res['fee_apr']:.1f}%",
            'IL (%)': f"{res['impermanent_loss']:.2f}%",
            'Pool Value ($)': f"${res['final_pool_value']:,.0f}",
            'Total Value ($)': f"${res['final_total_value']:,.0f}",
            'HODL Value ($)': f"${res['final_hodl_value']:,.0f}",
            'Total Return': f"{res['total_return']:+.2f}%",
            'vs HODL': f"{res['vs_hodl']:+.2f}%"
        })

    results_df = pd.DataFrame(rows)
    results_df.to_csv('pancakeswap_results_v3.csv',
                      index=False, encoding='utf-8-sig')
    print(f"\n💾 CSV saved: pancakeswap_results_v3.csv")

    # نتیجه
    best = sorted_results[0]
    print("\n" + "═" * 65)
    print("🎯 CONCLUSION")
    print("═" * 65)
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  🥞 PancakeSwap V3 - CAKE/BNB ({days:.0f} days backtest)          
    ║                                                               ║
    ║  🏆 OPTIMAL RANGE: ±{best[0]}%                                     
    ║                                                               ║
    ║  📊 Results:                                                  ║
    ║     • Total Return:    {best[1]['total_return']:+.2f}%                       
    ║     • Net Fees:        ${best[1]['total_fees_net']:,.0f}                    
    ║     • Fee APR:         {best[1]['fee_apr']:.1f}%                           
    ║     • Active Time:     {best[1]['active_percent']:.1f}%                          
    ║     • Rebalances:      {best[1]['rebalance_count']}                              
    ║     • IL:              {best[1]['impermanent_loss']:.2f}%                       
    ║     • vs HODL:         {best[1]['vs_hodl']:+.2f}%                         
    ║                                                               ║
    ║  🔧 Key Fixes in V3:                                         ║
    ║     1. Full 1-year data (was ~3 months)                      ║
    ║     2. Rebalance centers on CURRENT price                    ║
    ║        (was centering on boundary → stayed out of range)     ║
    ║     3. 50/50 USD split with swap cost                        ║
    ║        (slippage only on swapped portion)                    ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

    📁 Files:
       • pancakeswap_optimization_v3.png
       • pancakeswap_top3_v3.png
       • pancakeswap_rebalancing_v3.png
       • pancakeswap_rebalance_visual_v3.png
       • pancakeswap_results_v3.csv
    """)

    print("✅ Analysis Complete!")
    return all_results, price_data


if __name__ == "__main__":
    results, data = main()