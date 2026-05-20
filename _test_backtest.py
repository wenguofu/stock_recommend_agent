#!/usr/bin/env python3
import numpy as np
from backtest_engine import calc_macd, calc_rsi, run_backtest
from data_fetchers import get_daily_kline as fk

code = '300136'
df = fk(code, count=240)
close = df['close'].values

print("=== MACD ===")
dif, dea, _ = calc_macd(close, 12, 26, 9)
buy = 0; sell = 0
for i in range(1, len(close)):
    if not np.isnan(dif[i]) and not np.isnan(dea[i]) and not np.isnan(dif[i-1]) and not np.isnan(dea[i-1]):
        if dif[i-1] <= dea[i-1] and dif[i] > dea[i]: buy += 1
        if dif[i-1] >= dea[i-1] and dif[i] < dea[i]: sell += 1
print('buy=%d, sell=%d' % (buy, sell))
print('DEA range: %.2f - %.2f' % (np.nanmin(dea), np.nanmax(dea)))
fvd = np.where(~np.isnan(dea))[0]
print('First DEA valid:', fvd[0] if len(fvd) > 0 else 'NONE')

print("\n=== RSI ===")
rsi = calc_rsi(close, 14)
valid = rsi[~np.isnan(rsi)]
br = 0; sr = 0
for i in range(1, len(rsi)):
    if not np.isnan(rsi[i]) and not np.isnan(rsi[i-1]):
        if rsi[i-1] <= 30 and rsi[i] > 30: br += 1
        if rsi[i-1] >= 70 and rsi[i] < 70: sr += 1
print('buy=%d, sell=%d, min=%.1f, max=%.1f' % (br, sr, valid.min(), valid.max()))

print("\n=== Full Backtest ===")
res = run_backtest(code, 'macd_cross', {'fast':12,'slow':26,'signal':9}, 100000, '2025-05-01', '2026-05-18')
if res.get('success'):
    m = res['metrics']
    print('MACD trades=%d, return=%.2f%%' % (m['total_trades'], m['total_return']))
else:
    print('MACD error:', res.get('error'))

res2 = run_backtest(code, 'rsi_reversal', {'rsi_period':14,'oversold':30,'overbought':70}, 100000, '2025-05-01', '2026-05-18')
if res2.get('success'):
    m2 = res2['metrics']
    print('RSI trades=%d, return=%.2f%%' % (m2['total_trades'], m2['total_return']))
else:
    print('RSI error:', res2.get('error'))
