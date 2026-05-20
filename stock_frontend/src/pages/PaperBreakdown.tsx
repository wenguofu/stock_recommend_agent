import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface Trade {
  order_id: number;
  direction: string;
  price: number;
  quantity: number;
  amount: number;
  commission: number;
  tax: number;
  order_type: string;
  note: string | null;
  created_at: string;
}

interface StockBreakdown {
  code: string;
  name: string;
  total_buy: number;
  total_sell: number;
  buy_count: number;
  sell_count: number;
  total_commission: number;
  total_tax: number;
  realized_pnl: number;
  current_position: number;
  current_market_value: number;
  current_unrealized_pnl: number;
  total_pnl: number;
  trade_count: number;
  trades: Trade[];
}

interface BreakdownData {
  account_id: number;
  account_name: string;
  initial_capital: number;
  total_value: number;
  cash_balance: number;
  total_pnl: number;
  total_profit_pct: number;
  max_drawdown: number | null;
  win_rate: number | null;
  stock_count: number;
  stocks: StockBreakdown[];
}

function fmtMoney(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(2) + "万";
  return v.toFixed(2);
}

function fmtPct(v: number | null): string {
  if (v == null) return "-";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

export default function PaperBreakdown() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const accountId = parseInt(id || "0");
  const [expandedStock, setExpandedStock] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-breakdown", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/profit-breakdown`);
      if (!r.ok) throw new Error("获取明细失败");
      return r.json() as Promise<BreakdownData>;
    },
    enabled: !!accountId,
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full"></div>
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="text-center py-16">
        <div className="text-6xl mb-4">📭</div>
        <p className="text-gray-500">数据加载失败</p>
        <button onClick={() => navigate("/paper/rankings")} className="mt-4 px-4 py-2 bg-blue-600 text-white rounded-lg">
          返回排名
        </button>
      </div>
    );
  }

  // Sort stocks by total_pnl desc
  const sortedStocks = [...data.stocks].sort((a, b) => b.total_pnl - a.total_pnl);

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={() => navigate("/paper/rankings")} className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
            </svg>
          </button>
          <div>
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white">
              {data.account_name}
            </h1>
            <p className="text-sm text-gray-500">个股盈亏明细</p>
          </div>
        </div>
        <button
          onClick={() => navigate(`/paper/${accountId}`)}
          className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700"
        >
          查看账户详情
        </button>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-400">总资产</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{fmtMoney(data.total_value)}</p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-400">总盈亏</p>
          <p className={`text-lg font-bold ${data.total_pnl >= 0 ? "text-red-500" : "text-green-500"}`}>
            {fmtMoney(data.total_pnl)}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-400">收益率</p>
          <p className={`text-lg font-bold ${data.total_profit_pct >= 0 ? "text-red-500" : "text-green-500"}`}>
            {fmtPct(data.total_profit_pct)}
          </p>
        </div>
        <div className="bg-white dark:bg-gray-800 rounded-xl p-4 shadow-sm border border-gray-200 dark:border-gray-700">
          <p className="text-xs text-gray-500 dark:text-gray-400">交易股票数</p>
          <p className="text-lg font-bold text-gray-900 dark:text-white">{data.stock_count} 只</p>
        </div>
      </div>

      {/* Per-Stock Breakdown */}
      <div className="space-y-4">
        {sortedStocks.map((stock) => {
          const isExpanded = expandedStock === stock.code;
          return (
            <div
              key={stock.code}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden"
            >
              {/* Stock Header (clickable) */}
              <div
                className="p-4 flex items-center justify-between cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-750 transition-colors"
                onClick={() => setExpandedStock(isExpanded ? null : stock.code)}
              >
                <div className="flex items-center gap-3">
                  <div>
                    <span className="font-mono text-sm text-gray-400">{stock.code}</span>
                    <span className="ml-2 font-semibold text-gray-900 dark:text-white">{stock.name}</span>
                  </div>
                  <span className={`text-xs px-2 py-0.5 rounded-full ${
                    stock.current_position > 0
                      ? "bg-blue-100 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400"
                      : "bg-gray-100 dark:bg-gray-700 text-gray-500"
                  }`}>
                    {stock.current_position > 0 ? `持仓${stock.current_position}股` : "已清仓"}
                  </span>
                </div>
                <div className="flex items-center gap-6">
                  <div className="text-right">
                    <p className="text-xs text-gray-400">总盈亏</p>
                    <p className={`font-bold ${stock.total_pnl >= 0 ? "text-red-500" : "text-green-500"}`}>
                      {fmtMoney(stock.total_pnl)}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-gray-400">交易</p>
                    <p className="font-medium text-gray-700 dark:text-gray-300">{stock.trade_count}次</p>
                  </div>
                  <svg
                    className={`h-5 w-5 text-gray-400 transition-transform ${isExpanded ? "rotate-180" : ""}`}
                    fill="none" viewBox="0 0 24 24" stroke="currentColor"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                  </svg>
                </div>
              </div>

              {/* Expanded Detail */}
              {isExpanded && (
                <div className="border-t border-gray-100 dark:border-gray-700">
                  {/* Summary Row */}
                  <div className="grid grid-cols-2 md:grid-cols-5 gap-4 p-4 bg-gray-50 dark:bg-gray-900/30 text-sm">
                    <div>
                      <p className="text-gray-400 text-xs">买入总额</p>
                      <p className="font-medium text-gray-900 dark:text-white">{fmtMoney(stock.total_buy)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">卖出总额</p>
                      <p className="font-medium text-gray-900 dark:text-white">{fmtMoney(stock.total_sell)}</p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">已实现盈亏</p>
                      <p className={`font-medium ${stock.realized_pnl >= 0 ? "text-red-500" : "text-green-500"}`}>
                        {fmtMoney(stock.realized_pnl)}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">未实现盈亏</p>
                      <p className={`font-medium ${stock.current_unrealized_pnl >= 0 ? "text-red-500" : "text-green-500"}`}>
                        {fmtMoney(stock.current_unrealized_pnl)}
                      </p>
                    </div>
                    <div>
                      <p className="text-gray-400 text-xs">费用合计</p>
                      <p className="font-medium text-gray-700 dark:text-gray-300">
                        {fmtMoney(stock.total_commission + stock.total_tax)}
                      </p>
                    </div>
                  </div>

                  {/* Trade Records */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-xs">
                      <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500">
                        <tr>
                          <th className="text-left px-4 py-2">时间</th>
                          <th className="text-left px-4 py-2">方向</th>
                          <th className="text-right px-4 py-2">价格</th>
                          <th className="text-right px-4 py-2">数量</th>
                          <th className="text-right px-4 py-2">金额</th>
                          <th className="text-right px-4 py-2">佣金</th>
                          <th className="text-right px-4 py-2">印花税</th>
                          <th className="text-left px-4 py-2">类型</th>
                          <th className="text-left px-4 py-2">备注</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {stock.trades.map((t) => (
                          <tr key={t.order_id} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                            <td className="px-4 py-2 text-gray-500">{new Date(t.created_at).toLocaleString("zh-CN")}</td>
                            <td className={`px-4 py-2 font-medium ${t.direction === "buy" ? "text-red-500" : "text-green-500"}`}>
                              {t.direction === "buy" ? "买入" : "卖出"}
                            </td>
                            <td className="px-4 py-2 text-right text-gray-900 dark:text-white">{t.price.toFixed(2)}</td>
                            <td className="px-4 py-2 text-right text-gray-900 dark:text-white">{t.quantity}</td>
                            <td className="px-4 py-2 text-right text-gray-900 dark:text-white">{fmtMoney(t.amount)}</td>
                            <td className="px-4 py-2 text-right text-gray-500">{t.commission.toFixed(2)}</td>
                            <td className="px-4 py-2 text-right text-gray-500">{t.tax.toFixed(2)}</td>
                            <td className="px-4 py-2">
                              <span className="px-1.5 py-0.5 rounded bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                                {t.order_type === "manual" ? "手动" : t.order_type === "signal" ? "信号" : t.order_type}
                              </span>
                            </td>
                            <td className="px-4 py-2 text-gray-500 max-w-[120px] truncate">{t.note || "-"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
