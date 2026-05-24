import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { stockAPI } from '../services/api';

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

// ─── 子组件 ──────────────────────────────────

/** 信号灯组件 */
function SignalLight({ label, status, color }: { label: string; status: string; color: string }) {
  return (
    <div className="flex items-center gap-2 text-sm">
      <span className={`w-3 h-3 rounded-full ${color}`} />
      <span className="text-gray-500 dark:text-gray-400">{label}:</span>
      <span className="font-medium text-gray-900 dark:text-white">{status}</span>
    </div>
  );
}

/** 持仓状态标签 */
function PosBadge({ shares, cost }: { shares?: number | null; cost?: number | null }) {
  if (!shares || !cost) return null;
  return (
    <span className="ml-2 px-1.5 py-0.5 text-xs rounded bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300">
      持仓 {shares}股 @ ¥{cost.toFixed(2)}
    </span>
  );
}

// ─── 主页面 ──────────────────────────────────

export default function Midline() {
  const queryClient = useQueryClient();

  // ═══ 自选池健康度 ═══
  const { data: healthData, isLoading: healthLoading } = useQuery({
    queryKey: ['midline-health'],
    queryFn: () => fetch(`${API}/api/midline/watchlist-health`).then(r => r.json()),
    refetchInterval: 60000,
  });

  // ═══ 仓位计算器 ═══
  const [calcInput, setCalcInput] = useState({
    total_capital: 100000,
    risk_pct: 2,
    entry_price: 0,
    stop_loss_price: 0,
    target_price: 0,
  });
  const [calcResult, setCalcResult] = useState<any>(null);

  const handleCalc = async () => {
    const res = await fetch(`${API}/api/midline/position-calc`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(calcInput),
    });
    const data = await res.json();
    setCalcResult(data);
  };

  // ═══ 交易日志 ═══
  const { data: journalData, isLoading: journalLoading } = useQuery({
    queryKey: ['midline-journal'],
    queryFn: () => fetch(`${API}/api/midline/journal`).then(r => r.json()),
  });

  const { data: statsData } = useQuery({
    queryKey: ['midline-journal-stats'],
    queryFn: () => fetch(`${API}/api/midline/journal/stats`).then(r => r.json()),
  });

  const handleDelete = async (id: number) => {
    if (!confirm('删除这笔记录？')) return;
    await fetch(`${API}/api/midline/journal/${id}`, { method: 'DELETE' });
    queryClient.invalidateQueries({ queryKey: ['midline-journal'] });
  };

  const journals = journalData?.data || [];
  const stats = statsData?.data || {};

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-gray-900 dark:text-white">📊 中长线交易看板</h1>

      {/* ═══════════ 自选池健康度 ═══════════ */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">📋 自选池趋势健康度</h2>
          <p className="text-xs text-gray-500 mt-1">基于均线排列+MACD+RSI 综合评分，满分100</p>
        </div>
        {healthLoading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-4 py-2 text-left">代码</th>
                  <th className="px-4 py-2 text-left">名称</th>
                  <th className="px-4 py-2 text-right">评分</th>
                  <th className="px-4 py-2 text-center">均线</th>
                  <th className="px-4 py-2 text-center">MACD</th>
                  <th className="px-4 py-2 text-center">RSI</th>
                  <th className="px-4 py-2 text-left">趋势</th>
                  <th className="px-4 py-2 text-left">建议</th>
                </tr>
              </thead>
              <tbody>
                {(healthData?.data || []).map((s: any) => (
                  <tr key={s.code} className="border-t border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-750">
                    <td className="px-4 py-3 font-mono text-blue-600 dark:text-blue-400">
                      <a href={`/stock/${s.code}`}>{s.code}</a>
                    </td>
                    <td className="px-4 py-3 text-gray-900 dark:text-white">
                      {s.name}
                      <PosBadge shares={s.shares} cost={s.cost_price} />
                    </td>
                    <td className="px-4 py-3 text-right">
                      <span className={`font-bold text-lg ${
                        s.score >= 70 ? 'text-green-500' : s.score >= 40 ? 'text-yellow-500' : 'text-red-500'
                      }`}>
                        {s.score}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-center text-xs">{s.ma_score}分</td>
                    <td className="px-4 py-3 text-center text-xs">{s.macd_signal}</td>
                    <td className="px-4 py-3 text-center text-xs">{s.rsi_score}分</td>
                    <td className="px-4 py-3 text-xs">{s.trend}</td>
                    <td className="px-4 py-3 text-xs">{s.suggestion}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ═══════════ 仓位计算器 + 统计 ═══════════ */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* 仓位计算器 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">🧮 仓位计算器</h2>
          <div className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500 mb-1">总资金</label>
                <input type="number" className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white text-sm"
                  value={calcInput.total_capital}
                  onChange={e => setCalcInput({...calcInput, total_capital: +e.target.value})} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">每笔风险(%)</label>
                <input type="number" className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white text-sm"
                  value={calcInput.risk_pct}
                  onChange={e => setCalcInput({...calcInput, risk_pct: +e.target.value})} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">入场价</label>
                <input type="number" step="0.01" className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white text-sm"
                  value={calcInput.entry_price || ''}
                  onChange={e => setCalcInput({...calcInput, entry_price: +e.target.value})} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">止损价</label>
                <input type="number" step="0.01" className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white text-sm"
                  value={calcInput.stop_loss_price || ''}
                  onChange={e => setCalcInput({...calcInput, stop_loss_price: +e.target.value})} />
              </div>
              <div>
                <label className="block text-xs text-gray-500 mb-1">目标价(可选)</label>
                <input type="number" step="0.01" className="w-full px-3 py-2 border rounded dark:bg-gray-700 dark:border-gray-600 dark:text-white text-sm"
                  value={calcInput.target_price || ''}
                  onChange={e => setCalcInput({...calcInput, target_price: +e.target.value})} />
              </div>
            </div>
            <button onClick={handleCalc}
              className="w-full py-2 bg-blue-600 text-white rounded hover:bg-blue-700 text-sm font-medium">
              计算仓位
            </button>
            {calcResult && !calcResult.error && (
              <div className="mt-4 p-4 bg-blue-50 dark:bg-blue-900/30 rounded space-y-2 text-sm">
                <div className="flex justify-between"><span className="text-gray-500">建议买入</span>
                  <span className="font-bold text-lg text-blue-600">{calcResult.suggested_shares} 股</span></div>
                <div className="flex justify-between"><span className="text-gray-500">占用资金</span>
                  <span>¥{calcResult.position_value?.toLocaleString()} ({calcResult.position_pct}%)</span></div>
                <div className="flex justify-between"><span className="text-gray-500">最大亏损</span>
                  <span className="text-red-500">¥{calcResult.max_loss_amount?.toLocaleString()}</span></div>
                {calcResult.risk_reward_ratio && (
                  <div className="flex justify-between"><span className="text-gray-500">盈亏比</span>
                    <span className={calcResult.risk_reward_ratio >= 2 ? 'text-green-600 font-bold' : 'text-yellow-600'}>
                      1:{calcResult.risk_reward_ratio}
                    </span></div>
                )}
                <div className="flex justify-between text-xs text-gray-400"><span>每股价差</span>
                  <span>¥{calcResult.risk_per_share}</span></div>
              </div>
            )}
          </div>
        </div>

        {/* 交易统计 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">📈 交易统计</h2>
          {stats.total_trades > 0 ? (
            <div className="grid grid-cols-2 gap-4 text-sm">
              <Stat label="总交易" value={stats.total_trades} />
              <Stat label="胜率" value={`${stats.win_rate}%`} color={stats.win_rate >= 50 ? 'text-green-500' : 'text-red-500'} />
              <Stat label="盈利次数" value={stats.wins} />
              <Stat label="亏损次数" value={stats.losses} />
              <Stat label="累计盈亏" value={`¥${(stats.total_pnl || 0).toLocaleString()}`}
                color={(stats.total_pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'} />
              <Stat label="盈亏比" value={`1:${stats.profit_factor}`}
                color={(stats.profit_factor || 0) >= 1.5 ? 'text-green-500' : 'text-yellow-500'} />
              <Stat label="最大连胜" value={stats.max_win_streak} />
              <Stat label="最大连败" value={stats.max_loss_streak} color="text-red-500" />
              <Stat label="均盈" value={`¥${(stats.avg_win || 0).toLocaleString()}`} color="text-green-500" />
              <Stat label="均亏" value={`¥${(stats.avg_loss || 0).toLocaleString()}`} color="text-red-500" />
            </div>
          ) : (
            <div className="text-center py-8 text-gray-400">暂无交易记录，开始记录你的第一笔交易吧</div>
          )}
        </div>
      </div>

      {/* ═══════════ 交易日志 ═══════════ */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-4 border-b border-gray-200 dark:border-gray-700 flex justify-between items-center">
          <h2 className="text-lg font-semibold text-gray-900 dark:text-white">📝 交易日志</h2>
          <button
            onClick={() => {
              const code = prompt('股票代码');
              const name = prompt('股票名称');
              const entryDate = prompt('入场日期 (YYYY-MM-DD)');
              const entryPrice = prompt('入场价格');
              const shares = prompt('股数');
              const stopLoss = prompt('止损价');
              const reason = prompt('入场理由');
              if (!code || !entryPrice) return;
              fetch(`${API}/api/midline/journal`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  code, name, entry_date: entryDate,
                  entry_price: parseFloat(entryPrice),
                  shares: parseInt(shares || '100'),
                  stop_loss: parseFloat(stopLoss || '0'),
                  reason_entry: reason,
                }),
              }).then(() => queryClient.invalidateQueries({ queryKey: ['midline-journal'] }));
            }}
            className="px-3 py-1.5 bg-green-600 text-white text-sm rounded hover:bg-green-700"
          >
            + 记录交易
          </button>
        </div>
        {journalLoading ? (
          <div className="p-8 text-center text-gray-500">加载中...</div>
        ) : journals.length === 0 ? (
          <div className="p-8 text-center text-gray-400">暂无记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-700">
                <tr>
                  <th className="px-3 py-2 text-left">代码</th>
                  <th className="px-3 py-2 text-left">入场日</th>
                  <th className="px-3 py-2 text-right">入场价</th>
                  <th className="px-3 py-2 text-right">股数</th>
                  <th className="px-3 py-2 text-right">止损</th>
                  <th className="px-3 py-2 text-left">出场日</th>
                  <th className="px-3 py-2 text-right">盈亏</th>
                  <th className="px-3 py-2 text-left">理由</th>
                  <th className="px-3 py-2"></th>
                </tr>
              </thead>
              <tbody>
                {journals.map((j: any) => (
                  <tr key={j.id} className="border-t border-gray-100 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-750">
                    <td className="px-3 py-2 font-mono text-blue-600 dark:text-blue-400">{j.code} {j.name}</td>
                    <td className="px-3 py-2">{j.entry_date}</td>
                    <td className="px-3 py-2 text-right">¥{j.entry_price}</td>
                    <td className="px-3 py-2 text-right">{j.shares}</td>
                    <td className="px-3 py-2 text-right text-red-500">¥{j.stop_loss}</td>
                    <td className="px-3 py-2">{j.exit_date || '—'}</td>
                    <td className={`px-3 py-2 text-right font-medium ${
                      (j.pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    }`}>
                      {j.pnl != null ? `¥${j.pnl} (${j.pnl_pct}%)` : '—'}
                    </td>
                    <td className="px-3 py-2 text-xs text-gray-500 max-w-[200px] truncate">{j.reason_entry}</td>
                    <td className="px-3 py-2">
                      <button onClick={() => handleDelete(j.id)}
                        className="text-xs text-red-400 hover:text-red-600">✕</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}

function Stat({ label, value, color }: { label: string; value: any; color?: string }) {
  return (
    <div className="p-3 bg-gray-50 dark:bg-gray-700 rounded">
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={`text-lg font-bold ${color || 'text-gray-900 dark:text-white'}`}>{value}</div>
    </div>
  );
}
