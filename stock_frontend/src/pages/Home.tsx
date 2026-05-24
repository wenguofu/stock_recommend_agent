import { useQuery } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { stockAPI } from '../services/api';
import { useWatchlistStore } from '../store/watchlistStore';
import { useEffect, useState } from 'react';
import AIAnalyzeButton from '../components/AIAnalyzeButton';
import { findEtfs } from '../constants/sectorEtfs';

function isTradingTime(): boolean {
  const now = new Date(); const hour = now.getHours(); const minute = now.getMinutes(); const day = now.getDay();
  if (day === 0 || day === 6) return false;
  return (hour === 9 && minute >= 30 || hour > 9 && hour < 11 || hour === 11 && minute <= 30) || (hour >= 13 && hour < 15);
}
function getRefetchInterval(): number { return isTradingTime() ? 5000 : 60000; }

export default function Home() {
  const { items, fetchWatchlist } = useWatchlistStore();
  const [market, setMarket] = useState<'a' | 'us'>('a');
  const [debateFilter, setDebateFilter] = useState<'active' | 'completed'>('active');
  const location = useLocation();

  useEffect(() => { fetchWatchlist(); }, [fetchWatchlist]);

  const { data: debateJobs = [], isLoading: debateLoading, refetch: refetchDebates } = useQuery({
    queryKey: ['debate-jobs', debateFilter],
    queryFn: () => stockAPI.listDebateJobs(debateFilter, 20),
    refetchInterval: 5000,
  });
  useEffect(() => { refetchDebates(); }, [location.pathname, debateFilter, refetchDebates]);

  const handleStopDebate = async (jobId: string) => { await stockAPI.stopDebateJob(jobId); refetchDebates(); };
  const handleDeleteDebate = async (jobId: string) => { await stockAPI.deleteDebateJob(jobId); refetchDebates(); };

  const fetchIndexData = async (code: string) => {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
    const res = await fetch(`${apiUrl}/api/sina/realtime/${code}`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.message || data.error);
    return data;
  };

  // A股三大指数
  const { data: shIndex, isLoading: shLoading } = useQuery({queryKey: ['realtime','sh000001'], queryFn: () => fetchIndexData('sh000001'), refetchInterval: getRefetchInterval(), retry: 2});
  const { data: szIndex, isLoading: szLoading } = useQuery({queryKey: ['realtime','sz399001'], queryFn: () => fetchIndexData('sz399001'), refetchInterval: getRefetchInterval(), retry: 2});
  const { data: cybIndex, isLoading: cybLoading } = useQuery({queryKey: ['realtime','sz399006'], queryFn: () => fetchIndexData('sz399006'), refetchInterval: getRefetchInterval(), retry: 2});

  // 美股三大指数
  const { data: usDji, isLoading: usDjiLoading } = useQuery({queryKey: ['realtime','$dji'], queryFn: () => fetchIndexData('$dji'), refetchInterval: 30000, retry: 2});
  const { data: usInx, isLoading: usInxLoading } = useQuery({queryKey: ['realtime','$inx'], queryFn: () => fetchIndexData('$inx'), refetchInterval: 30000, retry: 2});
  const { data: usIxic, isLoading: usIxicLoading } = useQuery({queryKey: ['realtime','$ixic'], queryFn: () => fetchIndexData('$ixic'), refetchInterval: 30000, retry: 2});

  // 板块表现
  const { data: sectorPerf = [], isLoading: sectorLoading } = useQuery({
    queryKey: ['sector-performance'],
    queryFn: () => stockAPI.getSectorPerformance(),
    refetchInterval: 60000,
  });

  // 大盘研判
  const { data: outlook, isLoading: outlookLoading } = useQuery({
    queryKey: ['market-outlook'],
    queryFn: () => stockAPI.getMarketOutlook(),
    refetchInterval: 300000, // 5分钟刷新一次
    retry: 3,
  });

  const filteredItems = items.filter((item) => {
    if (market === 'a') return /^\d{6}$/.test(item.code);
    return /^[A-Za-z]{1,5}$/.test(item.code);
  });

  // 从辩论报告中提取热点板块
  const hotSectors = sectorPerf.filter((s: any) => s.avg_change > 0).slice(0, 10);
  const top5 = sectorPerf.slice(0, 5);
  const worst3 = sectorPerf.slice(-3).reverse();

  return (
    <div className="lg:flex lg:gap-3">
      {/* 左侧悬浮栏 - 操作推荐 & 大盘研判 */}
      <div className="lg:w-48 xl:w-60 lg:sticky lg:top-4 lg:self-start min-w-0 space-y-3 max-lg:mb-6">
        {/* 大盘研判 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4">
          <div className="flex items-center gap-1.5 mb-3">
            <span className="text-sm">📊</span>
            <h2 className="text-xs font-bold text-gray-900 dark:text-white">操作推荐 · 大盘研判</h2>
          </div>
          {outlookLoading && !outlook ? (
            <div className="text-center py-6 text-gray-500"><div className="animate-spin h-5 w-5 border-2 border-blue-600 border-t-transparent rounded-full mx-auto mb-2"></div><span className="text-xs">分析大盘数据中...</span></div>
          ) : outlook && outlook.success !== false ? (
            <div className="space-y-3">
              {/* 判定标签 */}
              <div className={`text-center py-2 px-3 rounded-lg text-sm font-bold ${
                outlook.market_status === 'bull' ? 'bg-red-50 dark:bg-red-900/20 text-red-700 dark:text-red-400 border border-red-200 dark:border-red-800/50' :
                outlook.market_status === 'bull_neutral' ? 'bg-orange-50 dark:bg-orange-900/20 text-orange-700 dark:text-orange-400 border border-orange-200 dark:border-orange-800/50' :
                outlook.market_status === 'neutral' ? 'bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400 border border-blue-200 dark:border-blue-800/50' :
                outlook.market_status === 'bear_neutral' ? 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-700 dark:text-yellow-400 border border-yellow-200 dark:border-yellow-800/50' :
                'bg-green-50 dark:bg-green-900/20 text-green-700 dark:text-green-400 border border-green-200 dark:border-green-800/50'
              }`}>{outlook.verdict}</div>

              {/* 分数条 */}
              <div>
                <div className="flex justify-between text-[10px] text-gray-500 mb-1">
                  <span>偏空</span>
                  <span className="font-bold text-xs">{outlook.score}分</span>
                  <span>偏多</span>
                </div>
                <div className="h-1.5 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
                  <div className="h-full rounded-full transition-all" style={{
                    width: `${(outlook.score + 100) / 2}%`,
                    background: outlook.score >= 0
                      ? `linear-gradient(90deg, #f59e0b, ${outlook.score > 20 ? '#ef4444' : '#f97316'})`
                      : `linear-gradient(90deg, ${outlook.score < -20 ? '#22c55e' : '#eab308'}, #f59e0b)`
                  }}></div>
                </div>
              </div>

              {/* 关键指标 */}
              <div className="grid grid-cols-2 gap-1.5 text-[11px]">
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded p-1.5">
                  <div className="text-gray-500">当前</div>
                  <div className="font-semibold text-gray-900 dark:text-white">{outlook.cur_price?.toFixed(0)}</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded p-1.5">
                  <div className="text-gray-500">MA20</div>
                  <div className="font-semibold text-gray-900 dark:text-white">{outlook.ma20?.toFixed(0)}</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded p-1.5">
                  <div className="text-gray-500">MA60</div>
                  <div className="font-semibold text-gray-900 dark:text-white">{outlook.ma60?.toFixed(0)}</div>
                </div>
                <div className="bg-gray-50 dark:bg-gray-700/50 rounded p-1.5">
                  <div className="text-gray-500">MA120</div>
                  <div className="font-semibold text-gray-900 dark:text-white">{outlook.ma120?.toFixed(0)}</div>
                </div>
              </div>

              {/* 近6月波动区间 */}
              <div className="text-[11px]">
                <div className="flex justify-between text-gray-500 mb-1">
                  <span>低 {outlook.low_6m?.toFixed(0)}</span>
                  <span>近6月区间</span>
                  <span>高 {outlook.high_6m?.toFixed(0)}</span>
                </div>
                <div className="h-2 bg-gradient-to-r from-green-400 via-yellow-400 to-red-400 rounded-full relative">
                  <div className="absolute top-0.5 w-0.5 h-1 bg-black dark:bg-white rounded-full transition-all" style={{
                    left: `${(outlook.cur_price - outlook.low_6m) / (outlook.high_6m - outlook.low_6m) * 100}%`
                  }}></div>
                </div>
              </div>

              {/* 近期涨跌 */}
              <div className="grid grid-cols-3 gap-1 text-center text-[11px]">
                <div>
                  <div className="text-gray-500">近1月</div>
                  <div className={`font-semibold ${outlook.pct_30d >= 0 ? 'text-red-600' : 'text-green-600'}`}>{outlook.pct_30d >= 0 ? '+' : ''}{outlook.pct_30d}%</div>
                </div>
                <div>
                  <div className="text-gray-500">近2月</div>
                  <div className={`font-semibold ${outlook.pct_60d >= 0 ? 'text-red-600' : 'text-green-600'}`}>{outlook.pct_60d >= 0 ? '+' : ''}{outlook.pct_60d}%</div>
                </div>
                <div>
                  <div className="text-gray-500">近6月</div>
                  <div className={`font-semibold ${outlook.pct_120d >= 0 ? 'text-red-600' : 'text-green-600'}`}>{outlook.pct_120d >= 0 ? '+' : ''}{outlook.pct_120d}%</div>
                </div>
              </div>

              {/* 操作建议 */}
              <div className="bg-blue-50 dark:bg-blue-900/10 rounded-lg p-3 border border-blue-100 dark:border-blue-800/30">
                <h3 className="text-[11px] font-bold text-gray-900 dark:text-white mb-1">📋 操作建议</h3>
                <p className="text-[11px] text-gray-700 dark:text-gray-300 leading-relaxed">{outlook.suggest}</p>
              </div>

              {/* 未来1月展望 */}
              <div className="bg-purple-50 dark:bg-purple-900/10 rounded-lg p-3 border border-purple-100 dark:border-purple-800/30">
                <h3 className="text-[11px] font-bold text-gray-900 dark:text-white mb-1">🔮 未来1月展望</h3>
                <p className="text-[11px] text-gray-700 dark:text-gray-300 leading-relaxed">{outlook.outlook}</p>
              </div>

              {/* 核心逻辑 */}
              <details className="text-[11px]">
                <summary className="text-gray-500 cursor-pointer hover:text-gray-700 dark:hover:text-gray-300">评分依据 ({outlook.reasons?.length || 0}条)</summary>
                <ul className="mt-1.5 space-y-1 pl-2">
                  {outlook.reasons?.map((r: string, i: number) => (
                    <li key={i} className="text-gray-600 dark:text-gray-400 leading-relaxed">· {r}</li>
                  ))}
                </ul>
              </details>
            </div>
          ) : (
            <div className="text-center py-6 text-gray-500 text-xs">数据获取失败</div>
          )}
        </div>
      </div>

      {/* 主内容区 */}
      <div className="flex-1 min-w-0 space-y-6">
        {/* 市场切换Tab */}
        <div className="flex items-center gap-1 bg-gray-100 dark:bg-gray-800 rounded-xl p-1 w-fit shadow">
          <button onClick={() => setMarket('a')} className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${market === 'a' ? 'bg-white dark:bg-gray-700 text-red-600 dark:text-red-400 shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}`}>🇨🇳 A股</button>
          <button onClick={() => setMarket('us')} className={`px-5 py-2 rounded-lg text-sm font-semibold transition-all ${market === 'us' ? 'bg-white dark:bg-gray-700 text-blue-600 dark:text-blue-400 shadow-sm' : 'text-gray-600 dark:text-gray-400 hover:text-gray-900 dark:hover:text-white'}`}>🇺🇸 美股</button>
        </div>

        {/* 三大指数 */}
        {market === 'a' ? (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <IndexCard title="上证指数" data={shIndex} isLoading={shLoading} gradientFrom="from-blue-600" gradientTo="to-blue-800" />
            <IndexCard title="深证成指" data={szIndex} isLoading={szLoading} gradientFrom="from-indigo-600" gradientTo="to-indigo-800" />
            <IndexCard title="创业板指" data={cybIndex} isLoading={cybLoading} gradientFrom="from-purple-600" gradientTo="to-purple-800" />
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <IndexCard title="道琼斯" data={usDji} isLoading={usDjiLoading} gradientFrom="from-blue-700" gradientTo="to-blue-900" />
            <IndexCard title="标普500" data={usInx} isLoading={usInxLoading} gradientFrom="from-sky-600" gradientTo="to-sky-800" />
            <IndexCard title="纳斯达克" data={usIxic} isLoading={usIxicLoading} gradientFrom="from-cyan-600" gradientTo="to-cyan-800" />
          </div>
        )}

        {/* 自选股 */}
        <div>
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
              {market === 'a' ? 'A股自选' : '美股自选'}
              <span className="ml-2 text-sm font-normal text-gray-500 dark:text-gray-400">({filteredItems.length}只)</span>
            </h2>
            <Link to="/watchlist" className="text-blue-600 hover:text-blue-800 dark:text-blue-400">管理自选</Link>
          </div>
          {filteredItems.length === 0 ? (
            <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-lg shadow">
              <p className="text-gray-500 dark:text-gray-400">{market === 'a' ? '暂无A股自选' : '暂无美股自选'}</p>
              <Link to="/watchlist" className="mt-4 inline-block text-blue-600 hover:text-blue-800 dark:text-blue-400">添加自选股</Link>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredItems.map((item) => (<StockCard key={item.code} code={item.code} name={item.name} />))}
            </div>
          )}
        </div>

        {/* 辩论记录 */}
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-2xl font-bold text-gray-900 dark:text-white">辩论记录</h2>
            <div className="flex gap-2">
              <button onClick={() => setDebateFilter('active')} className={`px-3 py-1 rounded ${debateFilter === 'active' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>进行中</button>
              <button onClick={() => setDebateFilter('completed')} className={`px-3 py-1 rounded ${debateFilter === 'completed' ? 'bg-blue-600 text-white' : 'bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300'}`}>已完成</button>
            </div>
          </div>
          {debateLoading ? (<div className="text-gray-500">加载中...</div>
          ) : debateJobs.length === 0 ? (<div className="text-gray-500">暂无任务</div>
          ) : (
            <div className="space-y-2">
              {debateJobs.map((job) => (
                <Link key={job.job_id} to={`/ai-debate?code=${job.code}&job_id=${job.job_id}`} className="flex items-center justify-between p-3 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700">
                  <div>
                    <div className="font-semibold text-gray-900 dark:text-white">{job.name}</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400">{job.updated_at}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-1 rounded ${job.status === 'completed' ? 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300' : job.status === 'failed' ? 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300' : job.status === 'canceled' ? 'bg-gray-200 text-gray-700 dark:bg-gray-700 dark:text-gray-300' : 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-300'}`}>
                      {job.status === 'completed' ? '已完成' : job.status === 'failed' ? '失败' : job.status === 'canceled' ? '已终止' : '进行中'}
                    </span>
                    <button onClick={(e) => { e.preventDefault(); handleStopDebate(job.job_id); }} disabled={job.status !== 'queued' && job.status !== 'running'} className="text-xs px-2 py-1 bg-yellow-600 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed">终止</button>
                    <button onClick={(e) => { e.preventDefault(); handleDeleteDebate(job.job_id); }} disabled={job.status === 'queued' || job.status === 'running'} className="text-xs px-2 py-1 bg-red-600 text-white rounded disabled:opacity-50 disabled:cursor-not-allowed">删除</button>
                  </div>
                </Link>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 右侧悬浮栏 - 板块市场预览（仅A股模式） */}
      {market === 'a' && (
        <div className="lg:w-48 xl:w-60 lg:sticky lg:top-4 lg:self-start min-w-0 space-y-3 max-lg:mt-6">
          {/* 今日热点板块 TOP 8 */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
            <div className="px-4 py-3 border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                <span className="text-base">🔥</span>
                <h2 className="text-sm font-bold text-gray-900 dark:text-white">今日热点板块</h2>
                {sectorLoading && <div className="animate-spin h-3 w-3 border-2 border-blue-600 border-t-transparent rounded-full"></div>}
              </div>
              <p className="text-[11px] text-gray-500 mt-0.5">基于成分股实时涨跌幅平均</p>
            </div>
            {sectorLoading && hotSectors.length === 0 ? (
              <div className="text-center py-6 text-gray-500 text-xs">计算板块表现中...</div>
            ) : (
              <div className="divide-y divide-gray-100 dark:divide-gray-700">
                {hotSectors.slice(0, 8).map((s: any, i: number) => {
                  const etfs = findEtfs(s.name);
                  return (
                    <div key={s.name} className="flex items-center justify-between px-4 py-2.5 hover:bg-gray-50 dark:hover:bg-gray-700/30">
                      <div className="flex items-center gap-2 min-w-0 flex-1">
                        <span className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-bold text-white shrink-0 ${i < 3 ? 'bg-red-500' : 'bg-blue-500'}`}>{i + 1}</span>
                        <div className="min-w-0">
                          <div className="text-xs font-semibold text-gray-900 dark:text-white truncate">{s.name}</div>
                          <div className="text-[10px] text-gray-500">{s.valid_stocks}/{s.total_stocks}只涨</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {etfs && (
                          <Link to={`/stock/${etfs[0].code}`} className="text-[10px] px-1.5 py-0.5 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded border border-blue-200 dark:border-blue-800 hover:bg-blue-100 leading-none">
                            {etfs[0].name.replace(/ETF$/, '')}
                          </Link>
                        )}
                        <div className={`text-right font-bold text-xs min-w-[56px] ${s.avg_change >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                          {s.avg_change >= 0 ? '+' : ''}{s.avg_change.toFixed(2)}%
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
            <div className="px-4 py-2 border-t border-gray-100 dark:border-gray-700 text-[10px] text-gray-400 text-center">
              {sectorPerf.reduce((a: number, s: any) => a + s.valid_stocks, 0)} 只成分股
            </div>
          </div>

          {/* TOP 5 + 偏弱 并排 */}
          <div className="grid grid-cols-2 gap-3">
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-sm">📈</span>
                <h3 className="text-xs font-bold text-gray-900 dark:text-white">最强 TOP 5</h3>
              </div>
              <div className="space-y-2">
                {top5.map((s: any, i: number) => (
                  <div key={s.name} className="flex items-center justify-between">
                    <span className="text-[11px] text-gray-700 dark:text-gray-300 truncate flex-1">{i + 1}. {s.name}</span>
                    <span className="text-[11px] font-bold text-red-600 dark:text-red-400 shrink-0 ml-1">+{s.avg_change.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-3">
              <div className="flex items-center gap-1.5 mb-2">
                <span className="text-sm">📉</span>
                <h3 className="text-xs font-bold text-gray-900 dark:text-white">偏弱 TOP 3</h3>
              </div>
              <div className="space-y-2">
                {worst3.map((s: any, i: number) => (
                  <div key={s.name} className="flex items-center justify-between">
                    <span className="text-[11px] text-gray-700 dark:text-gray-300 truncate flex-1">{i + 1}. {s.name}</span>
                    <span className="text-[11px] font-bold text-green-600 dark:text-green-400 shrink-0 ml-1">{s.avg_change.toFixed(1)}%</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* 下一个主线预测 */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-l-4 border-purple-500">
            <div className="flex items-center gap-1.5 mb-2">
              <span className="text-sm">🔮</span>
              <h2 className="text-xs font-bold text-gray-900 dark:text-white">下一个主线预测</h2>
            </div>
            {hotSectors.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs text-gray-600 dark:text-gray-400">
                  当前：<span className="font-bold text-red-600 dark:text-red-400">{hotSectors[0]?.name}</span>
                  {findEtfs(hotSectors[0]?.name) && (
                    <Link to={`/stock/${findEtfs(hotSectors[0]?.name)![0].code}`} className="ml-1.5 text-[10px] text-blue-500 hover:underline">
                      → {findEtfs(hotSectors[0]?.name)![0].name}
                    </Link>
                  )}
                </p>
                <p className="text-[11px] text-gray-500 leading-relaxed">
                  {(() => {
                    if (hotSectors.length < 2) return '数据不足，难以预测';
                    const top = hotSectors[0];
                    const second = hotSectors[1];
                    const gap = (top.avg_change - second.avg_change).toFixed(2);
                    if (parseFloat(gap) > 2) return `💡 ${top.name} 领先优势明显（+${gap}%），预计仍为主线。关注低位补涨。`;
                    return `📊 ${top.name} 与 ${second.name} 差距仅 ${gap}%，若 ${second.name} 放量有望轮动为新主线。`;
                  })()}
                </p>
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {hotSectors.slice(0, 5).map((s: any) => (
                    <Link key={s.name} to={`/stock/${findEtfs(s.name)?.[0]?.code || ''}`}
                      className={`px-2 py-0.5 text-[10px] rounded-full border leading-normal ${
                        s.avg_change > 0 ? 'bg-red-50 dark:bg-red-900/10 border-red-200 dark:border-red-800 text-red-700 dark:text-red-300' : 'bg-green-50 dark:bg-green-900/10 border-green-200 dark:border-green-800 text-green-700 dark:text-green-300'
                      } ${!findEtfs(s.name) ? 'opacity-60 pointer-events-none' : 'hover:bg-opacity-80'}`}
                    >
                      {s.name} {s.avg_change >= 0 ? '+' : ''}{s.avg_change.toFixed(1)}%
                    </Link>
                  ))}
                </div>
              </div>
            ) : (
              <p className="text-xs text-gray-500">计算板块表现中...</p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function IndexCard({ title, data, isLoading, gradientFrom, gradientTo }: { title: string; data: any; isLoading: boolean; gradientFrom: string; gradientTo: string }) {
  const changePercent = data?.change_percent ?? 0;
  const changeValue = data?.current_price && data?.yesterday_close ? data.current_price - data.yesterday_close : 0;
  const isUp = changePercent >= 0;
  return (
    <div className={`bg-gradient-to-r ${gradientFrom} ${gradientTo} rounded-xl shadow-lg p-6 text-white transition-transform hover:scale-105`}>
      <h3 className="text-lg font-semibold mb-4 opacity-90">{title}</h3>
      {isLoading ? (<div className="flex items-center justify-center py-8"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div></div>
      ) : data && data.current_price != null ? (
        <div>
          <div className={`text-3xl font-bold mb-2 ${isUp ? 'text-red-300' : 'text-green-300'}`}>{Number(data.current_price).toFixed(2)}</div>
          <div className="flex items-baseline gap-3 mb-3">
            <div className={`text-2xl font-bold ${isUp ? 'text-red-200' : 'text-green-200'}`}>{isUp ? '+' : ''}{changePercent.toFixed(2)}%</div>
            <div className={`text-lg font-semibold ${isUp ? 'text-red-200' : 'text-green-200'}`}>{isUp ? '+' : ''}{changeValue.toFixed(2)}</div>
          </div>
          <div className="grid grid-cols-2 gap-2 text-xs opacity-80 mt-4 pt-4 border-t border-white/20">
            <div><div className="opacity-70">最高</div><div className="font-semibold">{data.high?.toFixed(2) || '--'}</div></div>
            <div><div className="opacity-70">最低</div><div className="font-semibold">{data.low?.toFixed(2) || '--'}</div></div>
            <div className="col-span-2"><div className="opacity-70">成交量</div><div className="font-semibold">{data.volume ? (data.volume / 10000).toFixed(0) + '万手' : '--'}</div></div>
          </div>
        </div>
      ) : (<div className="text-red-200 text-sm">数据加载失败</div>)}
    </div>
  );
}

function StockCard({ code, name }: { code: string; name?: string }) {
  const { data, isLoading } = useQuery({queryKey: ['realtime', code], queryFn: () => stockAPI.getRealtime(code), refetchInterval: getRefetchInterval()});
  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-2">
        <Link to={`/stock/${code}`} className="flex-1">
          <div><h3 className="font-bold text-lg text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">{name || code}</h3><p className="text-sm text-gray-500 dark:text-gray-400">{code}</p></div>
        </Link>
      </div>
      {isLoading ? (<div className="text-gray-400">加载中...</div>
      ) : data ? (
        <div>
          <div className="text-2xl font-bold text-gray-900 dark:text-white mb-1">{/^\d{6}$/.test(code) ? '¥' : '$'}{data.current_price?.toFixed(2)}</div>
          <div className={`text-lg font-semibold mb-3 ${data.change_percent >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>{data.change_percent >= 0 ? '+' : ''}{data.change_percent?.toFixed(2)}%</div>
          <AIAnalyzeButton code={code} className="w-full text-sm" />
        </div>
      ) : (<div className="text-gray-400">数据获取失败</div>)}
    </div>
  );
}
