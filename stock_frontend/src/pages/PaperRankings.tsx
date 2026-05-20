import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface RankingItem {
  account_id: number;
  account_name: string;
  strategy_id: number | null;
  initial_capital: number;
  total_value: number;
  total_pnl: number;
  total_profit_pct: number;
  max_drawdown: number | null;
  win_rate: number | null;
  stock_count: number;
  order_count: number;
  days_running: number;
  created_at: string;
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

export default function PaperRankings() {
  const navigate = useNavigate();
  const [sortBy, setSortBy] = useState<"profit_pct" | "total_pnl" | "win_rate">("profit_pct");

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-rankings"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/profit-ranking`);
      if (!r.ok) throw new Error("获取排名失败");
      const d = await r.json();
      return d.rankings as RankingItem[];
    },
    refetchInterval: 30000,
  });

  const sorted = data
    ? [...data].sort((a, b) => {
        if (sortBy === "profit_pct") return b.total_profit_pct - a.total_profit_pct;
        if (sortBy === "total_pnl") return b.total_pnl - a.total_pnl;
        if (sortBy === "win_rate") return (b.win_rate ?? -999) - (a.win_rate ?? -999);
        return 0;
      })
    : [];

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">📊 收益排名</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            所有模拟盘按收益率倒序排列，评估各策略表现
          </p>
        </div>
        <button
          onClick={() => navigate("/paper")}
          className="px-4 py-2 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-200 dark:hover:bg-gray-600"
        >
          返回模拟盘
        </button>
      </div>

      {/* Sort Tabs */}
      <div className="flex gap-2">
        {[
          { key: "profit_pct" as const, label: "收益率" },
          { key: "total_pnl" as const, label: "总盈亏" },
          { key: "win_rate" as const, label: "胜率" },
        ].map((tab) => (
          <button
            key={tab.key}
            onClick={() => setSortBy(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              sortBy === tab.key
                ? "bg-blue-600 text-white"
                : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto"></div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-600">
          加载失败: {(error as Error).message}
        </div>
      )}

      {/* Empty */}
      {!isLoading && sorted.length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-2xl mb-2">📭</p>
          <p>暂无模拟盘数据</p>
        </div>
      )}

      {/* Ranking Table */}
      {sorted.length > 0 && (
        <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400">
                <tr>
                  <th className="text-center px-3 py-3 w-12">#</th>
                  <th className="text-left px-3 py-3">账户名称</th>
                  <th className="text-right px-3 py-3">收益率</th>
                  <th className="text-right px-3 py-3">总盈亏</th>
                  <th className="text-right px-3 py-3">总资产</th>
                  <th className="text-right px-3 py-3">起始资金</th>
                  <th className="text-right px-3 py-3">胜率</th>
                  <th className="text-right px-3 py-3">最大回撤</th>
                  <th className="text-center px-3 py-3">持仓</th>
                  <th className="text-center px-3 py-3">订单</th>
                  <th className="text-center px-3 py-3">运行</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                {sorted.map((item, idx) => {
                  const rankColors = ["text-yellow-500", "text-gray-400", "text-amber-600"];
                  return (
                    <tr
                      key={item.account_id}
                      onClick={() => navigate(`/paper/breakdown/${item.account_id}`)}
                      className="hover:bg-gray-50 dark:hover:bg-gray-750 cursor-pointer transition-colors"
                    >
                      <td className={`text-center px-3 py-3 font-bold text-lg ${rankColors[idx] || "text-gray-500"}`}>
                        {idx + 1 <= 3 ? ["🥇", "🥈", "🥉"][idx] : idx + 1}
                      </td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-gray-900 dark:text-white">{item.account_name}</div>
                        <div className="text-xs text-gray-400">
                          {item.strategy_id ? "策略盘" : "手动盘"}
                        </div>
                      </td>
                      <td className={`px-3 py-3 text-right font-bold text-base ${
                        item.total_profit_pct >= 0 ? "text-red-500" : "text-green-500"
                      }`}>
                        {fmtPct(item.total_profit_pct)}
                      </td>
                      <td className={`px-3 py-3 text-right font-medium ${
                        item.total_pnl >= 0 ? "text-red-500" : "text-green-500"
                      }`}>
                        {fmtMoney(item.total_pnl)}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-900 dark:text-white font-medium">
                        {fmtMoney(item.total_value)}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-500">
                        {fmtMoney(item.initial_capital)}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-700 dark:text-gray-300">
                        {fmtPct(item.win_rate)}
                      </td>
                      <td className="px-3 py-3 text-right text-gray-700 dark:text-gray-300">
                        {fmtPct(item.max_drawdown)}
                      </td>
                      <td className="text-center px-3 py-3 text-gray-900 dark:text-white">
                        {item.stock_count}
                      </td>
                      <td className="text-center px-3 py-3 text-gray-500">
                        {item.order_count}
                      </td>
                      <td className="text-center px-3 py-3 text-gray-500 text-xs">
                        {item.days_running}天
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
