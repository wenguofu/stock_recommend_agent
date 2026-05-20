import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface ApplyToPaperPanelProps {
  codes: string[];
  jobName: string;
  strategyRunId: string;
}

interface PaperAccount {
  id: number;
  name: string;
  initial_capital: number;
}

export default function ApplyToPaperPanel({ codes, jobName, strategyRunId }: ApplyToPaperPanelProps) {
  const queryClient = useQueryClient();
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [showResult, setShowResult] = useState<{ success: boolean; message: string } | null>(null);

  const { data: accounts, isLoading } = useQuery({
    queryKey: ["paper-accounts"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts`);
      if (!r.ok) throw new Error("获取模拟盘列表失败");
      const d = await r.json();
      return d.accounts as PaperAccount[];
    },
  });

  const applyMutation = useMutation({
    mutationFn: async () => {
      if (!selectedAccountId) throw new Error("请选择模拟盘账户");

      const signals = codes.map((code) => ({
        code,
        name: "",
        direction: "buy",
        price: 0,
        quantity: 100,
        note: `策略信号: ${jobName}`,
      }));

      // Try to get real-time prices first
      const signalsWithPrices = await Promise.all(
        signals.map(async (s) => {
          try {
            const r = await fetch(`${API_BASE}/api/sina/realtime/${s.code}`);
            if (r.ok) {
              const data = await r.json();
              return {
                ...s,
                name: data.name || "",
                price: data.current_price || 0,
              };
            }
          } catch {}
          return s;
        })
      );

      const r = await fetch(`${API_BASE}/api/strategy/apply_to_paper`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          account_id: selectedAccountId,
          signals: signalsWithPrices,
          strategy_run_id: strategyRunId,
        }),
      });
      const result = await r.json();
      if (!r.ok) throw new Error(result.error || "应用失败");
      return result;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["paper-accounts"] });
      setShowResult({
        success: true,
        message: `成功执行 ${data.executed} 个信号${data.failed > 0 ? `，${data.failed} 个失败` : ""}`,
      });
    },
    onError: (error) => {
      setShowResult({ success: false, message: (error as Error).message });
    },
  });

  if (!accounts?.length) {
    return (
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
        <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">📊 应用到模拟盘</h3>
        <p className="text-gray-500 dark:text-gray-400 text-sm mb-4">
          还没有创建模拟盘账户，请先在模拟盘页面创建一个。
        </p>
        <a
          href="/paper"
          className="inline-block px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm"
        >
          前往模拟盘
        </a>
      </div>
    );
  }

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
      <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-2">
        📊 应用到模拟盘
      </h3>
      <p className="text-sm text-gray-500 dark:text-gray-400 mb-4">
        将策略分析结果中推荐的股票作为买入信号应用到模拟盘账户
      </p>

      {/* Target Stocks */}
      <div className="mb-4">
        <p className="text-xs text-gray-500 mb-1">目标股票 ({codes.length} 只):</p>
        <div className="flex flex-wrap gap-1">
          {codes.map((code) => (
            <span
              key={code}
              className="text-xs px-2 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded"
            >
              {code}
            </span>
          ))}
        </div>
      </div>

      {/* Account Selector */}
      <div className="flex items-center gap-3 mb-4">
        <select
          value={selectedAccountId ?? ""}
          onChange={(e) => setSelectedAccountId(Number(e.target.value) || null)}
          className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white text-sm focus:ring-2 focus:ring-blue-500"
        >
          <option value="">-- 选择模拟盘账户 --</option>
          {accounts.map((a) => (
            <option key={a.id} value={a.id}>
              {a.name} (初始 {a.initial_capital.toLocaleString()})
            </option>
          ))}
        </select>
        <button
          onClick={() => applyMutation.mutate()}
          disabled={!selectedAccountId || applyMutation.isPending}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm whitespace-nowrap"
        >
          {applyMutation.isPending ? "执行中..." : "应用信号"}
        </button>
      </div>

      {/* Result */}
      {showResult && (
        <div
          className={`text-sm p-3 rounded-lg ${
            showResult.success
              ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800"
              : "bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800"
          }`}
        >
          {showResult.message}
          {showResult.success && (
            <button
              onClick={() => {
                window.open(`/paper/${selectedAccountId}`, "_self");
              }}
              className="ml-3 underline"
            >
              查看账户
            </button>
          )}
          <button onClick={() => setShowResult(null)} className="ml-3 text-xs underline">
            关闭
          </button>
        </div>
      )}

      {/* Errors detail */}
      {applyMutation.data?.errors?.length > 0 && (
        <div className="mt-2 text-xs text-gray-500">
          <p className="font-medium mb-1">失败详情:</p>
          {applyMutation.data.errors.map((e: any, i: number) => (
            <p key={i}>
              #{e.index} {e.code}: {e.error}
            </p>
          ))}
        </div>
      )}
    </div>
  );
}
