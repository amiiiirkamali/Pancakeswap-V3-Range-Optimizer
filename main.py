"""
پروژه بهینه‌سازی استخر نقدینگی V3 - PancakeSwap BSC
جفت‌ارز: CAKE/BNB
═══════════════════════════════════════════════════════════
نسخه ۲: با ریبالانسینگ واقعی + توضیح کامل فرمول‌ها
═══════════════════════════════════════════════════════════

فرمول‌ها و توضیحات:

1. HODL Value (ارزش نگهداری ساده):
   ─────────────────────────────────
   فرض: با $10,000 در لحظه اول، نصف را CAKE و نصف را BNB می‌خریم.

   initial_cake_amount = (initial_capital / 2) / cake_usdt_price_at_start
   initial_bnb_amount  = (initial_capital / 2) / bnb_usdt_price_at_start

   HODL_value(t) = initial_cake_amount × cake_usdt_price(t)
                  + initial_bnb_amount  × bnb_usdt_price(t)

   یعنی: اگر اصلاً کاری نمی‌کردیم و فقط نگه می‌داشتیم، الان چقدر داشتیم؟

2. Impermanent Loss (ضرر ناپایدار):
   ──────────────────────────────────
   برای V3 Concentrated Liquidity:

   ابتدا مقدار token0 و token1 در استخر محاسبه می‌شود:

   اگر price_lower ≤ P ≤ price_upper:
       amount0 = L × (√P_upper - √P) / (√P × √P_upper)
       amount1 = L × (√P - √P_lower)

   اگر P < price_lower (قیمت زیر بازه):
       amount0 = L × (√P_upper - √P_lower) / (√P_lower × √P_upper)
       amount1 = 0
       → تمام دارایی تبدیل به token0 شده

   اگر P > price_upper (قیمت بالای بازه):
       amount0 = 0
       amount1 = L × (√P_upper - √P_lower)
       → تمام دارایی تبدیل به token1 شده

   pool_value = amount0 × P_cake_usdt + amount1 × P_bnb_usdt  (به دلار)

   IL% = (pool_value / hodl_value - 1) × 100

   اگر IL منفی باشد → ضرر ناپایدار (معمول)
   اگر IL مثبت باشد → سود ناپایدار (نادر)

3. ریبالانسینگ:
   ─────────────
   وقتی قیمت CAKE/BNB از بازه [P_lower, P_upper] خارج می‌شود:

   الف) اگر از بالا خارج شد (P > P_upper):
        - قیمت جدید مرکز = P_upper (نقطه خروج)
        - بازه جدید = [P_upper × (1 - range%), P_upper × (1 + range%)]

   ب) اگر از پایین خارج شد (P < P_lower):
        - قیمت جدید مرکز = P_lower (نقطه خروج)
        - بازه جدید = [P_lower × (1 - range%), P_lower × (1 + range%)]

   در هر ریبالانس:
        - نقدینگی فعلی برداشت می‌شود (withdraw)
        - هزینه گس پرداخت می‌شود
        - ممکن است اسلیپیج داشته باشیم
        - نقدینگی جدید ۵۰/۵۰ روی قیمت مرکز جدید قرار می‌گیرد

4. نمودار مقایسه نهایی:
   ─────────────────────
   سه مقدار نمایش داده می‌شود:

   "Pool Value" (ارزش استخر) = ارزش دلاری دارایی‌های درون استخر
                                بدون احتساب کارمزدها
                                (این مقدار IL را شامل می‌شود)

   "Pool + Fees" (ارزش نهایی) = Pool Value + مجموع کارمزدهای دریافتی
                                  = آنچه واقعاً دارید
                                  = سرمایه نهایی شما

   "HODL" (نگهداری ساده) = اگر هیچ کاری نمی‌کردید
                            و فقط ۵۰/۵۰ نگه می‌داشتید
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import requests
import warnings
from datetime import datetime

warnings.filterwarnings('ignore')


# ═══════════════════════════════════════════════════════════
# بخش ۱: دریافت داده‌های CAKE/BNB
# ═══════════════════════════════════════════════════════════

def get_pancakeswap_pair_data():
    """
    دریافت داده‌های CAKE/BNB برای PancakeSwap
    از ترکیب CAKE/USDT و BNB/USDT محاسبه می‌شود.

    همچنین قیمت‌های دلاری هر توکن را نگه می‌داریم
    برای محاسبه دقیق HODL و ارزش پوزیشن به دلار.
    """
    print("📥 دریافت داده‌های CAKE/BNB برای PancakeSwap...")

    url = 'https://api.binance.com/api/v3/klines'
    all_cake = []
    all_bnb = []

    end_time = int(datetime.now().timestamp() * 1000)

    print("\n   دریافت CAKE/USDT...")
    for i in range(9):
        params = {
            'symbol': 'CAKEUSDT',
            'interval': '1h',
            'limit': 1000,
            'endTime': end_time if i == 0 else end_time_cake
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if len(data) == 0:
                break
            all_cake = data + all_cake
            end_time_cake = data[0][0] - 1
            print(f"      ✓ بخش {i + 1}/9")
        except Exception as e:
            print(f"      ✗ خطا: {e}")
            break

    print("\n   دریافت BNB/USDT...")
    end_time = int(datetime.now().timestamp() * 1000)
    for i in range(9):
        params = {
            'symbol': 'BNBUSDT',
            'interval': '1h',
            'limit': 1000,
            'endTime': end_time if i == 0 else end_time_bnb
        }
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if len(data) == 0:
                break
            all_bnb = data + all_bnb
            end_time_bnb = data[0][0] - 1
            print(f"      ✓ بخش {i + 1}/9")
        except Exception as e:
            print(f"      ✗ خطا: {e}")
            break

    df_cake = pd.DataFrame(all_cake, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    df_bnb = pd.DataFrame(all_bnb, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume',
        'close_time', 'quote_volume', 'trades', 'taker_buy_base',
        'taker_buy_quote', 'ignore'
    ])

    for df_temp in [df_cake, df_bnb]:
        df_temp['timestamp'] = pd.to_datetime(df_temp['timestamp'], unit='ms')
        df_temp['close'] = df_temp['close'].astype(float)
        df_temp['high'] = df_temp['high'].astype(float)
        df_temp['low'] = df_temp['low'].astype(float)
        df_temp['volume'] = df_temp['volume'].astype(float)
        df_temp['quote_volume'] = df_temp['quote_volume'].astype(float)

    df_cake = df_cake.drop_duplicates(subset='timestamp').set_index('timestamp')
    df_bnb = df_bnb.drop_duplicates(subset='timestamp').set_index('timestamp')

    df = pd.DataFrame()
    df['cake_usdt'] = df_cake['close']
    df['bnb_usdt'] = df_bnb['close']
    df['cake_volume'] = df_cake['quote_volume']
    df['bnb_volume'] = df_bnb['quote_volume']

    df = df.dropna()

    # نسبت CAKE/BNB
    df['close'] = df['cake_usdt'] / df['bnb_usdt']
    df['quote_volume'] = (df['cake_volume'] + df['bnb_volume']) / 2

    df = df.reset_index()

    days = len(df) / 24
    print(f"\n✅ داده‌های CAKE/BNB آماده شد")
    print(f"   📊 تعداد کندل: {len(df)} ({days:.0f} روز)")
    print(f"   📅 از: {df['timestamp'].iloc[0]}")
    print(f"   📅 تا: {df['timestamp'].iloc[-1]}")
    print(f"   💰 CAKE/BNB اولیه: {df['close'].iloc[0]:.6f}")
    print(f"   💰 CAKE/BNB نهایی: {df['close'].iloc[-1]:.6f}")
    print(f"   💰 CAKE اولیه: ${df['cake_usdt'].iloc[0]:.2f}")
    print(f"   💰 BNB اولیه: ${df['bnb_usdt'].iloc[0]:.2f}")
    print(f"   💰 CAKE نهایی: ${df['cake_usdt'].iloc[-1]:.2f}")
    print(f"   💰 BNB نهایی: ${df['bnb_usdt'].iloc[-1]:.2f}")

    return df


# ═══════════════════════════════════════════════════════════
# بخش ۲: کلاس استخر V3 با ریبالانسینگ
# ═══════════════════════════════════════════════════════════

class LiquidityPositionV3:
    """
    یک پوزیشن Concentrated Liquidity در V3.

    فرمول‌های اصلی Uniswap V3:
    ──────────────────────────

    L (نقدینگی) از سمت token0:
        L = amount0 × (√P × √P_upper) / (√P_upper - √P)

    L از سمت token1:
        L = amount1 / (√P - √P_lower)

    L نهایی = min(L0, L1) → برای اینکه هر دو طرف کافی باشد

    محاسبه مقدار توکن‌ها در قیمت P:
        اگر P_lower ≤ P ≤ P_upper:
            amount0 = L × (√P_upper - √P) / (√P × √P_upper)
            amount1 = L × (√P - √P_lower)
        اگر P < P_lower:
            amount0 = L × (√P_upper - √P_lower) / (√P_lower × √P_upper)
            amount1 = 0
        اگر P > P_upper:
            amount0 = 0
            amount1 = L × (√P_upper - √P_lower)
    """

    def __init__(self):
        self.L = 0
        self.price_lower = 0
        self.price_upper = 0
        self.center_price = 0

    def open_position(self, capital_usd, center_price, range_percent,
                      cake_usdt_price, bnb_usdt_price):
        """
        باز کردن پوزیشن جدید:
        - capital_usd: سرمایه به دلار
        - center_price: قیمت مرکزی (CAKE/BNB)
        - range_percent: درصد بازه (مثلاً 2 یعنی ±2%)
        - cake_usdt_price: قیمت CAKE به دلار (برای تبدیل)
        - bnb_usdt_price: قیمت BNB به دلار (برای تبدیل)
        """
        self.center_price = center_price
        self.range_percent = range_percent
        self.price_lower = center_price * (1 - range_percent / 100)
        self.price_upper = center_price * (1 + range_percent / 100)

        # نصف سرمایه به CAKE، نصف به BNB
        # amount0 = مقدار CAKE (بر حسب CAKE)
        # amount1 = مقدار BNB (بر حسب BNB)
        usd_per_side = capital_usd / 2
        amount0_cake = usd_per_side / cake_usdt_price  # تعداد CAKE
        amount1_bnb = usd_per_side / bnb_usdt_price    # تعداد BNB

        # ذخیره مقادیر اولیه (برای HODL نیاز نداریم،
        # اما اینجا برای اطلاع)
        self.initial_amount0 = amount0_cake
        self.initial_amount1 = amount1_bnb

        sqrt_p = np.sqrt(center_price)
        sqrt_pa = np.sqrt(self.price_lower)
        sqrt_pb = np.sqrt(self.price_upper)

        # محاسبه L بر حسب جفت CAKE/BNB
        # amount0 بر حسب CAKE، قیمت CAKE/BNB
        if sqrt_pb - sqrt_p > 1e-15:
            L0 = amount0_cake * (sqrt_p * sqrt_pb) / (sqrt_pb - sqrt_p)
        else:
            L0 = 0

        # amount1 بر حسب BNB
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
        """آیا قیمت CAKE/BNB در بازه است؟"""
        return self.price_lower <= price <= self.price_upper

    def get_amounts(self, current_price_cake_bnb):
        """
        مقدار CAKE و BNB در پوزیشن فعلی.

        بازگشت: (amount_cake, amount_bnb)
        """
        P = current_price_cake_bnb
        sqrt_p = np.sqrt(P)
        sqrt_pa = np.sqrt(self.price_lower)
        sqrt_pb = np.sqrt(self.price_upper)

        if P <= self.price_lower:
            # تمام دارایی CAKE شده
            amount0 = self.L * (sqrt_pb - sqrt_pa) / (sqrt_pa * sqrt_pb) \
                if sqrt_pa * sqrt_pb > 0 else 0
            amount1 = 0
        elif P >= self.price_upper:
            # تمام دارایی BNB شده
            amount0 = 0
            amount1 = self.L * (sqrt_pb - sqrt_pa)
        else:
            # در بازه
            amount0 = self.L * (sqrt_pb - sqrt_p) / (sqrt_p * sqrt_pb) \
                if sqrt_p * sqrt_pb > 0 else 0
            amount1 = self.L * (sqrt_p - sqrt_pa)

        return amount0, amount1  # (CAKE, BNB)

    def get_value_usd(self, cake_bnb_price, cake_usdt, bnb_usdt):
        """
        ارزش دلاری پوزیشن.

        amount_cake × cake_usdt + amount_bnb × bnb_usdt
        """
        amount_cake, amount_bnb = self.get_amounts(cake_bnb_price)
        return amount_cake * cake_usdt + amount_bnb * bnb_usdt


# ═══════════════════════════════════════════════════════════
# بخش ۳: بک‌تست با ریبالانسینگ
# ═══════════════════════════════════════════════════════════

def run_backtest_with_rebalance(price_data, range_percent,
                                 initial_capital=10000, fee_tier=0.25,
                                 gas_cost_usd=0.30, slippage_pct=0.1):
    """
    بک‌تست با ریبالانسینگ واقعی.

    منطق ریبالانسینگ:
    ──────────────────
    1. پوزیشن اولیه: مرکز = قیمت فعلی، بازه = ±range_percent%
    2. هر ساعت بررسی می‌شود:
       - اگر قیمت در بازه → کارمزد جمع می‌شود
       - اگر قیمت خارج بازه → ریبالانس:
         • از هر طرف که خارج شد (بالا/پایین)، آن حد به عنوان مرکز جدید
         • بازه جدید = مرکز جدید ± range_percent%
         • هزینه گس کسر می‌شود
         • اسلیپیج کسر می‌شود

    Parameters:
    ──────────
    price_data: DataFrame با ستون‌های close, cake_usdt, bnb_usdt, quote_volume
    range_percent: درصد بازه (مثلاً 2 → ±2%)
    initial_capital: سرمایه اولیه ($)
    fee_tier: درصد کارمزد (0.25%)
    gas_cost_usd: هزینه هر ریبالانس ($) - در BSC ارزان
    slippage_pct: اسلیپیج هر ریبالانس (%)
    """
    fee_rate = fee_tier / 100

    # ─── HODL: ذخیره مقادیر اولیه ───
    initial_cake_usdt = price_data['cake_usdt'].iloc[0]
    initial_bnb_usdt = price_data['bnb_usdt'].iloc[0]

    # HODL: نصف سرمایه CAKE، نصف BNB خریداری می‌شود
    hodl_cake_amount = (initial_capital / 2) / initial_cake_usdt
    hodl_bnb_amount = (initial_capital / 2) / initial_bnb_usdt

    # ─── پوزیشن اولیه ───
    position = LiquidityPositionV3()
    entry_price = price_data['close'].iloc[0]
    current_capital = initial_capital  # سرمایه در دسترس
    position.open_position(
        current_capital, entry_price, range_percent,
        initial_cake_usdt, initial_bnb_usdt
    )

    # ─── متغیرهای ردیابی ───
    total_fees_usd = 0
    total_gas_costs = 0
    total_slippage_costs = 0
    rebalance_count = 0
    periods_in_range = 0
    periods_out_of_range = 0

    fee_history = []
    pool_value_history = []
    hodl_value_history = []
    total_value_history = []  # pool + fees - costs
    rebalance_timestamps = []
    range_history = []  # ذخیره بازه‌ها

    # حجم و TVL تخمینی
    avg_daily_volume = price_data['quote_volume'].mean() * 24
    estimated_tvl = avg_daily_volume * 5
    our_share = min(initial_capital / estimated_tvl, 0.1)

    was_in_range = True

    for idx in range(len(price_data)):
        row = price_data.iloc[idx]
        price_cake_bnb = row['close']
        cake_usdt = row['cake_usdt']
        bnb_usdt = row['bnb_usdt']
        volume = row['quote_volume']

        in_range = position.is_in_range(price_cake_bnb)

        # ─── ریبالانسینگ ───
        if not in_range and was_in_range:
            # قیمت تازه از بازه خارج شده → ریبالانس

            # 1. ارزش فعلی پوزیشن (قبل از ریبالانس)
            current_pool_value = position.get_value_usd(
                price_cake_bnb, cake_usdt, bnb_usdt
            )

            # 2. هزینه‌های ریبالانس
            gas = gas_cost_usd
            slippage = current_pool_value * (slippage_pct / 100)
            total_gas_costs += gas
            total_slippage_costs += slippage

            rebalance_capital = current_pool_value - gas - slippage

            # 3. مرکز جدید = نقطه خروج
            if price_cake_bnb >= position.price_upper:
                new_center = position.price_upper
            else:
                new_center = position.price_lower

            # 4. باز کردن پوزیشن جدید
            position = LiquidityPositionV3()
            position.open_position(
                max(rebalance_capital, 0),
                new_center, range_percent,
                cake_usdt, bnb_usdt
            )

            rebalance_count += 1
            rebalance_timestamps.append(row['timestamp'])

            # بررسی مجدد آیا در بازه جدید هست
            in_range = position.is_in_range(price_cake_bnb)

        # ─── محاسبه کارمزد ───
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

        was_in_range = in_range

        # ─── ثبت ارزش‌ها ───
        pool_val = position.get_value_usd(price_cake_bnb, cake_usdt, bnb_usdt)
        hodl_val = hodl_cake_amount * cake_usdt + hodl_bnb_amount * bnb_usdt
        total_val = pool_val + total_fees_usd - total_gas_costs - total_slippage_costs

        pool_value_history.append(pool_val)
        hodl_value_history.append(hodl_val)
        total_value_history.append(total_val)

        range_history.append({
            'lower': position.price_lower,
            'upper': position.price_upper,
            'center': position.center_price
        })

    # ─── نتایج نهایی ───
    final_cake_usdt = price_data['cake_usdt'].iloc[-1]
    final_bnb_usdt = price_data['bnb_usdt'].iloc[-1]
    final_cake_bnb = price_data['close'].iloc[-1]

    final_pool_value = position.get_value_usd(
        final_cake_bnb, final_cake_usdt, final_bnb_usdt
    )
    final_hodl_value = hodl_cake_amount * final_cake_usdt + \
                       hodl_bnb_amount * final_bnb_usdt

    net_fees = total_fees_usd - total_gas_costs - total_slippage_costs
    final_total_value = final_pool_value + net_fees

    # IL محاسبه
    if final_hodl_value > 0:
        il_percent = (final_pool_value / final_hodl_value - 1) * 100
    else:
        il_percent = 0

    total_periods = len(price_data)
    active_percent = (periods_in_range / total_periods) * 100
    days = total_periods / 24

    total_return = ((final_total_value - initial_capital) / initial_capital) * 100
    fee_apr = (net_fees / initial_capital) * (365 / days) * 100
    vs_hodl = ((final_total_value - final_hodl_value) / final_hodl_value) * 100 \
        if final_hodl_value > 0 else 0

    results = {
        'range_percent': range_percent,
        'entry_price': entry_price,

        # بازه فعلی (آخرین)
        'price_lower': position.price_lower,
        'price_upper': position.price_upper,

        # فعالیت
        'active_percent': active_percent,
        'periods_in_range': periods_in_range,
        'periods_out_of_range': periods_out_of_range,

        # ریبالانسینگ
        'rebalance_count': rebalance_count,
        'total_gas_costs': total_gas_costs,
        'total_slippage_costs': total_slippage_costs,
        'rebalance_timestamps': rebalance_timestamps,

        # کارمزد
        'total_fees_gross': total_fees_usd,
        'total_fees_net': net_fees,
        'fee_apr': fee_apr,

        # ارزش‌ها
        'final_pool_value': final_pool_value,
        'final_hodl_value': final_hodl_value,
        'final_total_value': final_total_value,

        # درصدها
        'impermanent_loss': il_percent,
        'total_return': total_return,
        'vs_hodl': vs_hodl,

        # تاریخچه
        'fee_history': fee_history,
        'pool_value_history': pool_value_history,
        'hodl_value_history': hodl_value_history,
        'total_value_history': total_value_history,
        'range_history': range_history,
    }

    return results


def run_all_scenarios(price_data, scenarios, initial_capital=10000):
    """اجرای بک‌تست برای همه بازه‌ها"""
    print("\n" + "═" * 80)
    print("🚀 شروع بک‌تست با ریبالانسینگ - PancakeSwap V3 - CAKE/BNB")
    print("═" * 80)
    print(f"{'بازه':^8} │ {'فعال%':^8} │ {'ریبالانس':^10} │ "
          f"{'کارمزد خالص':^14} │ {'APR':^8} │ {'بازده':^10}")
    print("─" * 80)

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

    print("─" * 80)
    return all_results


# ═══════════════════════════════════════════════════════════
# بخش ۴: نمودارها (اصلاح‌شده و واضح)
# ═══════════════════════════════════════════════════════════

def create_all_charts(all_results, price_data):
    """ساخت همه نمودارها با توضیحات واضح"""

    ranges = sorted(all_results.keys())
    sorted_results = sorted(
        all_results.items(),
        key=lambda x: x[1]['total_return'], reverse=True
    )
    top3 = [r[0] for r in sorted_results[:3]]

    # ═══════════════════════════════════════════════════════════
    # نمودار ۱: بهینه‌سازی کلی
    # ═══════════════════════════════════════════════════════════
    print("\n📊 ساخت نمودار ۱: بهینه‌سازی کلی...")

    fig1, axes1 = plt.subplots(2, 3, figsize=(20, 13))
    fig1.suptitle(
        'PancakeSwap V3 - CAKE/BNB - Optimization with Rebalancing\n'
        '(Initial Capital: $10,000 | Fee: 0.25% | 1 Year Backtest)',
        fontsize=15, fontweight='bold'
    )

    # 1-1: قیمت
    ax = axes1[0, 0]
    ax.plot(price_data['timestamp'], price_data['close'],
            color='#F0B90B', linewidth=0.8)
    ax.set_title('CAKE/BNB Price Over Time', fontsize=11, fontweight='bold')
    ax.set_ylabel('Price (CAKE per BNB)')
    ax.grid(True, alpha=0.3)

    # 1-2: بازده کل (با ریبالانس)
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
    best_idx = returns.index(max(returns))
    bars[best_idx].set_edgecolor('gold')
    bars[best_idx].set_linewidth(3)

    # 1-3: درصد فعال بودن (مجموع ساعاتی که در بازه بوده)
    ax = axes1[0, 2]
    active = [all_results[r]['active_percent'] for r in ranges]
    ax.plot(ranges, active, 'o-', color='#3498db', linewidth=2, markersize=8)
    ax.fill_between(ranges, active, alpha=0.2, color='#3498db')
    ax.set_title(
        'Time In Range (with Rebalancing)\n'
        'Hours active / Total hours × 100',
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
        '(Each rebalance costs gas + slippage)',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Count')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, fontsize=8)
    ax.grid(True, alpha=0.3, axis='y')

    # 1-5: Fee APR خالص
    ax = axes1[1, 1]
    aprs = [all_results[r]['fee_apr'] for r in ranges]
    ax.plot(ranges, aprs, 's-', color='#9b59b6', linewidth=2, markersize=8)
    ax.set_title(
        'Net Fee APR (after gas & slippage)\n'
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
    ax.set_title('Return vs Active Time Trade-off', fontsize=11, fontweight='bold')
    ax.set_xlabel('Time Active (%)')
    ax.set_ylabel('Total Return (%)')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range Width (%)')

    plt.tight_layout()
    plt.savefig('pancakeswap_optimization_v2.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_optimization_v2.png")
    plt.close(fig1)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۲: مقایسه ۳ بازه برتر
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۲: مقایسه ۳ برتر...")

    fig2, axes2 = plt.subplots(2, 2, figsize=(16, 12))
    fig2.suptitle(
        'PancakeSwap V3 - Top 3 Ranges Detailed Comparison\n'
        '(with Rebalancing)',
        fontsize=15, fontweight='bold'
    )

    colors_top3 = {
        top3[0]: '#27ae60',
        top3[1]: '#3498db',
        top3[2]: '#f39c12'
    }

    # 2-1: ارزش کل در طول زمان
    ax = axes2[0, 0]
    for r in top3:
        result = all_results[r]
        ax.plot(price_data['timestamp'], result['total_value_history'],
                label=f'±{r}% (rebal: {result["rebalance_count"]}x)',
                color=colors_top3[r], linewidth=1.5)

    # HODL هم نشان بده
    ax.plot(price_data['timestamp'],
            all_results[top3[0]]['hodl_value_history'],
            label='HODL (50/50 buy & hold)',
            color='gray', linewidth=2, linestyle='--')
    ax.axhline(y=initial_capital, color='red', linestyle=':',
               alpha=0.5, label=f'Initial: ${initial_capital:,}')

    ax.set_title(
        'Portfolio Value Over Time\n'
        '"Total Value" = Pool Value + Cumulative Fees - Gas - Slippage',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Value ($)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 2-2: تجمعی کارمزد خالص
    ax = axes2[0, 1]
    for r in top3:
        result = all_results[r]
        cum_fees = np.cumsum(result['fee_history'])
        # کسر هزینه‌های تجمعی ریبالانس
        gas_per_rebalance = 0.30
        slip_per_rebalance = result['total_slippage_costs'] / max(
            result['rebalance_count'], 1)

        # ساخت خط هزینه تجمعی (تقریبی)
        ax.plot(price_data['timestamp'], cum_fees,
                label=f'±{r}% gross fees',
                color=colors_top3[r], linewidth=1.5)

    ax.set_title(
        'Cumulative Fees Earned (Gross)\n'
        'Net = Gross - Gas Costs - Slippage',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Fees ($)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 2-3: مقایسه ارزش نهایی - با توضیح واضح
    ax = axes2[1, 0]
    x = np.arange(len(top3))
    width = 0.2

    # سه مقدار برای هر بازه:
    pool_vals = []  # ارزش دارایی‌های درون استخر (بدون fees)
    total_vals = []  # ارزش کل = pool + fees - costs
    hodl_vals = []  # ارزش HODL

    for r in top3:
        res = all_results[r]
        pool_vals.append(res['final_pool_value'])
        total_vals.append(res['final_total_value'])
        hodl_vals.append(res['final_hodl_value'])

    bars1 = ax.bar(x - width, pool_vals, width,
                   label='Pool Value\n(assets in pool, includes IL)',
                   color='#3498db', alpha=0.8)
    bars2 = ax.bar(x, total_vals, width,
                   label='Total Value\n(pool + fees - gas - slippage)\n= YOUR ACTUAL MONEY',
                   color='#27ae60', alpha=0.8)
    bars3 = ax.bar(x + width, hodl_vals, width,
                   label='HODL Value\n(if you just held 50/50)',
                   color='#95a5a6', alpha=0.8)

    ax.axhline(y=initial_capital, color='red', linestyle='--',
               alpha=0.7, linewidth=2,
               label=f'Initial Capital: ${initial_capital:,}')

    # نوشتن مقادیر روی بارها
    for i, (p, t, h) in enumerate(zip(pool_vals, total_vals, hodl_vals)):
        ax.text(x[i] - width, p + 100, f'${p:,.0f}',
                ha='center', va='bottom', fontsize=7, fontweight='bold')
        ax.text(x[i], t + 100, f'${t:,.0f}',
                ha='center', va='bottom', fontsize=7, fontweight='bold',
                color='darkgreen')
        ax.text(x[i] + width, h + 100, f'${h:,.0f}',
                ha='center', va='bottom', fontsize=7, fontweight='bold')

    ax.set_title(
        'Final Value Comparison (After 1 Year)\n'
        'Green bar = What you actually have',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Value ($)')
    ax.set_xticks(x)
    ax.set_xticklabels([f'±{r}%' for r in top3])
    ax.legend(fontsize=7, loc='upper right')
    ax.grid(True, alpha=0.3, axis='y')

    # 2-4: جدول خلاصه
    ax = axes2[1, 1]
    ax.axis('off')

    table_data = []
    headers = [
        'Range', 'Active%', 'Rebalances',
        'Gross Fees', 'Gas+Slip', 'Net Fees',
        'Fee APR', 'IL%', 'Total Return', 'vs HODL'
    ]

    for r in top3:
        res = all_results[r]
        table_data.append([
            f'±{r}%',
            f"{res['active_percent']:.1f}%",
            f"{res['rebalance_count']}",
            f"${res['total_fees_gross']:,.0f}",
            f"${res['total_gas_costs'] + res['total_slippage_costs']:,.0f}",
            f"${res['total_fees_net']:,.0f}",
            f"{res['fee_apr']:.1f}%",
            f"{res['impermanent_loss']:.2f}%",
            f"{res['total_return']:+.2f}%",
            f"{res['vs_hodl']:+.2f}%"
        ])

    table = ax.table(
        cellText=table_data,
        colLabels=headers,
        loc='center', cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    table.scale(1.3, 2.2)

    # رنگ‌بندی
    for j in range(len(headers)):
        table[(0, j)].set_facecolor('#F0B90B')
        table[(0, j)].set_text_props(fontweight='bold', fontsize=7)
        table[(1, j)].set_facecolor('#d5f5e3')  # بهترین

    ax.set_title('Detailed Summary (Top 3)',
                 fontsize=11, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig('pancakeswap_top3_v2.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_top3_v2.png")
    plt.close(fig2)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۳: ریبالانسینگ و هزینه‌ها
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۳: تحلیل ریبالانسینگ...")

    fig3, axes3 = plt.subplots(2, 2, figsize=(16, 12))
    fig3.suptitle(
        'PancakeSwap V3 - Rebalancing Analysis\n'
        'Impact of rebalancing frequency on returns',
        fontsize=14, fontweight='bold'
    )

    # 3-1: تعداد ریبالانس vs بازده
    ax = axes3[0, 0]
    rebalances = [all_results[r]['rebalance_count'] for r in ranges]
    returns_list = [all_results[r]['total_return'] for r in ranges]
    scatter = ax.scatter(rebalances, returns_list, c=ranges,
                         cmap='viridis', s=200, edgecolors='black', zorder=5)
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (rebalances[i], returns_list[i]),
                    textcoords="offset points", xytext=(5, 8), fontsize=9)
    ax.set_title('Total Return vs Rebalance Count', fontsize=11, fontweight='bold')
    ax.set_xlabel('Number of Rebalances')
    ax.set_ylabel('Total Return (%)')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    # 3-2: هزینه‌های ریبالانس
    ax = axes3[0, 1]
    gas_costs = [all_results[r]['total_gas_costs'] for r in ranges]
    slip_costs = [all_results[r]['total_slippage_costs'] for r in ranges]
    x_pos = np.arange(len(ranges))
    ax.bar(x_pos, gas_costs, 0.4, label='Gas Costs', color='#e74c3c')
    ax.bar(x_pos, slip_costs, 0.4, bottom=gas_costs,
           label='Slippage Costs', color='#f39c12')
    ax.set_title(
        'Rebalancing Costs\n'
        '(Gas: $0.30/tx on BSC, Slippage: 0.1%)',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Cost ($)')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'±{r}%' for r in ranges], fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # 3-3: کارمزد خالص vs ناخالص
    ax = axes3[1, 0]
    gross_fees = [all_results[r]['total_fees_gross'] for r in ranges]
    net_fees = [all_results[r]['total_fees_net'] for r in ranges]
    ax.bar(x_pos - 0.2, gross_fees, 0.35,
           label='Gross Fees (before costs)', color='#3498db')
    ax.bar(x_pos + 0.2, net_fees, 0.35,
           label='Net Fees (after gas + slippage)', color='#27ae60')
    ax.set_title(
        'Gross vs Net Fees\n'
        'Net = Gross - Gas - Slippage',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Fees ($)')
    ax.set_xticks(x_pos)
    ax.set_xticklabels([f'±{r}%' for r in ranges], fontsize=8)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # 3-4: APR vs ریبالانس
    ax = axes3[1, 1]
    aprs = [all_results[r]['fee_apr'] for r in ranges]
    scatter = ax.scatter(rebalances, aprs, c=ranges,
                         cmap='plasma', s=200, edgecolors='black', zorder=5)
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (rebalances[i], aprs[i]),
                    textcoords="offset points", xytext=(5, 8), fontsize=9)
    ax.set_title('Net Fee APR vs Rebalance Count', fontsize=11, fontweight='bold')
    ax.set_xlabel('Number of Rebalances')
    ax.set_ylabel('Net Fee APR (%)')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    plt.tight_layout()
    plt.savefig('pancakeswap_rebalancing_v2.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_rebalancing_v2.png")
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
        f'PancakeSwap V3 - Rebalancing Visualization for ±{best_range}%\n'
        f'({best_result["rebalance_count"]} rebalances over 1 year)',
        fontsize=14, fontweight='bold'
    )

    # 4-1: قیمت با بازه‌های متحرک
    ax = axes4[0]
    timestamps = price_data['timestamp']
    prices = price_data['close']

    ax.plot(timestamps, prices, color='#2c3e50', linewidth=0.8,
            label='CAKE/BNB Price', zorder=3)

    # رسم بازه‌ها
    range_lowers = [rh['lower'] for rh in best_result['range_history']]
    range_uppers = [rh['upper'] for rh in best_result['range_history']]

    ax.fill_between(timestamps, range_lowers, range_uppers,
                    alpha=0.15, color='green', label='Active Range')
    ax.plot(timestamps, range_lowers, color='green',
            linewidth=0.5, alpha=0.5)
    ax.plot(timestamps, range_uppers, color='green',
            linewidth=0.5, alpha=0.5)

    # نقاط ریبالانس
    for ts in best_result['rebalance_timestamps'][:50]:  # حداکثر 50 تا نمایش
        ax.axvline(x=ts, color='red', alpha=0.3, linewidth=0.5)

    ax.set_title(
        f'Price with Dynamic Range (±{best_range}%)\n'
        'Red lines = Rebalance points | Green area = Active range',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('CAKE/BNB')
    ax.legend(loc='upper right')
    ax.grid(True, alpha=0.3)

    # 4-2: مقایسه ارزش
    ax = axes4[1]
    ax.plot(timestamps, best_result['total_value_history'],
            color='#27ae60', linewidth=1.5,
            label=f'LP Strategy (±{best_range}%): '
                  f'Pool + Fees - Costs = ${best_result["final_total_value"]:,.0f}')
    ax.plot(timestamps, best_result['hodl_value_history'],
            color='#95a5a6', linewidth=1.5, linestyle='--',
            label=f'HODL (50/50): ${best_result["final_hodl_value"]:,.0f}')
    ax.axhline(y=initial_capital, color='red', linestyle=':',
               alpha=0.5, label=f'Initial: ${initial_capital:,}')

    ax.set_title(
        'Portfolio Value: LP Strategy vs HODL\n'
        '"Total Value" = Pool assets + Earned fees - Gas costs - Slippage',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Value ($)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    # 4-3: تجمعی کارمزد
    ax = axes4[2]
    cum_fees = np.cumsum(best_result['fee_history'])
    ax.plot(timestamps, cum_fees, color='#F0B90B', linewidth=1.5,
            label=f'Cumulative Fees: ${best_result["total_fees_gross"]:,.0f}')
    ax.axhline(
        y=best_result['total_gas_costs'] + best_result['total_slippage_costs'],
        color='red', linestyle='--', alpha=0.7,
        label=f'Total Costs (gas+slip): '
              f'${best_result["total_gas_costs"] + best_result["total_slippage_costs"]:,.0f}'
    )
    ax.set_title(
        'Cumulative Fees Earned',
        fontsize=10, fontweight='bold'
    )
    ax.set_ylabel('Fees ($)')
    ax.set_xlabel('Date')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('pancakeswap_rebalance_visual_v2.png', dpi=300,
                bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_rebalance_visual_v2.png")
    plt.close(fig4)

    print("\n✅ همه نمودارها ساخته شدند!")
    return top3


# ═══════════════════════════════════════════════════════════
# بخش ۵: جدول نتایج
# ═══════════════════════════════════════════════════════════

def print_results(all_results):
    """چاپ جدول کامل نتایج"""
    print("\n" + "═" * 140)
    print("📋 جدول کامل نتایج - PancakeSwap V3 - CAKE/BNB (با ریبالانسینگ)")
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

    # ─── توضیح فرمول‌ها ───
    print("\n📐 توضیح فرمول‌ها:")
    print("─" * 60)
    print("""
    HODL Value = (اولیه CAKE تعداد × فعلی CAKE قیمت) + (اولیه BNB تعداد × فعلی BNB قیمت)
    
    Pool Value = مقدار CAKE در استخر × قیمت CAKE + مقدار BNB در استخر × قیمت BNB
                 (این شامل IL هست)
    
    IL% = (Pool Value / HODL Value - 1) × 100
          اگر منفی → ضرر ناپایدار
    
    Total Value = Pool Value + Σ(Fees) - Σ(Gas) - Σ(Slippage)
                = آنچه واقعاً در پایان دارید
    
    Total Return = (Total Value - Initial Capital) / Initial Capital × 100
    
    Fee APR = (Net Fees / Capital) × (365 / days) × 100
    
    vs HODL = (Total Value - HODL Value) / HODL Value × 100
    """)

    return sorted_results


# ═══════════════════════════════════════════════════════════
# بخش ۶: تابع اصلی
# ═══════════════════════════════════════════════════════════

# سرمایه اولیه - تعریف به عنوان متغیر سطح ماژول
initial_capital = 10000


def main():
    global initial_capital

    print("╔" + "═" * 65 + "╗")
    print("║  🥞 PancakeSwap V3 - Concentrated Liquidity Optimization     ║")
    print("║  📊 Pair: CAKE/BNB on BSC                                    ║")
    print("║  🔄 Version 2: WITH REBALANCING                              ║")
    print("╚" + "═" * 65 + "╝")

    INITIAL_CAPITAL = initial_capital
    FEE_TIER = 0.25
    SCENARIOS = [2, 3, 4, 5, 7, 10, 15, 20, 25, 30, 40, 50]
    GAS_COST = 0.30     # هزینه گس BSC (ارزان)
    SLIPPAGE = 0.1      # اسلیپیج 0.1%

    print(f"\n⚙️ Settings:")
    print(f"   • DEX: PancakeSwap V3")
    print(f"   • Chain: BNB Smart Chain (BSC)")
    print(f"   • Pair: CAKE/BNB")
    print(f"   • Capital: ${INITIAL_CAPITAL:,}")
    print(f"   • Fee Tier: {FEE_TIER}%")
    print(f"   • Gas Cost per Rebalance: ${GAS_COST}")
    print(f"   • Slippage per Rebalance: {SLIPPAGE}%")
    print(f"   • Ranges: {SCENARIOS}")
    print(f"   • Rebalance Strategy: Rebalance when price exits range")
    print(f"     → New center = exit boundary price")
    print(f"     → New range = new center ± range%")

    # دریافت داده
    print("\n" + "─" * 65)
    print("📥 Step 1: Fetching CAKE/BNB Data")
    print("─" * 65)
    price_data = get_pancakeswap_pair_data()

    # آمار
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

    print(f"\n📊 Market Stats:")
    print(f"   • CAKE/BNB Change: {price_change:+.2f}%")
    print(f"   • CAKE/USD Change: {cake_change:+.2f}%")
    print(f"   • BNB/USD Change:  {bnb_change:+.2f}%")
    print(f"   • Volatility (Annual): {volatility:.1f}%")

    # HODL ارزش نهایی
    hodl_cake_amt = (INITIAL_CAPITAL / 2) / price_data['cake_usdt'].iloc[0]
    hodl_bnb_amt = (INITIAL_CAPITAL / 2) / price_data['bnb_usdt'].iloc[0]
    hodl_final = (hodl_cake_amt * price_data['cake_usdt'].iloc[-1] +
                  hodl_bnb_amt * price_data['bnb_usdt'].iloc[-1])
    print(f"\n💰 HODL Benchmark:")
    print(f"   • Initial CAKE: {hodl_cake_amt:.2f} CAKE "
          f"(${INITIAL_CAPITAL / 2:,.0f})")
    print(f"   • Initial BNB:  {hodl_bnb_amt:.4f} BNB "
          f"(${INITIAL_CAPITAL / 2:,.0f})")
    print(f"   • Final HODL Value: ${hodl_final:,.2f} "
          f"({((hodl_final / INITIAL_CAPITAL) - 1) * 100:+.2f}%)")

    # بک‌تست
    print("\n" + "─" * 65)
    print("🔬 Step 2: Running Backtest with Rebalancing")
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
    top3 = create_all_charts(all_results, price_data)

    # ذخیره CSV
    rows = []
    for r in sorted(all_results.keys()):
        res = all_results[r]
        costs = res['total_gas_costs'] + res['total_slippage_costs']
        rows.append({
            'Range': f'±{r}%',
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
    results_df.to_csv('pancakeswap_results_v2.csv',
                      index=False, encoding='utf-8-sig')
    print(f"\n💾 CSV saved: pancakeswap_results_v2.csv")

    # نتیجه‌گیری
    best = sorted_results[0]

    print("\n" + "═" * 65)
    print("🎯 CONCLUSION")
    print("═" * 65)
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║  🥞 PancakeSwap V3 - CAKE/BNB Pool (with Rebalancing)       ║
    ║  🔗 Network: BNB Smart Chain (BSC)                           ║
    ║                                                               ║
    ║  🏆 OPTIMAL RANGE: ±{best[0]}%                                     
    ║                                                               ║
    ║  📊 Performance:                                              ║
    ║     • Total Return:    {best[1]['total_return']:+.2f}%                       
    ║     • Net Fees Earned: ${best[1]['total_fees_net']:,.0f}                    
    ║     • Fee APR:         {best[1]['fee_apr']:.1f}%                           
    ║     • Time Active:     {best[1]['active_percent']:.1f}%                          
    ║     • Rebalances:      {best[1]['rebalance_count']}                              
    ║     • IL:              {best[1]['impermanent_loss']:.2f}%                       
    ║     • vs HODL:         {best[1]['vs_hodl']:+.2f}%                         
    ║                                                               ║
    ║  📐 Formulas Used:                                            ║
    ║     HODL = Σ(initial_amounts × current_prices)               ║
    ║     IL% = (pool_value/hodl_value - 1) × 100                  ║
    ║     Net Fees = Gross Fees - Gas - Slippage                   ║
    ║     Total Value = Pool Value + Net Fees                      ║
    ║     Return = (Total Value - Initial) / Initial × 100         ║
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

    📁 Output Files:
       • pancakeswap_optimization_v2.png   (Overall optimization)
       • pancakeswap_top3_v2.png           (Top 3 comparison)
       • pancakeswap_rebalancing_v2.png    (Rebalancing analysis)
       • pancakeswap_rebalance_visual_v2.png (Visual rebalancing)
       • pancakeswap_results_v2.csv        (Full data)
    """)

    print("✅ Analysis Complete!")
    print("═" * 65)

    return all_results, price_data


if __name__ == "__main__":
    results, data = main()