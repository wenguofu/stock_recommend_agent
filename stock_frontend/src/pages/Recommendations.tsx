import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface RecItem {
  id: number; rank: number; code: string; name: string;
  price: number; change_pct: number; turnover: number;
  score: number; reason: string; strategy: string;
  rec_type: string; created_at: string;
}

const STRATEGY_LABELS: Record<string, string> = {
  youzi: "游资策略",
  lianghua: "量化策略",
  jichang: "基础工具",
};

const STRATEGY_COLORS: Record<string, string> = {
  youzi: "bg-red-50 dark:bg-red-900/20 border-red-200 dark:border-red-800 text-red-700 dark:text-red-400",
  lianghua: "bg-blue-50 dark:bg-blue-900/20 border-blue-200 dark:border-blue-800 text-blue-700 dark:text-blue-400",
  jichang: "bg-green-50 dark:bg-green-900/20 border-green-200 dark:border-green-800 text-green-700 dark:text-green-400",
};

export default function Recommendations() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"daily" | "weekly">("daily");
  const [generating, setGenerating] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", activeTab],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/recommendations/latest?type=${activeTab}`);
      if (!r.ok) throw new Error("获取推荐失败");
      return r.json();
    },
    refetchInterval: 120000,
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${API_BASE}/api/recommendations/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: activeTab, top_n: 10 }),
      });
      if (!r.ok) throw new Error("生成失败");
      return r.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  const handleAddTracking = async (code: string, name: string) => {
    try {
      // Get first auto-trade account
      const r = await fetch(`${API_BASE}/api/paper/accounts`);
      const accts = await r.json();
      const autoAcct = accts.accounts?.find((a: any) => a.auto_trade);
      if (!autoAcct) {
        alert("没有自动跟踪账户，请先创建");
        return;
      }
      // Add auto-trade rule
      const r2 = await fetch(`${API_BASE}/api/paper/accounts/${autoAcct.id}/auto-rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code, name,
          buy_price_low: null,
          buy_price_high: null,
          buy_quantity: 100,
          sell_target_price: null,
          sell_stop_loss: null,
          note: `推荐跟踪: ${activeTab}推荐`,
        }),
      });
      if (r2.ok) {
        alert(`已将 ${name}(${code}) 加入自动跟踪`);
      }
    } catch (e) {
      alert("添加跟踪失败");
    }
  };

  const strategies = data?.strategies || {};

  // 收集所有推荐股票代码，批量获取板块信息
  const allCodes = useMemo(() => {
    const codes = new Set<string>();
    Object.values(strategies).forEach((items: any) => {
      (items as RecItem[]).forEach((r) => {
        // 提取纯6位代码
        const c = r.code?.replace(/[^0-9]/g, '').slice(0, 6);
        if (c && c.length === 6) codes.add(c);
      });
    });
    return Array.from(codes);
  }, [strategies]);

  const { data: sectorMap = {} } = useQuery({
    queryKey: ['rec-sector-map', allCodes],
    queryFn: async () => {
      const map: Record<string, string> = {};
      for (const code of allCodes.slice(0, 20)) {
        try {
          const r = await fetch(`${API_BASE}/api/sectors/stock/${code}`);
          if (r.ok) {
            const d = await r.json();
            if (d?.sector) map[code] = d.sector;
          }
        } catch {}
      }
      return map;
    },
    enabled: allCodes.length > 0,
    staleTime: 300000, // 5分钟缓存
  });

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">📋 股票推荐</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">
            基于多种策略自动筛选潜力股票
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm"
          >
            {generateMutation.isPending ? "生成中..." : "🔄 立即生成"}
          </button>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-2">
        <button
          onClick={() => setActiveTab("daily")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "daily"
              ? "bg-blue-600 text-white"
              : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
          }`}
        >
          📅 每日推荐
        </button>
        <button
          onClick={() => setActiveTab("weekly")}
          className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
            activeTab === "weekly"
              ? "bg-blue-600 text-white"
              : "bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700"
          }`}
        >
          📆 每周推荐
        </button>
      </div>

      {/* Loading */}
      {isLoading && (
        <div className="text-center py-12">
          <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto"></div>
        </div>
      )}

      {/* Empty */}
      {!isLoading && Object.keys(strategies).length === 0 && (
        <div className="text-center py-16 text-gray-400">
          <p className="text-2xl mb-2">📭</p>
          <p>暂无推荐数据</p>
          <p className="text-sm mt-2">点击「立即生成」获取今日推荐</p>
        </div>
      )}

      {/* Strategy Sections */}
      {Object.entries(strategies).map(([sname, items]) => {
        const recs = items as RecItem[];
        return (
          <div key={sname} className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
            {/* Strategy Header */}
            <div className={`px-4 py-3 border-b ${STRATEGY_COLORS[sname] || ""}`}>
              <h2 className="text-lg font-semibold">
                {STRATEGY_LABELS[sname] || sname}
              </h2>
            </div>

            {/* Picks Table */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400">
                  <tr>
                    <th className="text-center px-3 py-2 w-10">#</th>
                    <th className="text-left px-3 py-2">代码</th>
                    <th className="text-left px-3 py-2">名称</th>
                    <th className="text-left px-3 py-2">所属板块</th>
                    <th className="text-right px-3 py-2">价格</th>
                    <th className="text-right px-3 py-2">涨跌幅</th>
                    <th className="text-right px-3 py-2">换手率</th>
                    <th className="text-right px-3 py-2">评分</th>
                    <th className="text-left px-3 py-2">推荐理由</th>
                    <th className="text-center px-3 py-2">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {recs.map((rec) => (
                    <tr key={rec.id || rec.code} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                      <td className="text-center px-3 py-2 text-gray-400 font-mono">{rec.rank}</td>
                      <td className="px-3 py-2 font-mono text-gray-900 dark:text-white">
                        <button
                          onClick={() => navigate(`/stock/${rec.code}`)}
                          className="hover:text-blue-600"
                        >
                          {rec.code}
                        </button>
                      </td>
                      <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">{rec.name}</td>
                      <td className="px-3 py-2 text-xs">
                        {(() => {
                          const code = rec.code?.replace(/[^0-9]/g, '').slice(0, 6);
                          const sector = code ? sectorMap[code] : null;
                          if (!sector) return <span className="text-gray-400">--</span>;
                          const colorMap: Record<string, string> = {
                            '半导体': 'text-purple-600 bg-purple-50 dark:bg-purple-900/20',
                            '芯片': 'text-purple-600 bg-purple-50 dark:bg-purple-900/20',
                            '消费电子': 'text-blue-600 bg-blue-50 dark:bg-blue-900/20',
                            '新能源': 'text-green-600 bg-green-50 dark:bg-green-900/20',
                          };
                          let cls = 'text-gray-600 bg-gray-50 dark:bg-gray-700/50';
                          for (const [k, v] of Object.entries(colorMap)) {
                            if (sector.includes(k)) { cls = v; break; }
                          }
                          return <span className={`inline-block px-2 py-0.5 rounded-full ${cls}`}>{sector}</span>;
                        })()}
                      </td>
                      <td className="px-3 py-2 text-right text-gray-900 dark:text-white">{rec.price?.toFixed(2)}</td>
                      <td className={`px-3 py-2 text-right font-medium ${
                        (rec.change_pct || 0) >= 0 ? "text-red-500" : "text-green-500"
                      }`}>
                        {(rec.change_pct || 0) >= 0 ? "+" : ""}{rec.change_pct?.toFixed(1)}%
                      </td>
                      <td className="px-3 py-2 text-right text-gray-700 dark:text-gray-300">{rec.turnover?.toFixed(1)}%</td>
                      <td className="px-3 py-2 text-right">
                        <span className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
                          (rec.score || 0) >= 80
                            ? "bg-red-100 text-red-700"
                            : (rec.score || 0) >= 60
                            ? "bg-yellow-100 text-yellow-700"
                            : "bg-blue-100 text-blue-700"
                        }`}>
                          {rec.score}
                        </span>
                      </td>
                      <td className="px-3 py-2 text-gray-600 dark:text-gray-400 text-xs max-w-[200px]">
                        {rec.reason}
                      </td>
                      <td className="px-3 py-2 text-center">
                        <button
                          onClick={() => handleAddTracking(rec.code, rec.name)}
                          className="text-xs px-2 py-1 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400 rounded hover:bg-gray-200 dark:hover:bg-gray-600"
                          title="加入自动跟踪"
                        >
                          +跟踪
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        );
      })}

      {/* Generate result */}
      {generateMutation.data && (
        <div className="bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800 rounded-lg p-4 text-green-700 dark:text-green-400 text-sm">
          ✅ 生成完成！共 {generateMutation.data.count} 条推荐，
          {generateMutation.data.total_unique} 只个股
        </div>
      )}
    </div>
  );
}
