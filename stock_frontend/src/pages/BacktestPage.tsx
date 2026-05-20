import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import { Link } from 'react-router-dom';

interface Preset {
  key: string; name: string; description: string; params: ParamDef[];
}
interface ParamDef {
  key: string; label: string; type: string; default: number; min: number; max: number;
}

function formatMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿';
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万';
  return v.toFixed(2);
}

export default function BacktestPage() {
  const [code, setCode] = useState('000001');
  const [selectedStrategy, setSelectedStrategy] = useState('ma_cross');
  const [params, setParams] = useState<Record<string, number>>({ fast_period: 5, slow_period: 20 });
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [capital, setCapital] = useState('100000');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: presets = [] } = useQuery({
    queryKey: ['backtest-presets'],
    queryFn: () => stockAPI.getBacktestPresets(),
  });

  const handleStrategyChange = (key: string) => {
    setSelectedStrategy(key);
    const preset = presets.find((p: Preset) => p.key === key);
    if (preset) {
      const p: Record<string, number> = {};
      preset.params.forEach((def: ParamDef) => { p[def.key] = def.default; });
      setParams(p);
    }
    setResult(null);
    setError(null);
  };

  const handleParamChange = (key: string, val: string) => {
    const num = parseFloat(val);
    if (!isNaN(num)) setParams(prev => ({ ...prev, [key]: num }));
  };

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const payload: any = { code, strategy: selectedStrategy, params };
      if (startDate) payload.start_date = startDate;
      if (endDate) payload.end_date = endDate;
      if (capital) payload.initial_capital = parseFloat(capital);
      const res = await stockAPI.runBacktest(payload);
      if (res.success === false) {
        setError(res.error || '回测失败');
      } else {
        setResult(res);
      }
    } catch (e: any) {
      setError(e.message || '回测请求失败');
    } finally {
      setRunning(false);
    }
  };

  const preset = presets.find((p: Preset) => p.key === selectedStrategy);

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <Link to="/strategies" className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
          <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">策略回测</h1>
      </div>

      {/* 参数表单 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">股票代码</label>
            <input value={code} onChange={e => setCode(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm font-mono"
              placeholder="000001" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">开始日期</label>
            <input type="date" value={startDate} onChange={e => setStartDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">结束日期</label>
            <input type="date" value={endDate} onChange={e => setEndDate(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm" />
          </div>
          <div>
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-1">初始资金(元)</label>
            <input type="number" value={capital} onChange={e => setCapital(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm" />
          </div>
        </div>

        {/* 策略选择 */}
        <div className="mb-4">
          <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">策略</label>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {presets.map((p: Preset) => (
              <button key={p.key} onClick={() => handleStrategyChange(p.key)}
                className={`text-left px-3 py-2 rounded-lg border text-sm transition-all ${
                  selectedStrategy === p.key
                    ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300'
                    : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:border-blue-300'
                }`}>
                <div className="font-semibold">{p.name}</div>
                <div className="text-xs opacity-70 mt-0.5">{p.description}</div>
              </button>
            ))}
          </div>
        </div>

        {/* 策略参数 */}
        {preset && (
          <div className="mb-4">
            <label className="block text-xs font-medium text-gray-600 dark:text-gray-400 mb-2">策略参数</label>
            <div className="flex flex-wrap gap-4">
              {preset.params.map((def: ParamDef) => (
                <div key={def.key}>
                  <label className="block text-xs text-gray-500 mb-0.5">{def.label} ({def.min}-{def.max})</label>
                  <input type="number" value={params[def.key] ?? def.default}
                    onChange={e => handleParamChange(def.key, e.target.value)}
                    min={def.min} max={def.max} step={def.type === 'float' ? 0.1 : 1}
                    className="w-24 px-2 py-1 border border-gray-300 dark:border-gray-600 rounded bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm" />
                </div>
              ))}
            </div>
          </div>
        )}

        <button onClick={handleRun} disabled={running}
          className="px-6 py-2.5 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 transition-all shadow">
          {running ? '⏳ 回测运行中...' : '🚀 开始回测'}
        </button>
        {error && <p className="mt-2 text-sm text-red-600">{error}</p>}
      </div>

      {/* 回测结果 */}
      {result && (
        <>
          {/* 核心指标 */}
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
            {[
              { label: '总收益率', value: `${result.metrics.total_return}%`, color: result.metrics.total_return >= 0 ? 'text-red-600' : 'text-green-600' },
              { label: '年化收益', value: `${result.metrics.annual_return}%`, color: result.metrics.annual_return >= 0 ? 'text-red-600' : 'text-green-600' },
              { label: '最大回撤', value: `${result.metrics.max_drawdown}%`, color: 'text-green-600' },
              { label: '夏普比率', value: result.metrics.sharpe_ratio, color: result.metrics.sharpe_ratio >= 1 ? 'text-red-600' : 'text-gray-900 dark:text-white' },
              { label: '胜率', value: `${result.metrics.win_rate}%`, color: result.metrics.win_rate >= 50 ? 'text-red-600' : 'text-gray-900 dark:text-white' },
              { label: '交易次数', value: result.metrics.total_trades },
              { label: '买入持有', value: `${result.metrics.buy_hold_return}%`, color: result.metrics.buy_hold_return >= 0 ? 'text-red-600' : 'text-green-600' },
            ].map((item, i) => (
              <div key={i} className="bg-white dark:bg-gray-800 rounded-xl p-3 shadow-sm border border-gray-200 dark:border-gray-700">
                <p className="text-xs text-gray-500 dark:text-gray-400">{item.label}</p>
                <p className={`text-lg font-bold ${item.color || 'text-gray-900 dark:text-white'}`}>{item.value}</p>
              </div>
            ))}
          </div>

          {/* 超额收益提示 */}
          <div className="bg-blue-50 dark:bg-blue-900/10 border border-blue-200 dark:border-blue-800/30 rounded-lg p-4 text-sm">
            <span className="font-semibold text-gray-900 dark:text-white">📊 策略 vs 买入持有：</span>
            <span className={result.metrics.excess_return >= 0 ? 'text-red-600' : 'text-green-600'}>
              {result.metrics.excess_return >= 0 ? '+' : ''}{result.metrics.excess_return}%
            </span>
            <span className="text-gray-500 ml-1">
              · 回测区间 {result.period.start} ~ {result.period.end}（{result.period.trading_days}个交易日）
              · 初始资金 {formatMoney(result.initial_capital)} → 最终 {formatMoney(result.final_value)}
            </span>
          </div>

          {/* 交易记录 */}
          {result.trades.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-hidden">
              <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
                <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
                  📝 交易记录 ({result.trades.length}笔)
                </h3>
              </div>
              <div className="overflow-x-auto max-h-[400px] overflow-y-auto">
                <table className="w-full text-sm">
                  <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400 sticky top-0">
                    <tr>
                      <th className="text-left px-3 py-2">日期</th>
                      <th className="text-left px-3 py-2">方向</th>
                      <th className="text-right px-3 py-2">价格</th>
                      <th className="text-right px-3 py-2">数量</th>
                      <th className="text-right px-3 py-2">金额</th>
                      <th className="text-right px-3 py-2">手续费</th>
                      <th className="text-right px-3 py-2">剩余现金</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                    {result.trades.map((t: any, i: number) => (
                      <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                        <td className="px-3 py-2 text-gray-500 text-xs">{t.date}</td>
                        <td className={`px-3 py-2 font-medium ${t.type === 'buy' ? 'text-red-600' : 'text-green-600'}`}>
                          {t.type === 'buy' ? '买入' : '卖出'}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-900 dark:text-white">{t.price.toFixed(2)}</td>
                        <td className="px-3 py-2 text-right text-gray-900 dark:text-white">
                          {t.type === 'buy' ? t.shares : t.shares}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-900 dark:text-white">
                          {t.type === 'buy' ? t.cost?.toFixed(2) : t.proceeds?.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-500 text-xs">
                          {t.commission?.toFixed(2)}
                        </td>
                        <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">
                          {formatMoney(t.cash_after)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}

          {/* 净值曲线 */}
          {result.equity_curve?.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-5">
              <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">📈 净值曲线</h3>
              <div className="overflow-x-auto">
                <svg viewBox="0 0 800 240" className="w-full h-60" preserveAspectRatio="xMidYMid meet">
                  {/* 背景网格 */}
                  <defs>
                    <linearGradient id="grid-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="currentColor" stopOpacity="0.06" />
                      <stop offset="100%" stopColor="currentColor" stopOpacity="0.02" />
                    </linearGradient>
                  </defs>
                  {(() => {
                    const curve = result.equity_curve;
                    const values = curve.map((e: any) => e.total_value);
                    const minV = Math.min(...values);
                    const maxV = Math.max(...values);
                    const range = maxV - minV || 1;
                    const w = 800, h = 200;
                    const pad = 20;
                    const plotW = w - pad * 2;
                    const plotH = h - pad * 2;
                    const steps = curve.length;

                    // 网格线
                    const gridLines = [];
                    for (let i = 0; i <= 4; i++) {
                      const y = pad + plotH - (plotH * i / 4);
                      const val = minV + range * i / 4;
                      gridLines.push(<line key={`g${i}`} x1={pad} y1={y} x2={w - pad} y2={y} stroke="#e5e7eb" strokeWidth="0.5" />);
                      gridLines.push(<text key={`gt${i}`} x={pad - 4} y={y + 3} textAnchor="end" className="text-[10px] fill-gray-400">{formatMoney(val)}</text>);
                    }

                    // 净值线
                    const points = curve.map((e: any, i: number) => {
                      const x = pad + (steps > 1 ? (i / (steps - 1)) * plotW : plotW / 2);
                      const y = pad + plotH - ((e.total_value - minV) / range) * plotH;
                      return `${x},${y}`;
                    });

                    return (
                      <>
                        {gridLines}
                        <polyline fill="none" stroke="#3b82f6" strokeWidth="2" points={points.join(' ')} />
                        {/* 起始结束点 */}
                        <circle cx={parseFloat(points[0].split(',')[0])} cy={parseFloat(points[0].split(',')[1])} r="3" fill="#3b82f6" />
                        <circle cx={parseFloat(points[points.length - 1].split(',')[0])} cy={parseFloat(points[points.length - 1].split(',')[1])} r="3" fill="#ef4444" />
                      </>
                    );
                  })()}
                </svg>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
