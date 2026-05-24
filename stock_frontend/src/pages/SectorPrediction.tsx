import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { stockAPI } from "../services/api";

// 从 markdown 报告中解析出结构化数据
interface SectorPredictionItem {
  rank: number;
  name: string;
  total: number;
  scores: { supply_demand: number; cycle_position: number; tech_breakthrough: number; policy_catalyst: number; capital_flow: number; valuation_elasticity: number };
  rating: string;
  gates_passed: number;
  stocks: string;
  details?: Record<string, string>;
  gate_msgs?: string[];
}

function parseMarkdownReport(report: string): { date: string; sectors: SectorPredictionItem[] } | null {
  if (!report) return null;

  // Extract date
  const dateMatch = report.match(/日期:\s*(\d{4}-\d{2}-\d{2})/);
  const date = dateMatch ? dateMatch[1] : "";

  const sectors: SectorPredictionItem[] = [];
  
  // Parse table rows: | rank | name | total | sd | cp | tb | pc | cf | ve | rating |
  const tableRegex = /\|\s*(\d+)\s*\|\s*\*\*([^*]+)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|/g;
  let match;
  while ((match = tableRegex.exec(report)) !== null) {
    sectors.push({
      rank: parseInt(match[1]),
      name: match[2].trim(),
      total: parseInt(match[3]),
      scores: {
        supply_demand: parseInt(match[4]),
        cycle_position: parseInt(match[5]),
        tech_breakthrough: parseInt(match[6]),
        policy_catalyst: parseInt(match[7]),
        capital_flow: parseInt(match[8]),
        valuation_elasticity: parseInt(match[9]),
      },
      rating: match[10].trim(),
      gates_passed: 0,
      stocks: "",
    });
  }

  // Parse details for each sector
  for (const sec of sectors) {
    // Find section for this sector
    const sectionRegex = new RegExp(
      `###\\s*[^` + `]*` + `—\\s*${sec.name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}[^#]*?(?=###|##\\s*🏆|---|$)`,
      "s"
    );
    const sectionMatch = report.match(sectionRegex);
    if (sectionMatch) {
      const section = sectionMatch[0];
      
      // Extract scores details
      sec.details = {};
      const scoreDetailRegex = /\|\s*(供需失衡度|周期位置|技术突破|政策催化|资金信号|估值弹性)\s*\|\s*(\d+)\/10\s*\|\s*([^|]*)\s*\|/g;
      let dm;
      while ((dm = scoreDetailRegex.exec(section)) !== null) {
        const keyMap: Record<string, string> = {
          "供需失衡度": "supply_demand",
          "周期位置": "cycle_position",
          "技术突破": "tech_breakthrough",
          "政策催化": "policy_catalyst",
          "资金信号": "capital_flow",
          "估值弹性": "valuation_elasticity",
        };
        sec.details![keyMap[dm[1]]] = dm[3].trim();
      }

      // Extract gate messages
      sec.gate_msgs = [];
      const gateRegex = /-\s*(✅|❌)\s*(Gate\d\s*[^-\n]*)/g;
      let gm;
      while ((gm = gateRegex.exec(section)) !== null) {
        sec.gate_msgs.push(gm[0]);
        if (gm[1] === "✅") sec.gates_passed++;
      }

      // Extract stocks
      const stocksMatch = section.match(/\*\*领涨标的:\*\*\s*(.+)/);
      if (stocksMatch) {
        sec.stocks = stocksMatch[1].trim();
      }

      // Extract rating
      const ratingMatch = section.match(/\*\*评级:\s*(.+?)\*\*/);
      if (ratingMatch) {
        sec.rating = ratingMatch[1].trim();
      }
    }
  }

  return { date, sectors };
}

// 评分颜色映射
function scoreColor(s: number): string {
  if (s >= 8) return "text-green-600 dark:text-green-400 font-bold";
  if (s >= 6) return "text-yellow-600 dark:text-yellow-400";
  return "text-red-500 dark:text-red-400";
}

function ratingBadge(rating: string) {
  if (rating.includes("S级")) return "bg-red-600 text-white";
  if (rating.includes("A级")) return "bg-orange-500 text-white";
  if (rating.includes("B级")) return "bg-yellow-500 text-white";
  return "bg-gray-400 text-white";
}

const FACTOR_LABELS: Record<string, string> = {
  supply_demand: "供需",
  cycle_position: "周期",
  tech_breakthrough: "技术",
  policy_catalyst: "政策",
  capital_flow: "资金",
  valuation_elasticity: "估值",
};

export default function SectorPrediction() {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [selectedSector, setSelectedSector] = useState<string>("");
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["sector-prediction", showAll ? "all" : "latest"],
    queryFn: () => stockAPI.getSectorPrediction(undefined, showAll),
    refetchInterval: 300000,
  });

  const predictionData = useMemo(() => {
    if (!data?.data) return null;
    if (showAll && Array.isArray(data.data)) {
      return data.data.map((d: any) => parseMarkdownReport(d.report)).filter(Boolean);
    }
    return [parseMarkdownReport(data.data.report)].filter(Boolean);
  }, [data, showAll]);

  const currentData = useMemo(() => {
    if (!predictionData) return null;
    if (selectedDate && Array.isArray(predictionData)) {
      return predictionData.find((d: any) => d.date === selectedDate) || predictionData[0];
    }
    return predictionData[0];
  }, [predictionData, selectedDate]);

  const selectedDetail = useMemo(() => {
    if (!currentData || !selectedSector) return null;
    return currentData.sectors.find((s: SectorPredictionItem) => s.name === selectedSector);
  }, [currentData, selectedSector]);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-blue-600" />
      </div>
    );
  }

  if (isError || !currentData) {
    return (
      <div className="text-center py-20 text-gray-500">
        <p className="text-lg mb-2">暂无主线预判数据</p>
        <p className="text-sm">请先导入九大板块数据后运行预判引擎</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 头部 */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-bold text-gray-900 dark:text-white">🔮 主线预判</h2>
          <p className="text-sm text-gray-500 mt-1">
            基于六因子+四关卡模型，预判下一个主线板块
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => setShowAll(!showAll)}
            className={`px-3 py-1.5 rounded text-sm ${
              showAll
                ? "bg-blue-600 text-white"
                : "bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300"
            }`}
          >
            {showAll ? "收起" : "查看历史"}
          </button>
          <button
            onClick={() => queryClient.invalidateQueries({ queryKey: ["sector-prediction"] })}
            className="px-3 py-1.5 rounded text-sm bg-gray-200 dark:bg-gray-700 text-gray-700 dark:text-gray-300 hover:bg-gray-300"
          >
            🔄 刷新
          </button>
        </div>
      </div>

      {/* 历史日期选择 */}
      {showAll && Array.isArray(predictionData) && predictionData.length > 1 && (
        <div className="flex gap-2 flex-wrap">
          {predictionData.map((d: any) => (
            <button
              key={d.date}
              onClick={() => setSelectedDate(d.date)}
              className={`px-3 py-1 rounded text-sm ${
                (selectedDate || predictionData[0].date) === d.date
                  ? "bg-blue-600 text-white"
                  : "bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200"
              }`}
            >
              {d.date.slice(5)}
            </button>
          ))}
        </div>
      )}

      {/* 当前日期 */}
      <div className="text-sm text-gray-500">
        📅 {currentData.date} · {currentData.sectors.length} 个板块
      </div>

      {/* 评分汇总表 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow overflow-x-auto">
        <table className="min-w-full text-sm">
          <thead className="bg-gray-50 dark:bg-gray-700">
            <tr>
              <th className="px-3 py-2 text-left">#</th>
              <th className="px-3 py-2 text-left">板块</th>
              <th className="px-3 py-2 text-right">总分</th>
              {Object.keys(FACTOR_LABELS).map((k) => (
                <th key={k} className="px-2 py-2 text-center text-xs" title={FACTOR_LABELS[k]}>
                  {FACTOR_LABELS[k]}
                </th>
              ))}
              <th className="px-3 py-2 text-center">关卡</th>
              <th className="px-3 py-2 text-left">评级</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
            {currentData.sectors.map((s: SectorPredictionItem) => (
              <tr
                key={s.name}
                onClick={() => setSelectedSector(s.name)}
                className={`cursor-pointer transition-colors hover:bg-blue-50 dark:hover:bg-blue-900/20 ${
                  selectedSector === s.name ? "bg-blue-50 dark:bg-blue-900/30 ring-1 ring-blue-300" : ""
                }`}
              >
                <td className="px-3 py-2 text-gray-400">{s.rank}</td>
                <td className="px-3 py-2 font-medium text-gray-900 dark:text-white">{s.name}</td>
                <td className={`px-3 py-2 text-right font-mono font-bold ${s.total >= 65 ? "text-green-600" : s.total >= 50 ? "text-yellow-600" : "text-gray-400"}`}>
                  {s.total}
                </td>
                {Object.keys(FACTOR_LABELS).map((k) => (
                  <td key={k} className={`px-2 py-2 text-center font-mono text-xs ${scoreColor((s.scores as any)[k])}`}>
                    {(s.scores as any)[k]}
                  </td>
                ))}
                <td className="px-3 py-2 text-center">
                  <span className={`text-xs ${s.gates_passed >= 3 ? "text-green-600" : s.gates_passed >= 2 ? "text-yellow-600" : "text-gray-400"}`}>
                    {s.gates_passed}/4
                  </span>
                </td>
                <td className="px-3 py-2">
                  <span className={`px-2 py-0.5 rounded text-xs ${ratingBadge(s.rating)}`}>
                    {s.rating.slice(0, 2)}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 详情面板 */}
      {selectedDetail && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-bold text-gray-900 dark:text-white">
              {selectedDetail.name} · 综合评分 {selectedDetail.total}
            </h3>
            <span className={`px-3 py-1 rounded-full text-sm font-medium ${ratingBadge(selectedDetail.rating)}`}>
              {selectedDetail.rating}
            </span>
          </div>

          {/* 六因子详情 */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3 mb-4">
            {Object.entries(FACTOR_LABELS).map(([key, label]) => (
              <div key={key} className="bg-gray-50 dark:bg-gray-700 rounded p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-gray-500">{label}</span>
                  <span className={`text-lg font-bold ${scoreColor((selectedDetail.scores as any)[key])}`}>
                    {(selectedDetail.scores as any)[key]}
                    <span className="text-xs font-normal text-gray-400">/10</span>
                  </span>
                </div>
                {selectedDetail.details?.[key] && (
                  <p className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                    {selectedDetail.details[key]}
                  </p>
                )}
              </div>
            ))}
          </div>

          {/* 验证关卡 */}
          {selectedDetail.gate_msgs && selectedDetail.gate_msgs.length > 0 && (
            <div className="mb-3">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                验证关卡 (通过 {selectedDetail.gates_passed}/4)
              </h4>
              <div className="space-y-1">
                {selectedDetail.gate_msgs.map((gm: string, i: number) => (
                  <div
                    key={i}
                    className={`text-xs px-3 py-1.5 rounded ${
                      gm.includes("✅")
                        ? "bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400"
                        : "bg-red-50 dark:bg-red-900/20 text-red-500 dark:text-red-400"
                    }`}
                  >
                    {gm}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 领涨标的 */}
          {selectedDetail.stocks && (
            <div className="text-sm text-gray-600 dark:text-gray-400">
              <span className="font-medium">领涨标的:</span> {selectedDetail.stocks}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
