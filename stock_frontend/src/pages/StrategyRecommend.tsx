import { useQuery, useQueryClient } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import LoadingSpinner from '../components/LoadingSpinner';

interface StrategyStock {
  code: string;
  name?: string;
  price?: number;
  score: number;
  roe?: number; gross_margin?: number; ret_60d?: number; ret_20d?: number;
  break_pct?: number; vol_ratio?: number; rsi?: number; ma_spread?: number;
  t1_limit_time?: string; t2_limit_time?: string;
  consecutive_days?: number; break_count?: number; industry?: string;
  current_price?: number | null; change_percent?: number | null;
  volume?: number | null; amount?: number | null;
}

interface StrategyData {
  strategy: string; name: string; description: string;
  count: number; stocks: StrategyStock[]; error?: string;
}

interface RecommendationsResponse {
  strategies: StrategyData[]; timestamp: string;
}

interface StrongStocksResponse {
  strategy: string; description: string; params: { limit_time: string };
  trade_dates: { T: string; 'T-1': string; 'T-2': string };
  count: number; stocks: any[];
}

const TIME_OPTIONS = ['09:30','09:45','10:00','10:15','10:30','10:45','11:00','11:15','11:30','13:00','13:30','14:00','14:30','15:00'];

const STRATEGY_TABS = [
  { key: 'strong_stocks', label: '强势股接力', color: 'from-blue-500 to-blue-700', bg: 'bg-blue-600/50', icon: '🔥' },
  { key: 'tenbagger', label: '十倍潜力股', color: 'from-purple-500 to-purple-700', bg: 'bg-purple-600/50', icon: '💎' },
  { key: 'breakout', label: '突破形态', color: 'from-orange-500 to-orange-700', bg: 'bg-orange-600/50', icon: '🚀' },
];

export default function StrategyRecommend() {
  const [activeTab, setActiveTab] = useState('tenbagger');
  const [limitTime, setLimitTime] = useState('11:30');
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [showMultiModal, setShowMultiModal] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);
  const [multiMode, setMultiMode] = useState<'fast'|'balanced'|'deep'>('fast');
  const [multiError, setMultiError] = useState<string|null>(null);
  const [addingMap, setAddingMap] = useState<Record<string,boolean>>({});
  const [addedMap, setAddedMap] = useState<Record<string,boolean>>({});
  const [showPaperModal, setShowPaperModal] = useState(false);
  const [selectedPaperAccountId, setSelectedPaperAccountId] = useState<number|null>(null);
  const [paperTargetStock, setPaperTargetStock] = useState<{code:string;name:string;currentPrice:number|null}|null>(null);
  const [paperLoading, setPaperLoading] = useState(false);
  const [paperError, setPaperError] = useState<string|null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Strong stocks (real data from akshare)
  const { data: strongData, isLoading: strongLoading, error: strongError, refetch: strongRefetch, isFetching: strongFetching } = useQuery<StrongStocksResponse>({
    queryKey: ['strong-stocks', limitTime],
    queryFn: () => stockAPI.getStrongStocks(limitTime),
    enabled: activeTab === 'strong_stocks',
    refetchInterval: 60000,
  });

  // Tenbagger + Breakout
  const { data: recData, isLoading: recLoading, error: recError, refetch: recRefetch, isFetching: recFetching } = useQuery<RecommendationsResponse>({
    queryKey: ['strategy-recommendations'],
    queryFn: async () => {
      const r = await fetch(`${stockAPI.getBaseURL()}/api/strategy/recommendations`);
      if (!r.ok) throw new Error('Failed');
      return r.json();
    },
    enabled: activeTab !== 'strong_stocks',
    refetchInterval: 300000,
  });

  const { data: agents } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => stockAPI.getAgents(true),
    enabled: showMultiModal,
  });

  useEffect(() => {
    if (showMultiModal && agents?.length > 0 && selectedAgentIds.length === 0) {
      setSelectedAgentIds(agents.map(a => a.id));
    }
  }, [showMultiModal, agents, selectedAgentIds.length]);

  const { data: paperAccounts } = useQuery({
    queryKey: ['paper-accounts'],
    queryFn: async () => {
      const r = await fetch(`${stockAPI.getBaseURL()}/api/paper/accounts`);
      if (!r.ok) throw new Error('Failed');
      return (await r.json()).accounts as any[];
    },
    enabled: showPaperModal,
  });

  useEffect(() => {
    if (showPaperModal && paperAccounts?.length > 0 && !selectedPaperAccountId) {
      setSelectedPaperAccountId(paperAccounts[0].id);
    }
  }, [showPaperModal, paperAccounts, selectedPaperAccountId]);

  // Get active strategy data
  const activeStrategy = ((): StrategyData | null => {
    if (activeTab === 'strong_stocks' && strongData) {
      return {
        strategy: 'strong_stocks', name: '强势股接力',
        description: '前两日早盘涨停, 今日未涨停的接力候选',
        count: strongData.count || 0,
        stocks: (strongData.stocks || []).map((s: any) => ({
          code: s.code, name: s.name, price: s.current_price,
          score: (s.consecutive_days||0)*20 + (s.break_count||0)*10,
          t1_limit_time: s.t1_limit_time, t2_limit_time: s.t2_limit_time,
          consecutive_days: s.consecutive_days, break_count: s.break_count,
          industry: s.industry, current_price: s.current_price,
          change_percent: s.change_percent, volume: s.volume, amount: s.amount,
        })),
      };
    }
    if (recData) return recData.strategies.find(s => s.strategy === activeTab) || null;
    return null;
  })();

  const isLoading = activeTab === 'strong_stocks' ? strongLoading : recLoading;
  const isFetching = activeTab === 'strong_stocks' ? strongFetching : recFetching;
  const error = activeTab === 'strong_stocks' ? strongError : recError;
  const refetch = activeTab === 'strong_stocks' ? strongRefetch : recRefetch;
  const stocks = activeStrategy?.stocks || [];

  // Helpers
  const formatNumber = (n: number|null|undefined) => {
    if (n==null) return '-';
    if (n>=1e8) return (n/1e8).toFixed(2)+'亿';
    if (n>=1e4) return (n/1e4).toFixed(2)+'万';
    return n.toFixed(2);
  };
  const formatTime = (t: string|null|undefined) => {
    if (!t) return '-'; const s=String(t);
    if (s.includes(':')) return s;
    if (s.length===6) return `${s.slice(0,2)}:${s.slice(2,4)}:${s.slice(4,6)}`;
    if (s.length===5) return `0${s.slice(0,1)}:${s.slice(1,3)}:${s.slice(3,5)}`;
    return s;
  };
  const toggleSelect = (code: string) => setSelectedCodes(p => p.includes(code)?p.filter(c=>c!==code):[...p,code]);
  const handleAddWatchlist = async (code: string, name: string) => {
    if (addingMap[code]) return;
    setAddingMap(p=>({...p,[code]:true}));
    try { await stockAPI.addWatchlist(code, name); setAddedMap(p=>({...p,[code]:true})); }
    catch { alert('加入自选失败'); }
    finally { setAddingMap(p=>({...p,[code]:false})); }
  };
  const handleOpenMulti = () => {
    if (selectedCodes.length<2) { setMultiError('至少勾选2只'); return; }
    setMultiError(null); setShowMultiModal(true);
  };
  const handleStartMulti = async () => {
    if (selectedCodes.length<2) { setMultiError('至少勾选2只'); return; }
    if (selectedAgentIds.length<2) { setMultiError('至少2个Agent'); return; }
    try {
      const cfg={fast:{analysisRounds:1,debateRounds:1},balanced:{analysisRounds:2,debateRounds:1},deep:{analysisRounds:3,debateRounds:2}}[multiMode];
      const res = await stockAPI.startMultiSelectDebate(selectedCodes, selectedAgentIds, cfg.analysisRounds, cfg.debateRounds);
      setShowMultiModal(false);
      navigate(`/ai-debate?job_id=${res.job_id}&code=${selectedCodes.join(',')}`);
    } catch { setMultiError('启动失败'); }
  };
  const handleOpenPaper = (stock: StrategyStock) => {
    setPaperTargetStock({code:stock.code,name:stock.name||stock.code,currentPrice:stock.current_price??stock.price??null});
    setPaperError(null); setShowPaperModal(true);
  };
  const handleSubmitPaper = async () => {
    if (!paperTargetStock||!selectedPaperAccountId) { setPaperError('请选择账户'); return; }
    setPaperLoading(true);
    try {
      await stockAPI.batchCreatePlans(selectedPaperAccountId, paperTargetStock.code, paperTargetStock.name, paperTargetStock.currentPrice??undefined);
      setShowPaperModal(false);
      queryClient.invalidateQueries({queryKey:['paper-accounts']});
    } catch { setPaperError('创建失败'); }
    finally { setPaperLoading(false); }
  };

  const tab = STRATEGY_TABS.find(t=>t.key===activeTab) || STRATEGY_TABS[0];

  return (
    <div className="px-4 sm:px-6 lg:px-8">
      {/* Strategy tabs */}
      <div className="flex gap-2 mb-6">
        {STRATEGY_TABS.map(t => (
          <button key={t.key} onClick={()=>{setActiveTab(t.key);setSelectedCodes([]);}}
            className={`flex-1 py-3 px-4 rounded-xl text-sm font-bold transition-all ${
              activeTab===t.key
                ? `bg-gradient-to-r ${t.color} text-white shadow-lg scale-105`
                : 'bg-gray-100 dark:bg-gray-800 text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'
            }`}>
            {t.icon} {t.label}
          </button>
        ))}
      </div>

      {/* Strategy info card */}
      <div className={`bg-gradient-to-r ${tab.color} rounded-xl p-6 text-white shadow-lg mb-6`}>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold">{tab.icon} {tab.label}</h2>
            <p className="text-sm opacity-80 mt-1">{activeStrategy?.description || '加载中...'}</p>
          </div>
          <div className="text-right">
            <div className="text-4xl font-bold">{activeStrategy?.count ?? '-'}</div>
            <div className="text-sm opacity-80">符合条件</div>
          </div>
        </div>
        {activeTab === 'strong_stocks' && (
          <div className="mt-4 p-3 bg-white/10 rounded-lg flex items-center gap-3 text-sm">
            <span>涨停截止:</span>
            <select value={limitTime} onChange={e=>setLimitTime(e.target.value)}
              className="bg-white/20 border border-white/30 rounded px-2 py-1 text-white">
              {TIME_OPTIONS.map(t=><option key={t} value={t} className="text-gray-900">{t}</option>)}
            </select>
          </div>
        )}
      </div>

      {/* Warning */}
      <div className="mb-4 text-center">
        <p className="text-sm text-yellow-600 dark:text-yellow-400">⚠️ 固定策略筛选，仅供参考。不构成投资建议。</p>
      </div>

      {/* Toolbar */}
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-lg font-semibold text-gray-900 dark:text-white">筛选结果 ({stocks.length}只)</h2>
        <div className="flex items-center gap-3">
          {selectedCodes.length>=2 && (
            <button onClick={handleOpenMulti}
              className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 text-sm font-medium">
              多选一 AI分析 ({selectedCodes.length})
            </button>
          )}
          <button onClick={()=>refetch()} disabled={isFetching}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 text-sm disabled:opacity-50">
            {isFetching?'刷新中...':'刷新'}
          </button>
        </div>
      </div>

      {/* Content */}
      {isLoading ? (
        <div className="bg-white dark:bg-gray-800 rounded-lg p-12 flex justify-center">
          <LoadingSpinner text="加载中..." />
        </div>
      ) : error ? (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 rounded-lg p-4 text-red-600">
          加载失败: {String(error)}
          <button onClick={()=>refetch()} className="ml-3 underline">重试</button>
        </div>
      ) : stocks.length===0 ? (
        <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-lg border">
          <div className="text-4xl mb-3">📭</div>
          <p className="text-gray-500">当前暂无符合条件的股票</p>
          <p className="text-xs text-gray-400 mt-1">
            {activeTab==='strong_stocks'?'非交易时段可能无数据':activeTab==='breakout'?'下跌市中突破信号稀少':'数据加载中，请刷新'}
          </p>
        </div>
      ) : (
        <div className="bg-white dark:bg-gray-800 rounded-lg border shadow overflow-hidden">
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 dark:divide-gray-700">
              <thead className="bg-gray-50 dark:bg-gray-900">
                <tr>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">勾选</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">代码</th>
                  <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">名称</th>
                  {activeTab==='strong_stocks' && <>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">行业</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">T-1</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">T-2</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">连板</th>
                    <th className="px-3 py-3 text-left text-xs font-medium text-gray-500 uppercase">炸板</th>
                  </>}
                  {activeTab==='tenbagger' && <>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">评分</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">ROE</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">毛利</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">60日</th>
                  </>}
                  {activeTab==='breakout' && <>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">评分</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">突破%</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">量比</th>
                    <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">RSI</th>
                  </>}
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">现价</th>
                  <th className="px-3 py-3 text-right text-xs font-medium text-gray-500 uppercase">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-200 dark:divide-gray-700">
                {stocks.map((stock, idx) => (
                  <tr key={stock.code} className="hover:bg-gray-50 dark:hover:bg-gray-700/50">
                    <td className="px-3 py-3">
                      <input type="checkbox" checked={selectedCodes.includes(stock.code)}
                        onChange={()=>toggleSelect(stock.code)} className="rounded" />
                    </td>
                    <td className="px-3 py-3 text-sm font-mono font-medium text-gray-900 dark:text-white">
                      {stock.code}
                    </td>
                    <td className="px-3 py-3 text-sm text-gray-700 dark:text-gray-300">
                      {stock.name || '-'}
                    </td>
                    {activeTab==='strong_stocks' && <>
                      <td className="px-3 py-3 text-sm text-gray-500">{stock.industry||'-'}</td>
                      <td className="px-3 py-3 text-sm text-gray-500">{formatTime(stock.t1_limit_time)}</td>
                      <td className="px-3 py-3 text-sm text-gray-500">{formatTime(stock.t2_limit_time)}</td>
                      <td className="px-3 py-3 text-sm">{(stock.consecutive_days??0)>0?<span className="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-700">{stock.consecutive_days}连板</span>:'-'}</td>
                      <td className="px-3 py-3 text-sm">{(stock.break_count??0)>0?<span className="px-2 py-0.5 text-xs rounded-full bg-yellow-100 text-yellow-700">{stock.break_count}次</span>:'-'}</td>
                    </>}
                    {activeTab==='tenbagger' && <>
                      <td className="px-3 py-3 text-sm text-right"><span className={`font-bold ${stock.score>=80?'text-red-500':stock.score>=65?'text-orange-500':'text-gray-500'}`}>{stock.score}</span></td>
                      <td className="px-3 py-3 text-sm text-right">{stock.roe!=null?`${stock.roe}%`:'-'}</td>
                      <td className="px-3 py-3 text-sm text-right">{stock.gross_margin!=null?`${stock.gross_margin}%`:'-'}</td>
                      <td className="px-3 py-3 text-sm text-right"><span className={(stock.ret_60d??0)>=0?'text-red-500':'text-green-500'}>{(stock.ret_60d??0)>0?'+':''}{stock.ret_60d!=null?`${stock.ret_60d}%`:'-'}</span></td>
                    </>}
                    {activeTab==='breakout' && <>
                      <td className="px-3 py-3 text-sm text-right"><span className={`font-bold ${stock.score>=80?'text-red-500':stock.score>=65?'text-orange-500':'text-gray-500'}`}>{stock.score}</span></td>
                      <td className="px-3 py-3 text-sm text-right text-red-500">{stock.break_pct!=null?`${stock.break_pct}%`:'-'}</td>
                      <td className="px-3 py-3 text-sm text-right">{stock.vol_ratio!=null?`${stock.vol_ratio}x`:'-'}</td>
                      <td className="px-3 py-3 text-sm text-right">{stock.rsi!=null?stock.rsi:'-'}</td>
                    </>}
                    <td className="px-3 py-3 text-sm text-right font-medium">
                      {(stock.current_price??stock.price)!=null?`¥${(stock.current_price??stock.price)!.toFixed(2)}`:'-'}
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex gap-1">
                        <Link to={`/stock/${stock.code}`}
                          className="px-2 py-1 text-xs rounded bg-blue-600 text-white hover:bg-blue-700">详情</Link>
                        <button onClick={()=>handleAddWatchlist(stock.code, stock.name||stock.code)}
                          disabled={addingMap[stock.code]||addedMap[stock.code]}
                          className="px-2 py-1 text-xs rounded bg-emerald-600 text-white hover:bg-emerald-700 disabled:opacity-50">
                          {addedMap[stock.code]?'已加':addingMap[stock.code]?'...':'加自选'}
                        </button>
                        <button onClick={()=>handleOpenPaper(stock)}
                          className="px-2 py-1 text-xs rounded bg-orange-600 text-white hover:bg-orange-700">📋计划</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Multi-select modal */}
      {showMultiModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between p-4 border-b">
              <h2 className="text-lg font-bold">多选一 AI分析</h2>
              <button onClick={()=>{setShowMultiModal(false);setMultiError(null);}} className="text-gray-400 hover:text-gray-600 text-xl">&times;</button>
            </div>
            <div className="p-4 space-y-3 overflow-y-auto">
              <div className="text-sm text-gray-500">已选: {selectedCodes.join(', ')}</div>
              <div className="flex gap-2">
                {(['fast','balanced','deep'] as const).map(m=>(
                  <button key={m} onClick={()=>setMultiMode(m)}
                    className={`flex-1 py-2 rounded text-sm border ${multiMode===m?'border-purple-600 bg-purple-50 text-purple-700':'border-gray-200'}`}>
                    {m==='fast'?'快速(1+1)':m==='balanced'?'均衡(2+1)':'深入(3+2)'}
                  </button>
                ))}
              </div>
              {agents?.length>0 && (
                <div className="grid grid-cols-2 gap-1">
                  {agents.map((a:any)=>(<label key={a.id} className="flex items-center gap-1 text-sm p-1"><input type="checkbox" checked={selectedAgentIds.includes(a.id)} onChange={()=>setSelectedAgentIds(p=>p.includes(a.id)?p.filter(i=>i!==a.id):[...p,a.id])} />{a.name}</label>))}
                </div>
              )}
              {multiError && <div className="text-red-500 text-sm">{multiError}</div>}
              <button onClick={handleStartMulti} className="w-full py-2 bg-purple-600 text-white rounded font-medium hover:bg-purple-700">启动分析</button>
            </div>
          </div>
        </div>
      )}

      {/* Paper modal */}
      {showPaperModal && paperTargetStock && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-sm w-full p-4 space-y-3">
            <h2 className="font-bold">添加模拟盘计划 - {paperTargetStock.name}</h2>
            <div className="text-sm text-gray-500">现价: ¥{paperTargetStock.currentPrice?.toFixed(2)||'未知'}</div>
            <select value={selectedPaperAccountId??''} onChange={e=>setSelectedPaperAccountId(Number(e.target.value))}
              className="w-full border rounded px-3 py-2 text-sm dark:bg-gray-700">
              <option value="">选择账户</option>
              {paperAccounts?.map((a:any)=><option key={a.id} value={a.id}>{a.name}</option>)}
            </select>
            {paperError && <div className="text-red-500 text-sm">{paperError}</div>}
            <div className="flex gap-2">
              <button onClick={()=>setShowPaperModal(false)} className="flex-1 py-2 border rounded text-sm">取消</button>
              <button onClick={handleSubmitPaper} disabled={paperLoading}
                className="flex-1 py-2 bg-orange-600 text-white rounded text-sm hover:bg-orange-700 disabled:opacity-50">
                {paperLoading?'创建中...':'创建计划'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
