"""
پروژه بهینه‌سازی استخر نقدینگی V3 - PancakeSwap BSC
جفت‌ارز: CAKE/BNB
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
    از ترکیب CAKE/USDT و BNB/USDT محاسبه می‌شود
    """
    print("📥 دریافت داده‌های CAKE/BNB برای PancakeSwap...")
    print("   (محاسبه از CAKE/USDT ÷ BNB/USDT)")

    url = 'https://api.binance.com/api/v3/klines'
    all_cake = []
    all_bnb = []

    # دریافت داده‌های یکساله
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

    # تبدیل به DataFrame
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

    # تبدیل انواع
    for df in [df_cake, df_bnb]:
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df['close'] = df['close'].astype(float)
        df['high'] = df['high'].astype(float)
        df['low'] = df['low'].astype(float)
        df['volume'] = df['volume'].astype(float)
        df['quote_volume'] = df['quote_volume'].astype(float)

    # ادغام بر اساس timestamp
    df_cake = df_cake.drop_duplicates(subset='timestamp').set_index('timestamp')
    df_bnb = df_bnb.drop_duplicates(subset='timestamp').set_index('timestamp')

    # محاسبه CAKE/BNB
    df = pd.DataFrame()
    df['cake_usdt'] = df_cake['close']
    df['bnb_usdt'] = df_bnb['close']
    df['cake_volume'] = df_cake['quote_volume']
    df['bnb_volume'] = df_bnb['quote_volume']

    # حذف ردیف‌های خالی
    df = df.dropna()

    # محاسبه قیمت CAKE/BNB
    df['close'] = df['cake_usdt'] / df['bnb_usdt']
    df['quote_volume'] = (df['cake_volume'] + df['bnb_volume']) / 2  # میانگین حجم

    df = df.reset_index()

    days = len(df) / 24
    print(f"\n✅ داده‌های CAKE/BNB آماده شد")
    print(f"   📊 تعداد کندل: {len(df)} ({days:.0f} روز)")
    print(f"   📅 از: {df['timestamp'].iloc[0]}")
    print(f"   📅 تا: {df['timestamp'].iloc[-1]}")
    print(f"   💰 قیمت اولیه: {df['close'].iloc[0]:.6f} BNB")
    print(f"   💰 قیمت نهایی: {df['close'].iloc[-1]:.6f} BNB")
    print(f"   💰 CAKE اولیه: ${df['cake_usdt'].iloc[0]:.2f}")
    print(f"   💰 BNB اولیه: ${df['bnb_usdt'].iloc[0]:.2f}")

    return df


# ═══════════════════════════════════════════════════════════
# بخش ۲: کلاس استخر
# ═══════════════════════════════════════════════════════════

class LiquidityPoolV3:
    def __init__(self, initial_capital=10000, fee_tier=0.25):
        self.initial_capital = initial_capital
        self.fee_rate = fee_tier / 100

    def set_position(self, current_price, range_percent):
        self.entry_price = current_price
        self.range_percent = range_percent
        self.price_lower = current_price * (1 - range_percent / 100)
        self.price_upper = current_price * (1 + range_percent / 100)

        sqrt_p = np.sqrt(current_price)
        sqrt_pa = np.sqrt(self.price_lower)
        sqrt_pb = np.sqrt(self.price_upper)

        capital_per_side = self.initial_capital / 2
        amount0 = capital_per_side / current_price

        # محافظت از تقسیم بر صفر
        if sqrt_pb - sqrt_p > 0:
            L0 = amount0 * (sqrt_p * sqrt_pb) / (sqrt_pb - sqrt_p)
        else:
            L0 = 0

        amount1 = capital_per_side
        if sqrt_p - sqrt_pa > 0:
            L1 = amount1 / (sqrt_p - sqrt_pa)
        else:
            L1 = 0

        self.L = min(L0, L1) if L0 > 0 and L1 > 0 else max(L0, L1)
        self.initial_token0 = amount0
        self.initial_token1 = capital_per_side

    def is_in_range(self, price):
        return self.price_lower <= price <= self.price_upper

    def get_amounts(self, current_price):
        sqrt_p = np.sqrt(current_price)
        sqrt_pa = np.sqrt(self.price_lower)
        sqrt_pb = np.sqrt(self.price_upper)

        if current_price <= self.price_lower:
            amount0 = self.L * (sqrt_pb - sqrt_pa) / (sqrt_pa * sqrt_pb) if sqrt_pa * sqrt_pb > 0 else 0
            amount1 = 0
        elif current_price >= self.price_upper:
            amount0 = 0
            amount1 = self.L * (sqrt_pb - sqrt_pa)
        else:
            amount0 = self.L * (sqrt_pb - sqrt_p) / (sqrt_p * sqrt_pb) if sqrt_p * sqrt_pb > 0 else 0
            amount1 = self.L * (sqrt_p - sqrt_pa)

        return amount0, amount1

    def calculate_position_value(self, current_price):
        amount0, amount1 = self.get_amounts(current_price)
        return amount0 * current_price + amount1

    def calculate_hodl_value(self, current_price):
        return self.initial_token0 * current_price + self.initial_token1

    def calculate_impermanent_loss(self, current_price):
        pool_value = self.calculate_position_value(current_price)
        hodl_value = self.calculate_hodl_value(current_price)
        if hodl_value == 0:
            return 0, pool_value, hodl_value
        il = (pool_value / hodl_value - 1) * 100
        return il, pool_value, hodl_value


# ═══════════════════════════════════════════════════════════
# بخش ۳: بک‌تست
# ═══════════════════════════════════════════════════════════

def run_backtest(price_data, range_percent, initial_capital=10000, fee_tier=0.25):
    pool = LiquidityPoolV3(initial_capital, fee_tier)
    entry_price = price_data['close'].iloc[0]
    pool.set_position(entry_price, range_percent)

    results = {
        'range_percent': range_percent,
        'price_lower': pool.price_lower,
        'price_upper': pool.price_upper,
        'entry_price': entry_price,
        'total_fees': 0,
        'periods_in_range': 0,
        'periods_out_of_range': 0,
        'exit_count': 0,
        'fee_history': [],
        'value_history': []
    }

    was_in_range = True
    avg_daily_volume = price_data['quote_volume'].mean() * 24
    estimated_tvl = avg_daily_volume * 5
    our_share = min(initial_capital / estimated_tvl, 0.1)
    concentration_factor = 100 / range_percent

    for idx in range(len(price_data)):
        row = price_data.iloc[idx]
        price = row['close']
        volume = row['quote_volume']

        in_range = pool.is_in_range(price)

        if in_range:
            results['periods_in_range'] += 1
            fee = volume * pool.fee_rate * our_share * concentration_factor
            fee = min(fee, volume * pool.fee_rate * 0.5)
            results['total_fees'] += fee
            results['fee_history'].append(fee)
        else:
            results['periods_out_of_range'] += 1
            results['fee_history'].append(0)
            if was_in_range:
                results['exit_count'] += 1

        results['value_history'].append(pool.calculate_position_value(price))
        was_in_range = in_range

    final_price = price_data['close'].iloc[-1]
    results['final_price'] = final_price
    results['active_percent'] = (results['periods_in_range'] / len(price_data)) * 100

    il, pool_value, hodl_value = pool.calculate_impermanent_loss(final_price)
    results['impermanent_loss'] = il
    results['final_pool_value'] = pool_value
    results['hodl_value'] = hodl_value
    results['final_value'] = pool_value + results['total_fees']
    results['total_return'] = ((results['final_value'] - initial_capital) / initial_capital) * 100

    days = len(price_data) / 24
    results['fee_apr'] = (results['total_fees'] / initial_capital) * (365 / days) * 100
    results['vs_hodl'] = ((results['final_value'] - hodl_value) / hodl_value) * 100 if hodl_value > 0 else 0

    return results


def run_all_scenarios(price_data, scenarios, initial_capital=10000):
    print("\n" + "═" * 70)
    print("🚀 شروع بک‌تست - PancakeSwap V3 - CAKE/BNB")
    print("═" * 70)

    all_results = {}
    for range_pct in scenarios:
        result = run_backtest(price_data, range_pct, initial_capital)
        all_results[range_pct] = result
        status = "✅" if result['total_return'] > 0 else "❌"
        print(f"   ±{range_pct:2d}% │ فعال: {result['active_percent']:5.1f}% │ "
              f"کارمزد: ${result['total_fees']:8.0f} │ بازده: {result['total_return']:+7.2f}% {status}")

    return all_results


# ═══════════════════════════════════════════════════════════
# بخش ۴: نمودارها
# ═══════════════════════════════════════════════════════════

def create_all_charts(all_results, price_data):
    """ساخت همه نمودارها"""

    ranges = sorted(all_results.keys())
    sorted_results = sorted(all_results.items(), key=lambda x: x[1]['total_return'], reverse=True)
    top3 = [r[0] for r in sorted_results[:3]]

    # ═══════════════════════════════════════════════════════════
    # نمودار ۱: بهینه‌سازی کلی
    # ═══════════════════════════════════════════════════════════
    print("\n📊 ساخت نمودار ۱...")

    fig1, axes1 = plt.subplots(2, 3, figsize=(18, 12))
    fig1.suptitle('PancakeSwap V3 - CAKE/BNB Pool Optimization (1 Year)', fontsize=16, fontweight='bold')

    # قیمت
    ax = axes1[0, 0]
    ax.plot(price_data['timestamp'], price_data['close'], color='#F0B90B', linewidth=0.8)
    ax.set_title('CAKE/BNB Price', fontsize=12, fontweight='bold')
    ax.set_ylabel('Price (BNB)')
    ax.grid(True, alpha=0.3)

    # بازده
    ax = axes1[0, 1]
    returns = [all_results[r]['total_return'] for r in ranges]
    colors = ['#27ae60' if r > 0 else '#e74c3c' for r in returns]
    bars = ax.bar([f'±{r}%' for r in ranges], returns, color=colors)
    ax.axhline(y=0, color='black', linewidth=1)
    ax.set_title('Total Return vs Range', fontsize=12, fontweight='bold')
    ax.set_ylabel('Return (%)')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    ax.grid(True, alpha=0.3, axis='y')
    best_idx = returns.index(max(returns))
    bars[best_idx].set_edgecolor('gold')
    bars[best_idx].set_linewidth(3)

    # درصد فعال
    ax = axes1[0, 2]
    active = [all_results[r]['active_percent'] for r in ranges]
    ax.plot(ranges, active, 'o-', color='#3498db', linewidth=2, markersize=8)
    ax.fill_between(ranges, active, alpha=0.3, color='#3498db')
    ax.set_title('Time In Range (%)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Range (%)')
    ax.set_ylabel('Active %')
    ax.grid(True, alpha=0.3)

    # کارمزد
    ax = axes1[1, 0]
    fees = [all_results[r]['total_fees'] for r in ranges]
    ax.bar([f'±{r}%' for r in ranges], fees, color='#F0B90B')
    ax.set_title('Total Fees Earned', fontsize=12, fontweight='bold')
    ax.set_ylabel('Fees ($)')
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45)
    ax.grid(True, alpha=0.3, axis='y')

    # APR
    ax = axes1[1, 1]
    aprs = [all_results[r]['fee_apr'] for r in ranges]
    ax.plot(ranges, aprs, 's-', color='#9b59b6', linewidth=2, markersize=8)
    ax.set_title('Fee APR', fontsize=12, fontweight='bold')
    ax.set_xlabel('Range (%)')
    ax.set_ylabel('APR %')
    ax.grid(True, alpha=0.3)

    # Trade-off
    ax = axes1[1, 2]
    scatter = ax.scatter(active, returns, c=ranges, cmap='RdYlGn', s=200, edgecolors='black')
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (active[i], returns[i]), textcoords="offset points",
                    xytext=(0, 10), ha='center', fontsize=9)
    ax.set_title('Return vs Active Time (Trade-off)', fontsize=12, fontweight='bold')
    ax.set_xlabel('Active %')
    ax.set_ylabel('Return %')
    ax.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    plt.tight_layout()
    plt.savefig('pancakeswap_optimization.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_optimization.png")
    plt.close(fig1)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۲: مقایسه ۳ برتر
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۲...")

    fig2, axes2 = plt.subplots(2, 2, figsize=(14, 10))
    fig2.suptitle('PancakeSwap V3 - Top 3 Ranges Comparison', fontsize=16, fontweight='bold')

    colors_top3 = {top3[0]: '#27ae60', top3[1]: '#3498db', top3[2]: '#f39c12'}

    # قیمت با بازه‌ها
    ax = axes2[0, 0]
    ax.plot(price_data['timestamp'], price_data['close'], color='#2c3e50', linewidth=0.8, label='Price')
    for r in top3:
        result = all_results[r]
        ax.axhline(y=result['price_lower'], color=colors_top3[r], linestyle='--', alpha=0.7)
        ax.axhline(y=result['price_upper'], color=colors_top3[r], linestyle='--', alpha=0.7, label=f'±{r}%')
    ax.set_title('Top 3 Ranges on Price', fontsize=12, fontweight='bold')
    ax.set_ylabel('CAKE/BNB')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # تجمعی کارمزد
    ax = axes2[0, 1]
    for r in top3:
        result = all_results[r]
        cumulative = np.cumsum(result['fee_history'])
        ax.plot(price_data['timestamp'], cumulative, label=f'±{r}%', color=colors_top3[r], linewidth=2)
    ax.set_title('Cumulative Fees', fontsize=12, fontweight='bold')
    ax.set_ylabel('Fees ($)')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # مقایسه ارزش
    ax = axes2[1, 0]
    x = np.arange(3)
    width = 0.25

    pool_vals = [all_results[r]['final_pool_value'] for r in top3]
    with_fees = [all_results[r]['final_value'] for r in top3]
    hodl_vals = [all_results[r]['hodl_value'] for r in top3]

    ax.bar(x - width, pool_vals, width, label='Pool Value', color='#3498db')
    ax.bar(x, with_fees, width, label='Pool + Fees', color='#27ae60')
    ax.bar(x + width, hodl_vals, width, label='HODL', color='#95a5a6')
    ax.axhline(y=10000, color='red', linestyle='--', alpha=0.5, label='Initial')

    ax.set_title('Final Value Comparison', fontsize=12, fontweight='bold')
    ax.set_ylabel('Value ($)')
    ax.set_xticks(x)
    ax.set_xticklabels([f'±{r}%' for r in top3])
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # جدول
    ax = axes2[1, 1]
    ax.axis('off')

    table_data = []
    for r in top3:
        res = all_results[r]
        table_data.append([
            f'±{r}%',
            f"{res['active_percent']:.1f}%",
            f"${res['total_fees']:,.0f}",
            f"{res['fee_apr']:.1f}%",
            f"{res['total_return']:+.2f}%",
            f"{res['vs_hodl']:+.2f}%"
        ])

    table = ax.table(
        cellText=table_data,
        colLabels=['Range', 'Active', 'Fees', 'APR', 'Return', 'vs HODL'],
        loc='center', cellLoc='center'
    )
    table.auto_set_font_size(False)
    table.set_fontsize(11)
    table.scale(1.2, 2)

    for j in range(6):
        table[(0, j)].set_facecolor('#F0B90B')
        table[(0, j)].set_text_props(fontweight='bold')
        table[(1, j)].set_facecolor('#d5f5e3')

    ax.set_title('Top 3 Summary', fontsize=12, fontweight='bold', pad=20)

    plt.tight_layout()
    plt.savefig('pancakeswap_top3.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_top3.png")
    plt.close(fig2)

    # ═══════════════════════════════════════════════════════════
    # نمودار ۳: Trade-off
    # ═══════════════════════════════════════════════════════════
    print("📊 ساخت نمودار ۳...")

    fig3, axes3 = plt.subplots(1, 2, figsize=(14, 6))
    fig3.suptitle('PancakeSwap V3 - Trade-off Analysis', fontsize=14, fontweight='bold')

    exits = [all_results[r]['exit_count'] for r in ranges]

    ax = axes3[0]
    scatter = ax.scatter(exits, fees, c=ranges, cmap='viridis', s=200, edgecolors='black')
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (exits[i], fees[i]), textcoords="offset points", xytext=(5, 5), fontsize=9)
    ax.set_title('Fees vs Exit Count', fontsize=12, fontweight='bold')
    ax.set_xlabel('Number of Exits')
    ax.set_ylabel('Total Fees ($)')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    ax = axes3[1]
    scatter = ax.scatter(active, aprs, c=ranges, cmap='plasma', s=200, edgecolors='black')
    for i, r in enumerate(ranges):
        ax.annotate(f'±{r}%', (active[i], aprs[i]), textcoords="offset points", xytext=(5, 5), fontsize=9)
    ax.set_title('Fee APR vs Active Time', fontsize=12, fontweight='bold')
    ax.set_xlabel('Active %')
    ax.set_ylabel('Fee APR %')
    ax.grid(True, alpha=0.3)
    plt.colorbar(scatter, ax=ax, label='Range %')

    plt.tight_layout()
    plt.savefig('pancakeswap_tradeoff.png', dpi=300, bbox_inches='tight', facecolor='white')
    print("   ✅ ذخیره شد: pancakeswap_tradeoff.png")
    plt.close(fig3)

    print("\n✅ همه نمودارها ساخته شدند!")
    return top3


def print_results(all_results):
    print("\n" + "═" * 115)
    print("📋 جدول کامل نتایج - PancakeSwap V3 - CAKE/BNB")
    print("═" * 115)

    sorted_results = sorted(all_results.items(), key=lambda x: x[1]['total_return'], reverse=True)

    print(
        f"{'':^4} {'بازه':^6} │ {'P_min':^12} │ {'P_max':^12} │ {'فعال%':^8} │ {'خروج':^6} │ {'کارمزد':^12} │ {'APR':^8} │ {'بازده':^10} │ {'vs HODL':^10}")
    print("─" * 115)

    for i, (range_pct, r) in enumerate(sorted_results):
        medal = ["🥇", "🥈", "🥉"][i] if i < 3 else "  "
        print(f"{medal} ±{range_pct:2d}%  │ {r['price_lower']:10.6f} │ {r['price_upper']:10.6f} │ "
              f"{r['active_percent']:6.1f}% │ {r['exit_count']:5d} │ ${r['total_fees']:10.0f} │ "
              f"{r['fee_apr']:6.1f}% │ {r['total_return']:+8.2f}% │ {r['vs_hodl']:+8.2f}%")

    print("═" * 115)
    return sorted_results


# ═══════════════════════════════════════════════════════════
# بخش ۵: تابع اصلی
# ═══════════════════════════════════════════════════════════

def main():
    print("╔" + "═" * 65 + "╗")
    print("║  🥞 PancakeSwap V3 - Concentrated Liquidity Optimization     ║")
    print("║  📊 Pair: CAKE/BNB on BSC                                    ║")
    print("╚" + "═" * 65 + "╝")

    # تنظیمات
    INITIAL_CAPITAL = 10000
    FEE_TIER = 0.25  # کارمزد استاندارد PancakeSwap V3
    SCENARIOS = [2, 3, 4, 5, 7, 10, 15, 20, 25, 30, 40, 50]

    print(f"\n⚙️ Settings:")
    print(f"   • DEX: PancakeSwap V3")
    print(f"   • Chain: BNB Smart Chain (BSC)")
    print(f"   • Pair: CAKE/BNB")
    print(f"   • Capital: ${INITIAL_CAPITAL:,}")
    print(f"   • Fee Tier: {FEE_TIER}%")
    print(f"   • Ranges: {SCENARIOS}")

    # دریافت داده
    print("\n" + "─" * 65)
    print("📥 Step 1: Fetching CAKE/BNB Data")
    print("─" * 65)
    price_data = get_pancakeswap_pair_data()

    # آمار
    price_change = ((price_data['close'].iloc[-1] / price_data['close'].iloc[0]) - 1) * 100
    volatility = price_data['close'].pct_change().std() * np.sqrt(24 * 365) * 100

    print(f"\n📊 CAKE/BNB Stats:")
    print(f"   • Price Change: {price_change:+.2f}%")
    print(f"   • Volatility (Annual): {volatility:.1f}%")
    print(f"   • Min: {price_data['close'].min():.6f} BNB")
    print(f"   • Max: {price_data['close'].max():.6f} BNB")

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
    top3 = create_all_charts(all_results, price_data)

    # ذخیره CSV
    results_df = pd.DataFrame([{
        'Range': f'±{r}%',
        'P_min (BNB)': f"{all_results[r]['price_lower']:.6f}",
        'P_max (BNB)': f"{all_results[r]['price_upper']:.6f}",
        'Active %': f"{all_results[r]['active_percent']:.1f}%",
        'Exits': all_results[r]['exit_count'],
        'Fees ($)': f"${all_results[r]['total_fees']:,.0f}",
        'Fee APR': f"{all_results[r]['fee_apr']:.1f}%",
        'IL (%)': f"{all_results[r]['impermanent_loss']:.2f}%",
        'Total Return': f"{all_results[r]['total_return']:+.2f}%",
        'vs HODL': f"{all_results[r]['vs_hodl']:+.2f}%"
    } for r in sorted(all_results.keys())])

    results_df.to_csv('pancakeswap_results.csv', index=False, encoding='utf-8-sig')
    print(f"\n💾 CSV saved: pancakeswap_results.csv")

    # نتیجه‌گیری
    best = sorted_results[0]

    print("\n" + "═" * 65)
    print("🎯 CONCLUSION")
    print("═" * 65)
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║  🥞 PancakeSwap V3 - CAKE/BNB Pool                           ║
    ║  🔗 Network: BNB Smart Chain (BSC)                           ║
    ║                                                               ║
    ║  🏆 OPTIMAL RANGE: ±{best[0]}%                                     
    ║                                                               ║
    ║  📊 Performance:                                              ║
    ║     • Total Return:  {best[1]['total_return']:+.2f}%                           
    ║     • Fees Earned:   ${best[1]['total_fees']:,.0f}                          
    ║     • Fee APR:       {best[1]['fee_apr']:.1f}%                             
    ║     • Time Active:   {best[1]['active_percent']:.1f}%                            
    ║     • vs HODL:       {best[1]['vs_hodl']:+.2f}%                           
    ║                                                               ║
    ╚═══════════════════════════════════════════════════════════════╝

    📁 Output Files:
       • pancakeswap_optimization.png
       • pancakeswap_top3.png  
       • pancakeswap_tradeoff.png
       • pancakeswap_results.csv
    """)

    print("✅ Analysis Complete!")
    print("═" * 65)

    return all_results, price_data


if __name__ == "__main__":
    results, data = main()