import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useWatchlistStore } from '../store/watchlistStore';
import { stockAPI } from '../services/api';
import AIAnalyzeButton from '../components/AIAnalyzeButton';
import type { Agent } from '../services/api';

// 判断是否在交易时间
function isTradingTime(): boolean {
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay(); // 0=周日, 6=周六
  
  // 周末不交易
  if (day === 0 || day === 6) return false;
  
  // 交易时间：9:30-11:30, 13:00-15:00
  const morningStart = hour === 9 && minute >= 30 || hour > 9 && hour < 11 || hour === 11 && minute <= 30;
  const afternoonStart = hour >= 13 && hour < 15;
  
  return morningStart || afternoonStart;
}

// 根据交易时间返回更新间隔（毫秒）
function getRefetchInterval(): number {
  return isTradingTime() ? 5000 : 60000; // 交易时间5秒，非交易时间60秒
}

export default function Watchlist() {
  const { items, loading, addStock, removeStock, error: storeError } = useWatchlistStore();
  const [codeInput, setCodeInput] = useState('');
  const [costInput, setCostInput] = useState('');
  const [sharesInput, setSharesInput] = useState('');
  const [showPositionFields, setShowPositionFields] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editPosition, setEditPosition] = useState<string | null>(null);
  const [editCost, setEditCost] = useState('');
  const [editShares, setEditShares] = useState('');
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [showMultiModal, setShowMultiModal] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);
  const [multiMode, setMultiMode] = useState<'fast' | 'balanced' | 'deep'>('fast');
  const [multiError, setMultiError] = useState<string | null>(null);
  const navigate = useNavigate();

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => stockAPI.getAgents(true),
    enabled: showMultiModal,
  });

  useEffect(() => {
    if (showMultiModal && agents && agents.length > 0 && selectedAgentIds.length === 0) {
      setSelectedAgentIds(agents.map((agent) => agent.id));
    }
  }, [showMultiModal, agents, selectedAgentIds.length]);

  const handleAdd = async () => {
    const code = codeInput.trim();
    if (!code) {
      alert('请输入股票代码（A股6位数字 或 美股ticker，如 AAPL）');
      return;
    }
    // 校验格式：6位数字(A股) 或 1-5位字母(美股)
    const isACode = /^\d{6}$/.test(code);
    const isUsCode = /^[A-Za-z]{1,5}$/.test(code);
    if (!isACode && !isUsCode) {
      alert('股票代码格式错误：A股输入6位数字(如 000001)，美股输入ticker(如 AAPL)');
      return;
    }

    setAdding(true);
    try {
      // 先获取股票名称
      const realtime = await stockAPI.getRealtime(code);
      const costPrice = costInput ? parseFloat(costInput) : null;
      const shares = sharesInput ? parseInt(sharesInput) : null;
      await addStock(code, realtime.name, costPrice, shares);
      setCodeInput('');
      setCostInput('');
      setSharesInput('');
      setShowPositionFields(false);
    } catch (error) {
      alert(`添加失败: ${(error as Error).message}`);
    } finally {
      setAdding(false);
    }
  };

  const toggleSelectCode = (code: string) => {
    setSelectedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleOpenMulti = () => {
    if (selectedCodes.length < 2) {
      setMultiError('请至少勾选2只股票');
      return;
    }
    setMultiError(null);
    setShowMultiModal(true);
  };

  const handleSavePosition = async (code: string) => {
    try {
      const costPrice = editCost ? parseFloat(editCost) : null;
      const shares = editShares ? parseInt(editShares) : null;
      await stockAPI.updateWatchlistPosition(code, costPrice, shares);
      setEditPosition(null);
      // Refresh the list
      useWatchlistStore.getState().fetchWatchlist();
    } catch (error) {
      alert(`更新失败: ${(error as Error).message}`);
    }
  };

  const handleStartMulti = async () => {
    if (selectedCodes.length < 2) {
      setMultiError('请至少勾选2只股票');
      return;
    }
    if (selectedAgentIds.length < 2) {
      setMultiError('至少选择2个Agent参与辩论');
      return;
    }
    setMultiError(null);
    try {
      const modeConfig = {
        fast: { analysisRounds: 1, debateRounds: 1 },
        balanced: { analysisRounds: 2, debateRounds: 1 },
        deep: { analysisRounds: 3, debateRounds: 2 },
      }[multiMode];
      const res = await stockAPI.startMultiSelectDebate(
        selectedCodes,
        selectedAgentIds,
        modeConfig.analysisRounds,
        modeConfig.debateRounds
      );
      setShowMultiModal(false);
      const params = new URLSearchParams();
      params.set('job_id', res.job_id);
      params.set('code', selectedCodes.join(','));
      navigate(`/ai-debate?${params.toString()}`);
    } catch (e) {
      console.error('多选一任务启动失败:', e);
      setMultiError('启动多选一任务失败，请稍后重试');
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-white">自选股管理</h1>
        {selectedCodes.length >= 2 && (
          <button
            onClick={handleOpenMulti}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            多选一 AI分析
          </button>
        )}
      </div>

      {/* 添加自选股 */}
      {storeError && (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-red-700 dark:text-red-400 text-sm">
          ❌ {storeError}
        </div>
      )}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">添加自选股</h2>
        <div className="flex flex-col gap-3">
          <div className="flex gap-2">
            <input
              type="text"
              value={codeInput}
              onChange={(e) => setCodeInput(e.target.value)}
              placeholder="股票代码（A股6位数字 或 美股ticker，如 000001 / AAPL）"
              className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white"
              maxLength={10}
            />
            <button
              onClick={handleAdd}
              disabled={adding}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {adding ? '添加中...' : '添加'}
            </button>
          </div>
          <div className="flex items-center gap-2">
            <label className="flex items-center gap-2 text-sm text-gray-600 dark:text-gray-400 cursor-pointer">
              <input
                type="checkbox"
                checked={showPositionFields}
                onChange={(e) => setShowPositionFields(e.target.checked)}
                className="rounded"
              />
              添加持仓信息
            </label>
          </div>
          {showPositionFields && (
            <div className="flex gap-3">
              <input
                type="number"
                value={costInput}
                onChange={(e) => setCostInput(e.target.value)}
                placeholder="持仓成本价（元）"
                step="0.01"
                className="w-48 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
              <input
                type="number"
                value={sharesInput}
                onChange={(e) => setSharesInput(e.target.value)}
                placeholder="持股数量（股）"
                step="100"
                className="w-48 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
            </div>
          )}
        </div>
      </div>

      {/* 自选股列表 */}
      <div className="bg-white dark:bg-gray-800 rounded-lg shadow">
        <div className="p-6">
          <h2 className="text-xl font-semibold mb-4 text-gray-900 dark:text-white">我的自选</h2>
          {loading ? (
            <div className="text-center py-8 text-gray-500">加载中...</div>
          ) : items.length === 0 ? (
            <div className="text-center py-8 text-gray-500">暂无自选股</div>
          ) : (
            <div className="space-y-2">
              {items.map((item) => (
                <WatchlistItem
                  key={item.id}
                  item={item}
                  onRemove={() => removeStock(item.code)}
                  selected={selectedCodes.includes(item.code)}
                  onToggleSelect={() => toggleSelectCode(item.code)}
                  editPosition={editPosition}
                  editCost={editCost}
                  editShares={editShares}
                  setEditPosition={setEditPosition}
                  setEditCost={setEditCost}
                  setEditShares={setEditShares}
                  onSavePosition={handleSavePosition}
                />
              ))}
            </div>
          )}
        </div>
      </div>

      {/* 多选一 模态 */}
      {showMultiModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl max-w-2xl w-full max-h-[90vh] overflow-hidden flex flex-col">
            <div className="flex items-center justify-between p-6 border-b border-gray-200 dark:border-gray-700">
              <h2 className="text-xl font-bold text-gray-900 dark:text-white">多选一 AI分析</h2>
              <button
                onClick={() => {
                  setShowMultiModal(false);
                  setMultiError(null);
                }}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              <div className="text-sm text-gray-600 dark:text-gray-400">
                本模式要求从所选股票中<strong>必须选择一只</strong>进行买入决策。
              </div>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  选择模式
                </label>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2">
                  <button
                    onClick={() => setMultiMode('fast')}
                    className={`px-3 py-2 rounded-lg text-sm border ${
                      multiMode === 'fast'
                        ? 'border-purple-600 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                        : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'
                    }`}
                  >
                    快速模式
                    <div className="text-xs opacity-70">思考1 / 辩论1</div>
                  </button>
                  <button
                    onClick={() => setMultiMode('balanced')}
                    className={`px-3 py-2 rounded-lg text-sm border ${
                      multiMode === 'balanced'
                        ? 'border-purple-600 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                        : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'
                    }`}
                  >
                    均衡模式
                    <div className="text-xs opacity-70">思考2 / 辩论1</div>
                  </button>
                  <button
                    onClick={() => setMultiMode('deep')}
                    className={`px-3 py-2 rounded-lg text-sm border ${
                      multiMode === 'deep'
                        ? 'border-purple-600 bg-purple-50 dark:bg-purple-900/30 text-purple-700 dark:text-purple-300'
                        : 'border-gray-200 dark:border-gray-700 text-gray-600 dark:text-gray-300'
                    }`}
                  >
                    深入模式
                    <div className="text-xs opacity-70">思考3 / 辩论2</div>
                  </button>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                  选择参与辩论的Agent（至少2个）
                </label>
                {agentsLoading ? (
                  <div className="text-gray-500">加载中...</div>
                ) : agents && agents.length > 0 ? (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                    {agents.map((agent: Agent) => (
                      <label
                        key={agent.id}
                        className="flex items-center gap-2 p-2 border border-gray-200 dark:border-gray-700 rounded-lg cursor-pointer hover:bg-gray-50 dark:hover:bg-gray-700"
                      >
                        <input
                          type="checkbox"
                          checked={selectedAgentIds.includes(agent.id)}
                          onChange={() =>
                            setSelectedAgentIds((prev) =>
                              prev.includes(agent.id) ? prev.filter((id) => id !== agent.id) : [...prev, agent.id]
                            )
                          }
                          className="rounded"
                        />
                        <span className="text-sm text-gray-900 dark:text-white">
                          {agent.name} ({agent.type})
                        </span>
                      </label>
                    ))}
                  </div>
                ) : (
                  <div className="text-gray-500">暂无启用的Agent，请先在配置页面添加</div>
                )}
              </div>

              {multiError && (
                <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-3 text-red-700 dark:text-red-400 text-sm">
                  {multiError}
                </div>
              )}

              <button
                onClick={handleStartMulti}
                className="w-full px-6 py-3 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition-all font-semibold"
              >
                启动多选一分析
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function WatchlistItem({
  item,
  onRemove,
  selected,
  onToggleSelect,
  editPosition,
  editCost,
  editShares,
  setEditPosition,
  setEditCost,
  setEditShares,
  onSavePosition,
}: {
  item: any;
  onRemove: () => void;
  selected: boolean;
  onToggleSelect: () => void;
  editPosition: string | null;
  editCost: string;
  editShares: string;
  setEditPosition: (code: string | null) => void;
  setEditCost: (val: string) => void;
  setEditShares: (val: string) => void;
  onSavePosition: (code: string) => void;
}) {
  // 获取实时行情数据
  const { data: realtimeData, isLoading } = useQuery({
    queryKey: ['realtime', item.code],
    queryFn: () => stockAPI.getRealtime(item.code),
    refetchInterval: getRefetchInterval(),
    enabled: !!item.code,
  });

  const changePercent = (realtimeData?.current_price && realtimeData?.current_price > 0 && realtimeData?.change_percent != null)
    ? realtimeData.change_percent : 0;
  const changeValue = realtimeData?.current_price && realtimeData?.current_price > 0 && realtimeData?.yesterday_close
    ? realtimeData.current_price - realtimeData.yesterday_close
    : 0;
  const isUp = changePercent >= 0;

  // 计算持仓盈亏
  const costPrice = item.cost_price;
  const shares = item.shares;
  const hasPosition = costPrice != null && shares != null && shares > 0;
  const positionValue = hasPosition ? (realtimeData?.current_price ?? 0) * shares! : 0;
  const positionCost = hasPosition ? costPrice! * shares! : 0;
  const positionPnl = positionValue - positionCost;
  const positionPnlPercent = costPrice && costPrice > 0 ? ((realtimeData?.current_price ?? 0) - costPrice) / costPrice * 100 : 0;

  return (
    <div className="flex items-center justify-between p-4 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors">
      <div className="mr-3">
        <input
          type="checkbox"
          checked={selected}
          onChange={(e) => {
            e.stopPropagation();
            onToggleSelect();
          }}
          className="rounded"
        />
      </div>
      <Link to={`/stock/${item.code}`} className="flex-1 flex items-center justify-between">
        <div className="flex-1">
          <div className="font-semibold text-gray-900 dark:text-white hover:text-blue-600 dark:hover:text-blue-400">
            {item.name || item.code}
          </div>
          <div className="text-sm text-gray-500 dark:text-gray-400">{item.code}</div>
          {hasPosition && (
            <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
              成本{costPrice!.toFixed(2)} × {shares!.toLocaleString()}股
            </div>
          )}
        </div>

        {/* 实时行情信息 */}
        {isLoading ? (
          <div className="text-gray-400 text-sm">加载中...</div>
        ) : realtimeData && realtimeData.current_price != null && realtimeData.current_price > 0 ? (
          <div className="flex items-center gap-6 text-right">
            {hasPosition && (
              <div className="text-right">
                <div className={`text-sm font-bold ${positionPnl >= 0 ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                  {positionPnl >= 0 ? '+' : ''}{positionPnl.toFixed(2)}
                </div>
                <div className={`text-xs ${positionPnlPercent >= 0 ? 'text-red-500 dark:text-red-500' : 'text-green-500 dark:text-green-500'}`}>
                  {positionPnlPercent >= 0 ? '+' : ''}{positionPnlPercent.toFixed(2)}%
                </div>
              </div>
            )}
            <div>
              <div className={`text-lg font-bold ${isUp ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {realtimeData.current_price != null && realtimeData.current_price > 0 ? realtimeData.current_price.toFixed(2) : '--'}
              </div>
            </div>
            <div>
              <div className={`text-sm font-semibold ${isUp ? 'text-red-600 dark:text-red-400' : 'text-green-600 dark:text-green-400'}`}>
                {isUp ? '+' : ''}{changePercent.toFixed(2)}%
              </div>
              <div className={`text-xs ${isUp ? 'text-red-500 dark:text-red-500' : 'text-green-500 dark:text-green-500'}`}>
                {isUp ? '+' : ''}{changeValue.toFixed(2)}
              </div>
            </div>
          </div>
        ) : (
          <div className="text-gray-400 text-sm">--</div>
        )}
      </Link>

      <div className="ml-4 flex items-center gap-2">
        <AIAnalyzeButton code={item.code} className="text-sm px-3 py-1.5" />
        {!hasPosition ? (
          <button
            onClick={(e) => {
              e.preventDefault();
              setEditPosition(item.code);
              setEditCost('');
              setEditShares('');
            }}
            className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            设置持仓
          </button>
        ) : (
          <button
            onClick={(e) => {
              e.preventDefault();
              setEditPosition(item.code);
              setEditCost(item.cost_price?.toString() || '');
              setEditShares(item.shares?.toString() || '');
            }}
            className="px-3 py-1.5 text-xs text-gray-600 hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-700 rounded-lg transition-colors"
          >
            编辑持仓
          </button>
        )}
        <button
          onClick={(e) => {
            e.preventDefault();
            onRemove();
          }}
          className="px-4 py-2 text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 rounded-lg transition-colors"
        >
          删除
        </button>
      </div>

      {/* 持仓编辑弹窗 */}
      {editPosition === item.code && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4" onClick={() => setEditPosition(null)}>
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-xl p-6 max-w-sm w-full" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-lg font-semibold mb-4 text-gray-900 dark:text-white">编辑持仓 - {item.name || item.code}</h3>
            <div className="space-y-3">
              <input
                type="number"
                value={editCost}
                onChange={(e) => setEditCost(e.target.value)}
                placeholder="持仓成本价（元）"
                step="0.01"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
              <input
                type="number"
                value={editShares}
                onChange={(e) => setEditShares(e.target.value)}
                placeholder="持股数量（股）"
                step="100"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
              <div className="flex gap-2 pt-2">
                <button
                  onClick={() => setEditPosition(null)}
                  className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 text-gray-700 dark:text-gray-300 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700"
                >
                  取消
                </button>
                <button
                  onClick={() => onSavePosition(item.code)}
                  className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  保存
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

