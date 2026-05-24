import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import CandlestickChart from '../components/charts/CandlestickChart';
import AIAnalyzeButton from '../components/AIAnalyzeButton';
import MoneyFlowPanel from '../components/MoneyFlowPanel';
import RiskPanel from '../components/RiskPanel';
import MLPredictPanel from '../components/MLPredictPanel';
import { useState, useEffect } from 'react';

// 现代化的加载动画组件
function LoadingSpinner({ text = '加载中...' }: { text?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-12">
      <div className="relative w-16 h-16">
        <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-200 rounded-full"></div>
        <div className="absolute top-0 left-0 w-full h-full border-4 border-blue-600 rounded-full border-t-transparent animate-spin"></div>
      </div>
      <p className="mt-4 text-gray-500 dark:text-gray-400">{text}</p>
    </div>
  );
}

export default function StockDetail() {
  const { code } = useParams<{ code: string }>();
  const codeStr = code || '';

  // 分别加载不同数据，先显示已加载的
  const { data: realtimeData, isLoading: realtimeLoading } = useQuery({
    queryKey: ['realtime', codeStr],
    queryFn: () => stockAPI.getRealtime(codeStr),
    enabled: !!codeStr,
  });

  const { data: comprehensiveData, isLoading: comprehensiveLoading } = useQuery({
    queryKey: ['comprehensive', codeStr],
    queryFn: () => stockAPI.getComprehensive(codeStr),
    enabled: !!codeStr,
  });

  const { data: sentimentData, isLoading: sentimentLoading } = useQuery({
    queryKey: ['sentiment', codeStr],
    queryFn: () => stockAPI.getSentiment(codeStr, 7),
    enabled: !!codeStr,
  });

  // 获取日K线数据（优先使用缓存加速）
  const { data: dailyData, isLoading: dailyLoading } = useQuery({
    queryKey: ['daily', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const response = await fetch(`${apiUrl}/api/sina/daily/${codeStr}?count=240`);
      if (!response.ok) {
        throw new Error('Failed to fetch daily data');
      }
      const result = await response.json();
      return result;
    },
    enabled: !!codeStr,
  });

  // 获取自选股持仓信息
  const { data: watchlistData } = useQuery({
    queryKey: ['watchlist-stock', codeStr],
    queryFn: async () => {
      const items = await stockAPI.getWatchlist();
      return items.find((item: any) => item.code === codeStr) || null;
    },
    enabled: !!codeStr,
  });

  const positionCost = watchlistData?.cost_price;
  const positionShares = watchlistData?.shares;
  const hasPosition = positionCost != null && positionShares != null && positionShares > 0;
  const currentPrice = realtimeData?.current_price || comprehensiveData?.realtime?.current_price || 0;
  const positionValue = hasPosition ? currentPrice * positionShares : 0;
  const positionCostTotal = hasPosition ? positionCost * positionShares : 0;
  const positionPnl = positionValue - positionCostTotal;
  const positionPnlPercent = positionCost && positionCost > 0 ? (currentPrice - positionCost) / positionCost * 100 : 0;

  // 获取最新的分析报告
  const [latestReport, setLatestReport] = useState<string | null>(null);
  const [reportPositions, setReportPositions] = useState<{ long: string; short: string } | null>(null);
  
  // 预测
  const [forecastStrategy, setForecastStrategy] = useState('macd_cross');
  const [forecastDays, setForecastDays] = useState(22);
  const [forecastResult, setForecastResult] = useState<any>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState(0);
  
  const handleRunForecast = async () => {
    if (!codeStr) return;
    setForecastLoading(true);
    setForecastResult(null);
    setSelectedScenario(0);
    try {
      const res = await stockAPI.runForecast({ code: codeStr, strategy: forecastStrategy, params: {}, forecast_days: forecastDays });
      setForecastResult(res);
    } catch (e: any) {
      alert('预测失败: ' + (e.message || ''));
    } finally {
      setForecastLoading(false);
    }
  };
  
  useEffect(() => {
    if (!codeStr) return;
    stockAPI.listDebateJobs('completed', 10).then((jobs) => {
      const thisStockJobs = jobs.filter((j: any) => j.code === codeStr || (j.code && j.code.includes(codeStr)));
      if (thisStockJobs.length > 0) {
        const latest = thisStockJobs.sort((a: any, b: any) => 
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
        )[0];
        if (latest.report_md) {
          setLatestReport(latest.report_md);
          // 提取看多/看空总结
          const longMatch = latest.report_md.match(/(?:看多|多方|乐观).*?(?:\n|$)/);
          const shortMatch = latest.report_md.match(/(?:看空|空方|悲观|建议).*?(?:\n|$)/);
          setReportPositions({
            long: longMatch ? latest.report_md.substring(Math.max(0, longMatch.index! - 20), longMatch.index! + 80).trim() : '',
            short: shortMatch ? latest.report_md.substring(Math.max(0, shortMatch.index! - 20), shortMatch.index! + 80).trim() : '',
          });
        }
      }
    }).catch(() => {}); // 忽略错误
  }, [codeStr]);

  // 获取历史资金流向
  const { data: moneyFlowHistory, isLoading: moneyFlowHistoryLoading } = useQuery({
    queryKey: ['moneyFlowHistory', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const response = await fetch(`${apiUrl}/api/sina/money_flow/history/${codeStr}?days=60`);
      if (!response.ok) {
        throw new Error('Failed to fetch money flow history');
      }
      const result = await response.json();
      const data = result.data || [];
      // 按日期倒序排列（最新的在前）
      return data.sort((a: any, b: any) => {
        const dateA = new Date(a.date).getTime();
        const dateB = new Date(b.date).getTime();
        return dateB - dateA; // 倒序
      });
    },
    enabled: !!codeStr,
  });

  // 风险管理数据
  const { data: riskData, isLoading: riskLoading } = useQuery({
    queryKey: ['risk', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const positionData = (window as any).__positionData;
      const body: any = { code: codeStr };
      if (positionData) body.position = positionData;
      const response = await fetch(`${apiUrl}/api/risk/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error('Failed to fetch risk data');
      const result = await response.json();
      return result.data || null;
    },
    enabled: !!codeStr,
    retry: 1,
  });

  // ML预测数据
  const { data: mlData, isLoading: mlLoading } = useQuery({
    queryKey: ['ml_predict', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const response = await fetch(`${apiUrl}/api/ml/predict/${codeStr}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ horizon_days: 5 }),
      });
      if (!response.ok) throw new Error('Failed to fetch ML prediction');
      const result = await response.json();
      return result;
    },
    enabled: !!codeStr,
    retry: 1,
  });

  return (
    <div className="space-y-6">
      {/* 标题 */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className={`text-3xl font-bold ${
            (realtimeData?.change_percent ?? 0) >= 0
              ? 'text-red-600 dark:text-red-400'
              : 'text-green-600 dark:text-green-400'
          }`}>
            {realtimeData?.name || comprehensiveData?.realtime?.name || codeStr}
          </h1>
          <p className="text-gray-500 dark:text-gray-400">{codeStr}</p>
        </div>
        <AIAnalyzeButton code={codeStr} />
      </div>

      {/* 持仓状态栏 */}
      {hasPosition && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-6">
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">持仓成本</div>
                <div className="text-sm font-semibold text-gray-900 dark:text-white">
                  ¥{positionCost!.toFixed(2)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">持股数量</div>
                <div className="text-sm font-semibold text-gray-900 dark:text-white">
                  {positionShares!.toLocaleString()}股
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500 dark:text-gray-400">持仓市值</div>
                <div className="text-sm font-semibold text-gray-900 dark:text-white">
                  ¥{positionValue.toFixed(2)}
                </div>
              </div>
            </div>
            <div className="text-right">
              <div className="text-xs text-gray-500 dark:text-gray-400">持仓盈亏</div>
              <div className={`text-xl font-bold ${positionPnl >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {positionPnl >= 0 ? '+' : ''}{positionPnl.toFixed(2)}
              </div>
              <div className={`text-sm font-semibold ${positionPnlPercent >= 0 ? 'text-red-500' : 'text-green-500'}`}>
                {positionPnlPercent >= 0 ? '+' : ''}{positionPnlPercent.toFixed(2)}%
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 风险指标卡片 */}
      <RiskPanel riskData={riskData} />

      {/* 实时行情卡片 */}
      {realtimeLoading && comprehensiveLoading ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <LoadingSpinner text="加载实时行情..." />
        </div>
      ) : (realtimeData || comprehensiveData?.realtime) ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">实时行情</h2>
          {/* 优先使用comprehensiveData中的实时数据（包含换手率），如果没有则使用realtimeData */}
          {(() => {
            // 优先使用comprehensiveData.realtime（包含换手率），否则使用realtimeData
            const displayData = comprehensiveData?.realtime || realtimeData;
            return (
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">当前价</div>
                  <div className={`text-2xl font-bold ${
                    (displayData?.change_percent ?? 0) >= 0
                      ? 'text-red-600 dark:text-red-400'
                      : 'text-green-600 dark:text-green-400'
                  }`}>
                    {displayData?.current_price?.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">涨跌幅</div>
                  <div
                    className={`text-2xl font-bold ${
                      (displayData?.change_percent ?? 0) >= 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-green-600 dark:text-green-400'
                    }`}
                  >
                    {(displayData?.change_percent ?? 0) >= 0 ? '+' : ''}
                    {displayData?.change_percent?.toFixed(2)}%
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">最高</div>
                  <div className="text-xl font-semibold text-gray-900 dark:text-white">
                    {displayData?.high?.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">最低</div>
                  <div className="text-xl font-semibold text-gray-900 dark:text-white">
                    {displayData?.low?.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">成交量</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {displayData?.volume ? (displayData.volume / 10000).toFixed(0) + '万手' : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">成交额</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {displayData?.amount ? (displayData.amount / 100000000).toFixed(2) + '亿' : '--'}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">换手率</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {displayData?.turnover_rate != null && displayData.turnover_rate !== undefined 
                      ? displayData.turnover_rate.toFixed(2) + '%' 
                      : '--'}
                  </div>
                </div>
              </div>
            );
          })()}
        </div>
      ) : null}

      {/* K线图 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">K线图</h2>
        {dailyLoading ? (
          <LoadingSpinner text="加载K线数据..." />
        ) : (
          <CandlestickChart 
            code={codeStr} 
            indicatorsData={
              dailyData?.raw_data?.daily || 
              dailyData?.daily || 
              dailyData?.data ||
              comprehensiveData?.daily || 
              null
            }
          />
        )}
      </div>

      {/* 技术指标 */}
      {comprehensiveData?.indicators && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">技术指标</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {comprehensiveData.indicators.MA && Object.entries(comprehensiveData.indicators.MA).map(([key, value]: [string, any]) => (
              <div key={key}>
                <div className="text-sm text-gray-500 dark:text-gray-400">{key}</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {typeof value === 'number' ? value.toFixed(2) : value}
                </div>
              </div>
            ))}
            {comprehensiveData.indicators.RSI && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">RSI</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {comprehensiveData.indicators.RSI.toFixed(2)}
                </div>
              </div>
            )}
            {comprehensiveData.indicators.MACD && (
              <>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">MACD DIF</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {comprehensiveData.indicators.MACD.DIF?.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">MACD DEA</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {comprehensiveData.indicators.MACD.DEA?.toFixed(2)}
                  </div>
                </div>
              </>
            )}
            {comprehensiveData.indicators.KDJ && (
              <>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">KDJ K</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {comprehensiveData.indicators.KDJ.K?.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">KDJ D</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {comprehensiveData.indicators.KDJ.D?.toFixed(2)}
                  </div>
                </div>
                <div>
                  <div className="text-sm text-gray-500 dark:text-gray-400">KDJ J</div>
                  <div className="text-lg font-semibold text-gray-900 dark:text-white">
                    {comprehensiveData.indicators.KDJ.J?.toFixed(2)}
                  </div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {/* ML预测卡片 */}
      <MLPredictPanel mlData={mlData} />

      {/* 建议操作 - 基于最新分析报告 */}
      {latestReport && (() => {
        // 解析报告中的价格信息
        const currentPx = currentPrice || 0;
        
        // 从报告中提取关键价位
        const extractPrice = (pattern: RegExp): number | null => {
          const m = latestReport.match(pattern);
          return m ? parseFloat(m[1]) : null;
        };
        
        // 提取各类价格
        const support1 = extractPrice(/(?:第一观察位|第一支撑|支撑位1|观察位1).*?([\d.]+)/);
        const support2 = extractPrice(/(?:第二观察位|第二支撑|支撑位2|观察位2).*?([\d.]+)/);
        const resistance1 = extractPrice(/(?:第一压力|压力位1|目标位1|目标价1|上方目标).*?([\d.]+)/);
        const resistance2 = extractPrice(/(?:第二压力|压力位2|目标位2).*?([\d.]+)/);
        const stopLossPrice = extractPrice(/(?:止损|止损位|止损价|跌破).*?(?:设[于在置]|为|看至|看).*?([\d.]+)/);
        const takeProfit1 = extractPrice(/(?:止盈|目标价|目标位|减仓|卖出).*?(?:设[于在置]|为|看至|看|在).*?([\d.]+)/);
        
        // 从报告中提取看多/看空判断
        const isBearish = latestReport.includes('强烈看空') || latestReport.includes('建议规避') || latestReport.includes('不建议追') || latestReport.includes('清仓');
        const isBullish = latestReport.includes('强烈看多') || latestReport.includes('建议买入') || latestReport.includes('推荐买入') || latestReport.includes('加仓');
        const verdict = isBearish ? 'bearish' : isBullish ? 'bullish' : 'neutral';
        
        // 根据判断计算建议价格
        const calcPrice = (base: number | null, pct: number): number | null => {
          return base ? Math.round(base * (1 + pct) * 100) / 100 : null;
        };
        
        // 构建价格表格
        const actionList: { type: string; price: string; desc: string; color: string }[] = [];
        
        // 解析"目标价与操作时间线"表格
        const timelineMatch = latestReport.match(/## 目标价与操作时间线[\s\S]*?(?=\n## |$)/);
        const timelineRows: { node: string; price: string; action: string; logic: string }[] = [];
        if (timelineMatch) {
          const tableLines = timelineMatch[0].split('\n');
          let inTable = false;
          for (const line of tableLines) {
            if (line.includes('|') && line.includes('时间节点') && line.includes('目标价')) inTable = true;
            else if (inTable && line.trim().startsWith('|') && !line.includes('---')) {
              const cols = line.split('|').map(c => c.trim()).filter(Boolean);
              if (cols.length >= 4 && cols[0] !== '时间节点') {
                timelineRows.push({ node: cols[0], price: cols[1], action: cols[2], logic: cols[3] });
              }
            }
          }
        }
        
        if (verdict === 'bearish') {
          // 偏空：建议减仓/止损
          const suggestStopLoss = stopLossPrice || calcPrice(currentPx, -0.05);
          const suggestSupport1 = support1 || calcPrice(currentPx, -0.08);
          const suggestSupport2 = support2 || calcPrice(currentPx, -0.15);
          actionList.push(
            { type: '⚠️ 止损', price: suggestStopLoss ? `≤ ¥${suggestStopLoss.toFixed(2)}` : '--', desc: '跌破止损位应果断离场', color: 'text-red-600' },
            { type: '📉 减仓①', price: suggestSupport1 ? `¥${suggestSupport1.toFixed(2)}` : '--', desc: '第一观察位，分批减仓', color: 'text-orange-500' },
            { type: '📉 减仓②', price: suggestSupport2 ? `¥${suggestSupport2.toFixed(2)}` : '--', desc: '第二观察位，剩余仓位出清', color: 'text-orange-500' },
            { type: '⏸️ 观望', price: currentPx ? `¥${currentPx.toFixed(2)}` : '--', desc: '当前不宜追高，等待回调', color: 'text-gray-500' },
          );
        } else if (verdict === 'bullish') {
          // 偏多：建议加仓/止盈
          const suggestTP1 = takeProfit1 || resistance1 || calcPrice(currentPx, 0.1);
          const suggestTP2 = resistance2 || calcPrice(currentPx, 0.2);
          const suggestAdd = support1 || calcPrice(currentPx, -0.03);
          actionList.push(
            { type: '📈 加仓', price: suggestAdd ? `¥${suggestAdd.toFixed(2)}` : '--', desc: '回调至支撑位可加仓', color: 'text-red-600' },
            { type: '🎯 止盈①', price: suggestTP1 ? `¥${suggestTP1.toFixed(2)}` : '--', desc: '第一目标位，减仓锁定利润', color: 'text-green-600' },
            { type: '🎯 止盈②', price: suggestTP2 ? `¥${suggestTP2.toFixed(2)}` : '--', desc: '第二目标位，继续持有观察', color: 'text-green-600' },
          );
        } else {
          // 中性：观望
          const suggestTP = takeProfit1 || resistance1 || calcPrice(currentPx, 0.08);
          const suggestSL = stopLossPrice || calcPrice(currentPx, -0.05);
          actionList.push(
            { type: '🎯 上方', price: suggestTP ? `¥${suggestTP.toFixed(2)}` : '--', desc: '突破可看高一线', color: 'text-green-600' },
            { type: '🛡️ 下方', price: suggestSL ? `¥${suggestSL.toFixed(2)}` : '--', desc: '跌破注意风险', color: 'text-red-600' },
            { type: '⏸️ 观望', price: currentPx ? `¥${currentPx.toFixed(2)}` : '--', desc: '当前方向不明，建议观望', color: 'text-gray-500' },
          );
        }

        const verdictColors: Record<string, string> = {
          bearish: 'bg-green-50 dark:bg-green-900/20 border-green-400 dark:border-green-600',
          bullish: 'bg-red-50 dark:bg-red-900/20 border-red-400 dark:border-red-600',
          neutral: 'bg-yellow-50 dark:bg-yellow-900/20 border-yellow-400 dark:border-yellow-600',
        };
        const verdictLabels: Record<string, string> = {
          bearish: '📉 偏空 / 建议减仓规避',
          bullish: '📈 偏多 / 可持股观察',
          neutral: '⚖️ 中性 / 暂时观望',
        };
        const verdictTextColors: Record<string, string> = {
          bearish: 'text-green-700 dark:text-green-300',
          bullish: 'text-red-700 dark:text-red-300',
          neutral: 'text-yellow-700 dark:text-yellow-300',
        };

        return (
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow border-l-4 border-yellow-500">
            {/* 头部 */}
            <div className="p-4 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold text-gray-900 dark:text-white">📋 建议操作</h2>
                <span className="text-xs text-gray-500 dark:text-gray-400">基于最新AI分析报告</span>
              </div>
              <div className={`mt-2 p-2 rounded-lg border text-sm font-semibold ${verdictColors[verdict]} ${verdictTextColors[verdict]}`}>
                {verdictLabels[verdict]}
              </div>
            </div>

            {/* 价格操作表 */}
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/50">
                    <th className="px-4 py-2.5 text-left text-gray-600 dark:text-gray-400 font-medium">操作</th>
                    <th className="px-4 py-2.5 text-right text-gray-600 dark:text-gray-400 font-medium">参考价格</th>
                    <th className="px-4 py-2.5 text-left text-gray-600 dark:text-gray-400 font-medium">说明</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                  {actionList.map((action, i) => (
                    <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <td className={`px-4 py-2.5 font-semibold whitespace-nowrap ${action.color}`}>{action.type}</td>
                      <td className={`px-4 py-2.5 text-right font-mono font-bold whitespace-nowrap ${action.color}`}>{action.price}</td>
                      <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400">{action.desc}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* 目标价时间线 */}
            {timelineRows.length > 0 && (
              <div className="border-t border-gray-200 dark:border-gray-700">
                <div className="px-4 py-3 bg-gray-50 dark:bg-gray-700/30 border-b border-gray-200 dark:border-gray-700">
                  <h3 className="text-sm font-semibold text-gray-700 dark:text-gray-300">🎯 目标价与操作时间线</h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-700/30">
                        <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400 font-medium">时间</th>
                        <th className="px-4 py-2 text-right text-gray-600 dark:text-gray-400 font-medium">目标价</th>
                        <th className="px-4 py-2 text-center text-gray-600 dark:text-gray-400 font-medium">操作</th>
                        <th className="px-4 py-2 text-left text-gray-600 dark:text-gray-400 font-medium">逻辑</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                      {timelineRows.map((row, i) => {
                        const actionColors: Record<string, string> = {
                          '加仓': 'text-white', '持仓': 'text-white', '减仓': 'text-white',
                          '止盈': 'text-white', '止损': 'text-white',
                        };
                        const actionBg: Record<string, string> = {
                          '加仓': 'bg-red-600', '持仓': 'bg-blue-600', '减仓': 'bg-orange-500',
                          '止盈': 'bg-green-600', '止损': 'bg-red-600',
                        };
                        const act = row.action.replace(/[\/\s].*$/, '');
                        const color = actionColors[act] || 'text-white';
                        const bg = actionBg[act] || 'bg-gray-500';
                        return (
                          <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-700/30">
                            <td className="px-4 py-2.5 font-semibold text-gray-900 dark:text-white">{row.node}</td>
                            <td className="px-4 py-2.5 text-right font-mono font-bold text-gray-900 dark:text-white">{row.price}</td>
                            <td className="px-4 py-2.5 text-center">
                              <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${bg} ${color}`}>{row.action}</span>
                            </td>
                            <td className="px-4 py-2.5 text-gray-600 dark:text-gray-400 text-xs">{row.logic}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {/* 看多/看空辩论摘要 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 p-4 border-t border-gray-200 dark:border-gray-700 bg-gray-50/50 dark:bg-gray-700/20">
              <div className="p-2.5 bg-red-50 dark:bg-red-900/10 rounded-lg border border-red-200 dark:border-red-800">
                <div className="text-xs text-red-600 dark:text-red-400 font-semibold mb-1">📈 多方观点</div>
                <div className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                  {reportPositions?.long ? (
                    reportPositions.long.length > 80 ? reportPositions.long.slice(0, 80) + '...' : reportPositions.long
                  ) : '未提取到明确看多观点'}
                </div>
              </div>
              <div className="p-2.5 bg-green-50 dark:bg-green-900/10 rounded-lg border border-green-200 dark:border-green-800">
                <div className="text-xs text-green-600 dark:text-green-400 font-semibold mb-1">📉 空方观点</div>
                <div className="text-xs text-gray-600 dark:text-gray-400 leading-relaxed">
                  {reportPositions?.short ? (
                    reportPositions.short.length > 80 ? reportPositions.short.slice(0, 80) + '...' : reportPositions.short
                  ) : '未提取到明确看空观点'}
                </div>
              </div>
            </div>

            {/* 风险提示 */}
            <div className="px-4 py-2.5 border-t border-gray-200 dark:border-gray-700">
              <p className="text-xs text-gray-400 dark:text-gray-500">
                ⚠️ 价格建议由AI分析报告自动解析生成 + 基于当前价 ¥{currentPx.toFixed(2)} 计算，仅供参考，不构成投资建议
              </p>
            </div>
          </div>
        );
      })()}

      {/* 预测面板 */}
      {codeStr && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-5 border-l-4 border-blue-500">
          <div className="flex items-center gap-2 mb-3">
            <span className="text-lg">🔮</span>
            <h2 className="text-base font-bold text-gray-900 dark:text-white">未来买卖预测</h2>
          </div>
          <div className="flex flex-wrap items-end gap-3 mb-4">
            <div>
              <label className="block text-xs text-gray-500 mb-1">策略</label>
              <select
                value={forecastStrategy}
                onChange={e => { setForecastStrategy(e.target.value); setForecastResult(null); }}
                className="px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
              >
                <option value="ma_cross">均线金叉</option>
                <option value="macd_cross">MACD金叉死叉</option>
                <option value="rsi_reversal">RSI超买超卖</option>
                <option value="bollinger_break">布林带突破</option>
                <option value="sar_parabolic">SAR抛物线转向</option>
              </select>
            </div>
            <div>
              <label className="block text-xs text-gray-500 mb-1">预测天数</label>
              <input type="number" value={forecastDays} onChange={e => setForecastDays(Number(e.target.value))}
                className="w-20 px-3 py-2 text-sm border border-gray-300 dark:border-gray-600 rounded-lg bg-white dark:bg-gray-700 text-gray-900 dark:text-white"
                min={5} max={60} />
            </div>
            <button onClick={handleRunForecast} disabled={forecastLoading}
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 text-sm">
              {forecastLoading ? '预测中...' : '开始预测'}
            </button>
          </div>

          {forecastResult && (
            <div className="space-y-4">
              <div className="flex items-center gap-3 text-sm">
                <span className="text-gray-500">当前信号：</span>
                <span className={`px-2 py-0.5 rounded text-xs font-bold ${
                  forecastResult.current_signal === '买入' ? 'bg-red-600 text-white' :
                  forecastResult.current_signal === '卖出' ? 'bg-green-600 text-white' :
                  'bg-gray-500 text-white'
                }`}>{forecastResult.current_signal}</span>
                <span className="text-gray-500">最新价：<span className="font-semibold text-gray-900 dark:text-white">¥{forecastResult.last_price?.toFixed(2)}</span></span>
                <span className="text-gray-500">最新日期：{forecastResult.last_date}</span>
              </div>

              {/* 场景切换Tab */}
              <div className="flex flex-wrap gap-2">
                {forecastResult.scenarios?.map((s: any, i: number) => (
                  <button key={i} onClick={() => setSelectedScenario(i)}
                    className={`px-3 py-1.5 rounded-lg text-xs font-medium transition-all border ${
                      selectedScenario === i
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-300 shadow-sm'
                        : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-400 hover:border-blue-300'
                    }`}>
                    <div className="font-semibold">{s.name}</div>
                    <div className={`text-[10px] mt-0.5 ${
                      s.metrics.return >= 0 ? 'text-red-500' : 'text-green-500'
                    }`}>{s.metrics.return >= 0 ? '+' : ''}{s.metrics.return}%</div>
                  </button>
                ))}
              </div>

              {/* 选中场景的详情 */}
              {selectedScenario >= 0 && forecastResult.scenarios?.[selectedScenario] && (
                <div>
                  <div className="flex items-center gap-4 text-xs text-gray-500 mb-2">
                    <span>{forecastResult.scenarios[selectedScenario].description}</span>
                    <span>交易:<span className="font-semibold text-gray-700 dark:text-gray-300">{forecastResult.scenarios[selectedScenario].metrics.trades}次</span></span>
                    <span>最大回撤:<span className="font-semibold text-green-600">{forecastResult.scenarios[selectedScenario].metrics.max_drawdown}%</span></span>
                    <span>买入信号:<span className="font-semibold text-red-600">{forecastResult.scenarios[selectedScenario].metrics.buy_signals}</span></span>
                    <span>卖出信号:<span className="font-semibold text-green-600">{forecastResult.scenarios[selectedScenario].metrics.sell_signals}</span></span>
                  </div>
                  <div className="overflow-x-auto max-h-[300px] overflow-y-auto border border-gray-200 dark:border-gray-700 rounded-lg">
                    <table className="w-full text-sm">
                      <thead className="bg-gray-50 dark:bg-gray-900/50 text-gray-500 dark:text-gray-400 sticky top-0">
                        <tr>
                          <th className="text-left px-3 py-2">日期</th>
                          <th className="text-right px-3 py-2">预测价</th>
                          <th className="text-center px-3 py-2">信号</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100 dark:divide-gray-700">
                        {forecastResult.scenarios[selectedScenario].prediction?.map((p: any, i: number) => (
                          <tr key={i} className="hover:bg-gray-50 dark:hover:bg-gray-750">
                            <td className="px-3 py-2 text-xs text-gray-500 font-mono">{p.date}</td>
                            <td className="px-3 py-2 text-right font-mono font-semibold text-gray-900 dark:text-white">¥{p.price.toFixed(2)}</td>
                            <td className="px-3 py-2 text-center">
                              <span className={`inline-block px-2 py-0.5 rounded text-xs font-bold ${
                                p.signal === 1 ? 'bg-red-600 text-white' :
                                p.signal === -1 ? 'bg-green-600 text-white' :
                                'bg-gray-200 dark:bg-gray-600 text-gray-700 dark:text-gray-300'
                              }`}>{p.action}</span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              <p className="text-xs text-gray-400">⚠️ 预测基于策略模型+历史波动率模拟，仅供参考</p>
            </div>
          )}
        </div>
      )}

      {/* 基本面数据 */}
      {comprehensiveData?.fundamental && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">基本面数据</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {comprehensiveData.fundamental.pe && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">市盈率(PE)</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {comprehensiveData.fundamental.pe.toFixed(2)}
                </div>
              </div>
            )}
            {comprehensiveData.fundamental.pb && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">市净率(PB)</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {comprehensiveData.fundamental.pb.toFixed(2)}
                </div>
              </div>
            )}
            {comprehensiveData.fundamental.roe && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">净资产收益率(ROE)</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {comprehensiveData.fundamental.roe.toFixed(2)}%
                </div>
              </div>
            )}
            {comprehensiveData.fundamental.eps && (
              <div>
                <div className="text-sm text-gray-500 dark:text-gray-400">每股收益(EPS)</div>
                <div className="text-lg font-semibold text-gray-900 dark:text-white">
                  {comprehensiveData.fundamental.eps.toFixed(2)}
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 行业对比 */}
      {comprehensiveData?.industry_comparison && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">行业对比</h2>
          <div className="space-y-2">
            {comprehensiveData.industry_comparison.industry_name && (
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">行业：</span>
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  {comprehensiveData.industry_comparison.industry_name}
                </span>
              </div>
            )}
            {comprehensiveData.industry_comparison.rank && (
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">行业排名：</span>
                <span className="text-sm font-semibold text-gray-900 dark:text-white">
                  第 {comprehensiveData.industry_comparison.rank} 名
                </span>
              </div>
            )}
            {comprehensiveData.industry_comparison.industry_avg_change && (
              <div>
                <span className="text-sm text-gray-500 dark:text-gray-400">行业平均涨跌幅：</span>
                <span className={`text-sm font-semibold ${
                  comprehensiveData.industry_comparison.industry_avg_change >= 0
                    ? 'text-red-600 dark:text-red-400'
                    : 'text-green-600 dark:text-green-400'
                }`}>
                  {comprehensiveData.industry_comparison.industry_avg_change >= 0 ? '+' : ''}
                  {comprehensiveData.industry_comparison.industry_avg_change.toFixed(2)}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}

      {/* 今日资金流向 */}
      {comprehensiveData?.money_flow && <MoneyFlowPanel moneyFlow={comprehensiveData.money_flow} />}

      {/* 历史资金流向 */}
      {moneyFlowHistoryLoading ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <LoadingSpinner text="加载历史资金流向..." />
        </div>
      ) : moneyFlowHistory && moneyFlowHistory.length > 0 ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">历史资金流向（近60天）</h2>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 dark:border-gray-700">
                  <th className="text-left py-2 px-3 text-gray-500 dark:text-gray-400">日期</th>
                  <th className="text-right py-2 px-3 text-gray-500 dark:text-gray-400">主力净流入</th>
                  <th className="text-right py-2 px-3 text-gray-500 dark:text-gray-400">超大单</th>
                  <th className="text-right py-2 px-3 text-gray-500 dark:text-gray-400">大单</th>
                  <th className="text-right py-2 px-3 text-gray-500 dark:text-gray-400">收盘价</th>
                  <th className="text-right py-2 px-3 text-gray-500 dark:text-gray-400">涨跌幅</th>
                </tr>
              </thead>
              <tbody>
                {moneyFlowHistory.slice(0, 30).map((item: any, index: number) => (
                  <tr key={index} className="border-b border-gray-100 dark:border-gray-800">
                    <td className="py-2 px-3 text-gray-900 dark:text-white">{item.date}</td>
                    <td className={`py-2 px-3 text-right ${
                      (item.main_net_inflow || 0) >= 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-green-600 dark:text-green-400'
                    }`}>
                      {item.main_net_inflow != null ? (item.main_net_inflow >= 0 ? '+' : '') + item.main_net_inflow.toFixed(2) + '万' : '--'}
                    </td>
                    <td className={`py-2 px-3 text-right ${
                      (item.super_large_net_inflow || 0) >= 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-green-600 dark:text-green-400'
                    }`}>
                      {item.super_large_net_inflow != null ? (item.super_large_net_inflow >= 0 ? '+' : '') + item.super_large_net_inflow.toFixed(2) + '万' : '--'}
                    </td>
                    <td className={`py-2 px-3 text-right ${
                      (item.large_net_inflow || 0) >= 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-green-600 dark:text-green-400'
                    }`}>
                      {item.large_net_inflow != null ? (item.large_net_inflow >= 0 ? '+' : '') + item.large_net_inflow.toFixed(2) + '万' : '--'}
                    </td>
                    <td className="py-2 px-3 text-right text-gray-900 dark:text-white">
                      {item.close != null ? item.close.toFixed(2) : '--'}
                    </td>
                    <td className={`py-2 px-3 text-right ${
                      (item.change_percent || 0) >= 0
                        ? 'text-red-600 dark:text-red-400'
                        : 'text-green-600 dark:text-green-400'
                    }`}>
                      {item.change_percent != null ? (item.change_percent >= 0 ? '+' : '') + item.change_percent.toFixed(2) + '%' : '--'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : null}

      {/* 舆情数据 */}
      {sentimentLoading ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <LoadingSpinner text="加载舆情数据..." />
        </div>
      ) : sentimentData ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">舆情数据</h2>
          
          {/* 新闻 */}
          {sentimentData.news && sentimentData.news.list && sentimentData.news.list.length > 0 && (
            <div className="mb-6">
              <h3 className="text-lg font-semibold mb-3 text-gray-900 dark:text-white">相关新闻</h3>
              <div className="space-y-3">
                {sentimentData.news.list.slice(0, 10).map((news: any, index: number) => (
                  <div key={index} className="border-b border-gray-200 dark:border-gray-700 pb-3">
                    <a
                      href={news.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-blue-600 dark:text-blue-400 hover:underline"
                    >
                      <div className="font-medium">{news.title}</div>
                    </a>
                    <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {news.source} · {news.time}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 股吧帖子 */}
          {sentimentData.posts && (
            <>
              {sentimentData.posts.latest_posts && sentimentData.posts.latest_posts.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-lg font-semibold mb-3 text-gray-900 dark:text-white">最新帖子</h3>
                  <div className="space-y-3">
                    {sentimentData.posts.latest_posts.slice(0, 10).map((post: any, index: number) => (
                      <div key={index} className="border-b border-gray-200 dark:border-gray-700 pb-3">
                        <div className="font-medium text-gray-900 dark:text-white">{post.title}</div>
                        <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          {post.author} · {post.time} · 阅读 {post.read_count}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {sentimentData.posts.hot_posts && sentimentData.posts.hot_posts.length > 0 && (
                <div>
                  <h3 className="text-lg font-semibold mb-3 text-gray-900 dark:text-white">热门帖子</h3>
                  <div className="space-y-3">
                    {sentimentData.posts.hot_posts.slice(0, 10).map((post: any, index: number) => (
                      <div key={index} className="border-b border-gray-200 dark:border-gray-700 pb-3">
                        <div className="font-medium text-gray-900 dark:text-white">{post.title}</div>
                        <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                          {post.author} · {post.time} · 阅读 {post.read_count}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      ) : null}

      {/* Agent分析区域（待实现） */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">AI分析</h2>
        <p className="text-gray-500 dark:text-gray-400">Agent分析功能开发中...</p>
      </div>
    </div>
  );
}
