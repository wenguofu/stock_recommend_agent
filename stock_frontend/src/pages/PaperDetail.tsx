import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import TradeModal from "../components/TradeModal";
import { createChart, ColorType } from "lightweight-charts";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface Position {
  id: number; code: string; name: string; shares: number;
  avg_cost: number; current_price: number; market_value: number;
  profit_pct: number; today_profit_pct: number;
  etf_replaced: boolean; original_code: string | null;
}

interface Order {
  id: number; code: string; name: string; direction: string;
  price: number; quantity: number; amount: number;
  commission: number; tax: number; order_type: string;
  strategy_run_id: string | null; note: string | null; created_at: string;
}

interface Plan {
  id: number; code: string; name?: string; direction: string;
  target_price: number; quantity?: number; reason: string | null; status: string;
  created_at: string;
}

interface Summary {
  id: number; name: string; initial_capital: number;
  cash_balance: number; total_market_value: number;
  total_profit_pct: number; max_drawdown: number | null;
  win_rate: number | null; snapshot_interval: number;
  position_count: number; snapshot_count: number; order_count: number;
}

interface CurvePoint {
  snapshot_time: string; total_value: number;
  cash_balance: number; market_value: number;
  daily_pnl: number; daily_pnl_pct: number;
}

function formatMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(2);
}

function fmtPct(v: number | null): string {
  if (v == null) return "-";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

export default function PaperDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const chartRef = useRef<HTMLDivElement>(null);
  const [showTrade, setShowTrade] = useState(false);
  const [ordersPage, setOrdersPage] = useState(1);
  const [editingInterval, setEditingInterval] = useState(false);
  const [newInterval, setNewInterval] = useState(60);
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [planModalCode, setPlanModalCode] = useState("");
  const [planDirection, setPlanDirection] = useState("buy");
  const [planTargetPrice, setPlanTargetPrice] = useState("");
  const [planReason, setPlanReason] = useState("");
  const accountId = parseInt(id || "0");

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["paper-summary", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/summary`);
      if (!r.ok) throw new Error("获取摘要失败");
      const d = await r.json();
      return d.summary as Summary;
    },
    enabled: !!accountId,
    refetchInterval: 60000,
  });

  const { data: positions, isLoading: posLoading } = useQuery({
    queryKey: ["paper-positions", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/positions`);
      if (!r.ok) throw new Error("获取持仓失败");
      const d = await r.json();
      return d.positions as Position[];
    },
    enabled: !!accountId,
    refetchInterval: 30000,
  });

  const { data: ordersData } = useQuery({
    queryKey: ["paper-orders", accountId, ordersPage],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/orders?page=${ordersPage}&per_page=20`);
      if (!r.ok) throw new Error("获取订单失败");
      return r.json();
    },
    enabled: !!accountId,
  });

  const { data: curveData } = useQuery({
    queryKey: ["paper-curve", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/equity_curve?limit=200`);
      if (!r.ok) throw new Error("获取曲线失败");
      return r.json();
    },
    enabled: !!accountId,
  });

  const { data: plansData } = useQuery({
    queryKey: ["paper-plans", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/plans/${accountId}`);
      if (!r.ok) throw new Error("获取计划失败");
      const d = await r.json();
      return d.plans as Plan[];
    },
    enabled: !!accountId,
    refetchInterval: 30000,
  });

  const snapshotMut = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/snapshot`, { method: "POST" });
      if (!r.ok) throw new Error("快照失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-curve", accountId] });
      queryClient.invalidateQueries({ queryKey: ["paper-summary", accountId] });
    },
  });

  const intervalMut = useMutation({
    mutationFn: async (interval: number) => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ snapshot_interval: interval }),
      });
      if (!r.ok) throw new Error("更新失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-summary", accountId] });
      setEditingInterval(false);
    },
  });

  const createPlanMut = useMutation({
    mutationFn: async (data: { code: string; direction: string; target_price: number; reason: string }) => {
      const r = await fetch(`${API_BASE}/api/paper/plans/${accountId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!r.ok) throw new Error("创建计划失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-plans", accountId] });
      setPlanModalOpen(false);
      setPlanDirection("buy");
      setPlanTargetPrice("");
      setPlanReason("");
    },
  });

  const cancelPlanMut = useMutation({
    mutationFn: async (planId: number) => {
      const r = await fetch(`${API_BASE}/api/paper/plans/${planId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "cancelled" }),
      });
      if (!r.ok) throw new Error("取消计划失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-plans", accountId] });
    },
  });

  useEffect(() => {
    if (!chartRef.current || !curveData?.curve?.length) return;
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "#9CA3AF" : "#6B7280",
      },
      grid: {
        vertLines: { color: isDark ? "#374151" : "#E5E7EB" },
        horzLines: { color: isDark ? "#374151" : "#E5E7EB" },
      },
      width: chartRef.current.clientWidth,
      height: 280,
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const lineSeries = chart.addLineSeries({
      color: "#3B82F6",
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(2) },
    });
    const data = curveData.curve
      .slice()
      .reverse()
      .map((p: CurvePoint, i: number) => ({
        time: i as import("lightweight-charts").Time,
        value: p.total_value,
      }));
    lineSeries.setData(data);
    chart.timeScale().fitContent();
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    observer.observe(chartRef.current);
    return () => { observer.disconnect(); chart.remove(); };
  }, [curveData]);

  if (summaryLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (!summary) {
    return (
      <div className="text-center py-16">
        <div className="text-6xl mb-4">📭</div>
        <p className="text-gray-500">模拟盘账户不存在</p>
        <button onClick={() => navigate("/paper")} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg">
          返回模拟盘列表
        </button>
      </div>
    );
  }

  const totalValue = summary.cash_balance + summary.total_market_value;

  // Group plans by code
  const plansByCode: Record<string, Plan[]> = {};
  if (plansData) {
    for (const p of plansData) {
      if (!plansByCode[p.code]) plansByCode[p.code] = [];
      plansByCode[p.code].push(p);
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate("/paper")} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <h1 className="text-2xl font-bold text-gray-900 dark:text-white">{summary.name}</h1>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => snapshotMut.mutate()}
            disabled={snapshotMut.isPending}
            className="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600 disabled:opacity-50"
          >
            {snapshotMut.isPending ? "更新中..." : "📸 更新快照"}
          </button>
          <button
            onClick={() => setShowTrade(true)}
            className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
          >
            + 手动交易
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">总资产</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">{formatMoney(totalValue)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">可用现金</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">{formatMoney(summary.cash_balance)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">持仓市值</p>
          <p className="text-xl font-bold text-gray-900 dark:text-white">{formatMoney(summary.total_market_value)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-sm text-gray-500 dark:text-gray-400">总收益率</p>
          <p className={`text-xl font-bold ${summary.total_profit_pct >= 0 ? "text-red-500" : "text-green-500"}`}>
            {fmtPct(summary.total_profit_pct)}
          </p>
        </div>
      </div>

      {/* Secondary Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500">初始资金</p>
          <p className="text-sm font-semibold">{formatMoney(summary.initial_capital)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500">最大回撤</p>
          <p className="text-sm font-semibold">{fmtPct(summary.max_drawdown)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500">胜率</p>
          <p className="text-sm font-semibold">{fmtPct(summary.win_rate)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-3 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500">
            快照间隔
            <button onClick={() => { setNewInterval(summary.snapshot_interval); setEditingInterval(true); }} className="ml-1 text-blue-500 hover:text-blue-600">
              [编辑]
            </button>
          </p>
          <p className="text-sm font-semibold">{summary.snapshot_interval} 分钟</p>
        </div>
      </div>

      {/* 待买入计划 */}
      {(() => {
        const pendingBuys = plansData?.filter(p => p.direction === 'buy' && p.status === 'pending') || [];
        if (pendingBuys.length === 0) return null;
        const totalNeeded = pendingBuys.reduce((s, p) => s + (p.target_price * (p.quantity || 100)), 0);
        return (
          <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
              <h3 className="text-base font-semibold text-gray-900 dark:text-white">
                📋 待买入计划 ({pendingBuys.length})
              </h3>
              <span className="text-xs text-gray-500">
                预计需 {formatMoney(totalNeeded)}（可用 {formatMoney(summary.cash_balance)}）
              </span>
            </div>
            <div className="divide-y divide-gray-100 dark:divide-gray-700">
              {pendingBuys.map((p) => (
                <div key={p.id} className="flex items-center justify-between px-4 py-3 hover:bg-gray-50 dark:hover:bg-gray-750">
                  <div className="flex items-center gap-4 min-w-0">
                    <Link to={`/stock/${p.code}`} className="font-mono text-sm font-semibold text-blue-600 dark:text-blue-400 hover:underline shrink-0">
                      {p.code}
                    </Link>
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-gray-900 dark:text-white truncate">{p.name || p.code}</div>
                      <div className="text-xs text-gray-500">
                        目标 <span className="font-semibold text-red-600">¥{p.target_price.toFixed(2)}</span>
                        {p.quantity ? ` · ${p.quantity}股 · 共${formatMoney(p.target_price * p.quantity)}` : ''}
                      </div>
                      {p.reason && <div className="text-xs text-gray-400 mt-0.5 truncate max-w-[200px]">{p.reason}</div>}
                      <div className="text-[10px] text-gray-400 mt-0.5">{p.created_at}</div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-xs px-2 py-0.5 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300">待买入</span>
                    <button
                      onClick={() => cancelPlanMut.mutate(p.id)}
                      disabled={cancelPlanMut.isPending}
                      className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-500 hover:text-red-500 rounded hover:bg-red-50 dark:hover:bg-red-900/20 disabled:opacity-50"
                      title="取消计划"
                    >
                      取消
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })()}

      {/* Edit Interval Modal */}
      {editingInterval && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setEditingInterval(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">设置快照间隔</h3>
            <input
              type="number"
              value={newInterval}
              onChange={e => setNewInterval(Number(e.target.value))}
              className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
            />
            <p className="text-xs text-gray-500 mt-1">建议值: 15-240分钟，0=不自动快照</p>
            <div className="flex justify-end gap-3 mt-4">
              <button onClick={() => setEditingInterval(false)} className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">取消</button>
              <button onClick={() => intervalMut.mutate(newInterval)} disabled={intervalMut.isPending} className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50">保存</button>
            </div>
          </div>
        </div>
      )}

      {/* Equity Curve */}
      <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
        <h3 className="text-base font-semibold text-gray-900 dark:text-white mb-3">📈 收益曲线</h3>
        {curveData?.curve?.length ? (
          <div ref={chartRef} className="w-full" />
        ) : (
          <div className="text-center py-8 text-gray-400">
            <p>暂无快照数据</p>
            <p className="text-sm mt-1">点击「更新快照」开始记录收益曲线</p>
          </div>
        )}
      </div>

      {/* Positions Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            📦 持仓 ({positions?.length || 0})
          </h3>
        </div>
        {posLoading ? (
          <div className="text-center py-8 text-gray-400">加载中...</div>
        ) : !positions?.length ? (
          <div className="text-center py-8 text-gray-400">暂无持仓，点击「手动交易」开始模拟交易</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400">
                <tr>
                  <th className="text-left px-4 py-2">代码</th>
                  <th className="text-left px-4 py-2">名称</th>
                  <th className="text-right px-4 py-2">持股</th>
                  <th className="text-right px-4 py-2">均价</th>
                  <th className="text-right px-4 py-2">现价</th>
                  <th className="text-right px-4 py-2">市值</th>
                  <th className="text-right px-4 py-2">盈亏</th>
                  <th className="text-right px-4 py-2">当日</th>
                  <th className="text-left px-4 py-2">计划</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {positions.map((p) => (
                  <tr key={p.id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                    <td className="px-4 py-3 font-mono text-gray-900 dark:text-white">
                      {p.code}
                      {p.etf_replaced && <span className="ml-1 text-xs bg-yellow-100 dark:bg-yellow-900/30 text-yellow-600 rounded px-1">ETF</span>}
                    </td>
                    <td className="px-4 py-3 text-gray-700 dark:text-gray-300">{p.name}</td>
                    <td className="px-4 py-3 text-right text-gray-900 dark:text-white">{p.shares}</td>
                    <td className="px-4 py-3 text-right text-gray-700 dark:text-gray-300">{p.avg_cost.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right text-gray-900 dark:text-white">{p.current_price.toFixed(2)}</td>
                    <td className="px-4 py-3 text-right text-gray-900 dark:text-white font-medium">{formatMoney(p.market_value)}</td>
                    <td className={`px-4 py-3 text-right font-medium ${p.profit_pct >= 0 ? "text-red-500" : "text-green-500"}`}>
                      {fmtPct(p.profit_pct)}
                    </td>
                    <td className={`px-4 py-3 text-right font-medium ${p.today_profit_pct >= 0 ? "text-red-500" : "text-green-500"}`}>
                      {fmtPct(p.today_profit_pct)}
                    </td>
                    <td className="px-4 py-3">
                      {plansByCode[p.code]?.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                          {plansByCode[p.code].map((pl) => {
                            const isBuy = pl.direction === "buy";
                            const isTakeProfit = pl.direction === "sell" && pl.status === "take_profit";
                            const isStopLoss = pl.direction === "sell" && pl.status === "stop_loss";
                            let badgeClass = "bg-blue-100 dark:bg-blue-900/30 text-blue-600";
                            let icon = "🔵";
                            if (isTakeProfit) { badgeClass = "bg-red-100 dark:bg-red-900/30 text-red-600"; icon = "🔴"; }
                            if (isStopLoss) { badgeClass = "bg-green-100 dark:bg-green-900/30 text-green-600"; icon = "🟢"; }
                            return (
                              <span key={pl.id} className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full ${badgeClass}`}>
                                <span>{icon}</span>
                                <span>{pl.target_price.toFixed(2)}</span>
                              </span>
                            );
                          })}
                        </div>
                      ) : (
                        <button
                          onClick={() => {
                            setPlanModalCode(p.code);
                            setPlanDirection("buy");
                            setPlanTargetPrice("");
                            setPlanReason("");
                            setPlanModalOpen(true);
                          }}
                          className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                        >
                          + 添加计划
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Orders Table */}
      <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
        <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
          <h3 className="text-base font-semibold text-gray-900 dark:text-white">
            📝 交易记录 ({ordersData?.total || 0})
          </h3>
          {ordersData && (
            <div className="flex gap-2 text-sm">
              <button disabled={ordersPage <= 1} onClick={() => setOrdersPage(p => Math.max(1, p - 1))} className="px-2 py-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 disabled:opacity-30">&lt;</button>
              <span className="text-gray-500">{ordersPage}/{Math.max(1, Math.ceil((ordersData.total || 0) / 20))}</span>
              <button disabled={ordersPage >= Math.ceil((ordersData.total || 0) / 20)} onClick={() => setOrdersPage(p => p + 1)} className="px-2 py-1 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300 disabled:opacity-30">&gt;</button>
            </div>
          )}
        </div>
        {!ordersData?.orders?.length ? (
          <div className="text-center py-8 text-gray-400">暂无交易记录</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400">
                <tr>
                  <th className="text-left px-4 py-2">时间</th>
                  <th className="text-left px-4 py-2">方向</th>
                  <th className="text-left px-4 py-2">代码</th>
                  <th className="text-left px-4 py-2">名称</th>
                  <th className="text-right px-4 py-2">价格</th>
                  <th className="text-right px-4 py-2">数量</th>
                  <th className="text-right px-4 py-2">金额</th>
                  <th className="text-left px-4 py-2">类型</th>
                  <th className="text-left px-4 py-2">备注</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {ordersData.orders.map((o: Order) => (
                  <tr key={o.id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                    <td className="px-4 py-2 text-gray-500 text-xs">{new Date(o.created_at).toLocaleString("zh-CN")}</td>
                    <td className={`px-4 py-2 font-medium ${o.direction === "buy" ? "text-red-500" : "text-green-500"}`}>
                      {o.direction === "buy" ? "买入" : "卖出"}
                    </td>
                    <td className="px-4 py-2 font-mono text-gray-900 dark:text-white">{o.code}</td>
                    <td className="px-4 py-2 text-gray-700 dark:text-gray-300">{o.name}</td>
                    <td className="px-4 py-2 text-right text-gray-900 dark:text-white">{o.price.toFixed(2)}</td>
                    <td className="px-4 py-2 text-right text-gray-900 dark:text-white">{o.quantity}</td>
                    <td className="px-4 py-2 text-right text-gray-900 dark:text-white">{formatMoney(o.amount)}</td>
                    <td className="px-4 py-2">
                      <span className="text-xs px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                        {o.order_type === "manual" ? "手动" : o.order_type === "signal" ? "信号" : o.order_type}
                      </span>
                    </td>
                    <td className="px-4 py-2 text-gray-500 text-xs max-w-[100px] truncate">{o.note || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showTrade && (
        <TradeModal
          accountId={accountId}
          onClose={() => setShowTrade(false)}
          onSuccess={() => {
            queryClient.invalidateQueries({ queryKey: ["paper-positions", accountId] });
            queryClient.invalidateQueries({ queryKey: ["paper-orders", accountId] });
            queryClient.invalidateQueries({ queryKey: ["paper-summary", accountId] });
            queryClient.invalidateQueries({ queryKey: ["paper-curve", accountId] });
          }}
        />
      )}

      {/* Add Plan Modal */}
      {planModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setPlanModalOpen(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">
              添加买卖计划 - {planModalCode}
            </h3>
            <div className="space-y-4">
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">方向</label>
                <select
                  value={planDirection}
                  onChange={e => setPlanDirection(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                >
                  <option value="buy">买入</option>
                  <option value="sell">卖出</option>
                </select>
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">目标价格</label>
                <input
                  type="number"
                  step="0.01"
                  value={planTargetPrice}
                  onChange={e => setPlanTargetPrice(e.target.value)}
                  placeholder="0.00"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
              <div>
                <label className="block text-sm text-gray-600 dark:text-gray-400 mb-1">备注</label>
                <input
                  type="text"
                  value={planReason}
                  onChange={e => setPlanReason(e.target.value)}
                  placeholder="计划理由（可选）"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                />
              </div>
              <div className="flex justify-end gap-3 pt-2">
                <button onClick={() => setPlanModalOpen(false)} className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg">
                  取消
                </button>
                <button
                  onClick={() => {
                    if (!planTargetPrice) return;
                    createPlanMut.mutate({
                      code: planModalCode,
                      direction: planDirection,
                      target_price: parseFloat(planTargetPrice),
                      reason: planReason,
                    });
                  }}
                  disabled={createPlanMut.isPending || !planTargetPrice}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
                >
                  {createPlanMut.isPending ? "提交中..." : "确认添加"}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
