import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface PaperAccount {
  id: number;
  name: string;
  strategy_id: number | null;
  initial_capital: number;
  cash_balance: number;
  total_market_value: number;
  total_profit_pct: number;
  max_drawdown: number | null;
  win_rate: number | null;
  snapshot_interval: number;
  include_etf_replacement: boolean;
  enabled: boolean;
  created_at: string;
  position_count?: number;
}

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 100000000) {
    return (value / 100000000).toFixed(2) + "亿";
  }
  if (Math.abs(value) >= 10000) {
    return (value / 10000).toFixed(2) + "万";
  }
  return value.toFixed(2);
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return "-";
  return (value >= 0 ? "+" : "") + value.toFixed(2) + "%";
}

export default function PaperAccounts() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [showDelete, setShowDelete] = useState<number | null>(null);
  const [form, setForm] = useState({
    name: "",
    initial_capital: 1000000,
    snapshot_interval: 60,
    include_etf_replacement: true,
  });

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-accounts"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/paper/accounts`);
      if (!res.ok) throw new Error("获取模拟盘列表失败");
      const json = await res.json();
      return json.accounts as PaperAccount[];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (data: typeof form) => {
      const res = await fetch(`${API_BASE}/api/paper/accounts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!res.ok) throw new Error("创建失败");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-accounts"] });
      setShowCreate(false);
      setForm({ name: "", initial_capital: 1000000, snapshot_interval: 60, include_etf_replacement: true });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`${API_BASE}/api/paper/accounts/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("删除失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-accounts"] });
      setShowDelete(null);
    },
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">
            模拟盘
          </h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            管理模拟交易账户，跟踪验证量化策略
          </p>
        </div>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          新建模拟盘
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-500">加载中...</p>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-600 dark:text-red-400">
          加载失败: {(error as Error).message}
        </div>
      )}

      {/* Empty */}
      {data && data.length === 0 && !isLoading && (
        <div className="text-center py-16">
          <div className="text-6xl mb-4">📊</div>
          <h2 className="text-xl font-semibold text-gray-700 dark:text-gray-300 mb-2">
            还没有模拟盘账户
          </h2>
          <p className="text-gray-500 dark:text-gray-400 mb-6">
            创建一个模拟盘账户来开始跟踪你的策略表现
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            创建第一个模拟盘
          </button>
        </div>
      )}

      {/* Account Cards Grid */}
      {data && data.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {data.map((account) => (
            <div
              key={account.id}
              className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 hover:shadow-md transition-all cursor-pointer"
              onClick={() => navigate(`/paper/${account.id}`)}
            >
              <div className="p-5">
                {/* Account Name + Badge */}
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white truncate">
                    {account.name}
                  </h3>
                  <div className="flex gap-1">
                    {account.strategy_id && (
                      <span className="text-xs bg-purple-100 dark:bg-purple-900/30 text-purple-600 dark:text-purple-400 px-2 py-0.5 rounded-full">
                        策略盘
                      </span>
                    )}
                    {!account.enabled && (
                      <span className="text-xs bg-gray-100 dark:bg-gray-700 text-gray-500 px-2 py-0.5 rounded-full">
                        已停用
                      </span>
                    )}
                  </div>
                </div>

                {/* Stats */}
                <div className="space-y-3">
                  <div className="flex justify-between items-baseline">
                    <span className="text-sm text-gray-500 dark:text-gray-400">总资产</span>
                    <span className="text-2xl font-bold text-gray-900 dark:text-white">
                      {formatCurrency(
                        account.cash_balance + account.total_market_value
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline">
                    <span className="text-sm text-gray-500 dark:text-gray-400">收益率</span>
                    <span
                      className={`text-lg font-semibold ${
                        account.total_profit_pct >= 0
                          ? "text-red-500"
                          : "text-green-500"
                      }`}
                    >
                      {formatPercent(account.total_profit_pct)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 dark:text-gray-400">持仓数</span>
                    <span className="text-gray-700 dark:text-gray-300">
                      {account.position_count ?? 0} 只
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-500 dark:text-gray-400">初始资金</span>
                    <span className="text-gray-700 dark:text-gray-300">
                      {formatCurrency(account.initial_capital)}
                    </span>
                  </div>
                </div>

                {/* Max Drawdown + Win Rate */}
                <div className="mt-4 pt-3 border-t border-gray-100 dark:border-gray-700 flex justify-between text-xs text-gray-500 dark:text-gray-400">
                  <span>最大回撤: {formatPercent(account.max_drawdown)}</span>
                  <span>胜率: {formatPercent(account.win_rate)}</span>
                </div>
              </div>

              {/* Action Buttons */}
              <div
                className="px-5 py-2 bg-gray-50 dark:bg-gray-900/50 border-t border-gray-100 dark:border-gray-700 flex justify-end gap-2 rounded-b-xl"
                onClick={(e) => e.stopPropagation()}
              >
                <button
                  onClick={() => navigate(`/paper/${account.id}`)}
                  className="px-3 py-1 text-sm text-blue-600 hover:bg-blue-50 dark:hover:bg-blue-900/20 rounded transition-colors"
                >
                  查看详情
                </button>
                <button
                  onClick={() => setShowDelete(account.id)}
                  className="px-3 py-1 text-sm text-red-500 hover:bg-red-50 dark:hover:bg-red-900/20 rounded transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowCreate(false)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-md mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-4">
              新建模拟盘账户
            </h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  账户名称
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="例如: 游资策略盘"
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  初始资金
                </label>
                <input
                  type="number"
                  value={form.initial_capital}
                  onChange={(e) => setForm({ ...form, initial_capital: Number(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">
                  快照间隔（分钟）
                </label>
                <input
                  type="number"
                  value={form.snapshot_interval}
                  onChange={(e) => setForm({ ...form, snapshot_interval: Number(e.target.value) })}
                  className="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                />
              </div>
              <label className="flex items-center gap-2 text-sm text-gray-700 dark:text-gray-300">
                <input
                  type="checkbox"
                  checked={form.include_etf_replacement}
                  onChange={(e) => setForm({ ...form, include_etf_replacement: e.target.checked })}
                  className="rounded border-gray-300"
                />
                自动将科创板股票替换为ETF
              </label>
            </div>
            <div className="flex justify-end gap-3 mt-6">
              <button
                onClick={() => setShowCreate(false)}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => createMutation.mutate(form)}
                disabled={!form.name || createMutation.isPending}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {createMutation.isPending ? "创建中..." : "创建"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation */}
      {showDelete !== null && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowDelete(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-xl p-6 w-full max-w-sm mx-4 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
              确认删除
            </h3>
            <p className="text-gray-500 dark:text-gray-400 mb-2">
              删除后该模拟盘的所有持仓、交易记录和快照将被永久删除。
            </p>
            <p className="text-red-500 text-sm mb-4">
              此操作不可撤销！
            </p>
            <div className="flex justify-end gap-3">
              <button
                onClick={() => setShowDelete(null)}
                className="px-4 py-2 text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-700 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={() => deleteMutation.mutate(showDelete)}
                disabled={deleteMutation.isPending}
                className="px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 disabled:opacity-50 transition-colors"
              >
                {deleteMutation.isPending ? "删除中..." : "确认删除"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
