import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { stockAPI, type StrategyDetail, type WatchlistItem, type DebateStep } from '../services/api';
import ApplyToPaperPanel from '../components/ApplyToPaperPanel';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

type Stage = 'select' | 'running' | 'done';
type Mode = 'fast' | 'balanced' | 'deep';

const MODE_CONFIG: Record<Mode, { analysisRounds: number; debateRounds: number; label: string }> = {
  fast: { analysisRounds: 1, debateRounds: 0, label: '快速模式' },
  balanced: { analysisRounds: 2, debateRounds: 1, label: '均衡模式' },
  deep: { analysisRounds: 3, debateRounds: 2, label: '深入模式' },
};

export default function StrategyRun() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const strategyId = parseInt(id || '0');

  const [stage, setStage] = useState<Stage>('select');
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [manualCode, setManualCode] = useState('');
  const [mode, setMode] = useState<Mode>('balanced');
  const [jobId, setJobId] = useState('');
  const [jobName, setJobName] = useState('');
  const [error, setError] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<string>('');

  // 加载策略详情
  const { data: strategy, isLoading: strategyLoading } = useQuery<StrategyDetail>({
    queryKey: ['strategy-run', strategyId],
    queryFn: () => stockAPI.getStrategyDetail(strategyId),
    enabled: !!strategyId,
  });

  // 加载自选股
  const { data: watchlist } = useQuery<WatchlistItem[]>({
    queryKey: ['watchlist'],
    queryFn: () => stockAPI.getWatchlist(),
  });

  // 加载板块列表
  const { data: sectors = [] } = useQuery<string[]>({
    queryKey: ['sectors'],
    queryFn: () => stockAPI.listSectors(),
  });

  const addSector = async (sector: string) => {
    if (selectedSectors.includes(sector)) return;
    setSelectedSectors((prev) => [...prev, sector]);
    const stocks = await stockAPI.getSectorStocks(sector);
    const codes = stocks.map((s) => s.code).filter((c) => !selectedCodes.includes(c));
    setSelectedCodes((prev) => [...prev, ...codes]);
  };

  const removeSector = (sector: string) => {
    setSelectedSectors((prev) => prev.filter((s) => s !== sector));
    // 移除该板块的所有股票（但保留手动添加的）
    stockAPI.getSectorStocks(sector).then((stocks) => {
      const sectorCodes = stocks.map((s) => s.code);
      setSelectedCodes((prev) => prev.filter((c) => !sectorCodes.includes(c)));
    });
  };

  // 轮询任务状态
  const { data: jobStatus } = useQuery({
    queryKey: ['strategy-run-status', jobId],
    queryFn: () => stockAPI.getDebateJobStatus(jobId),
    enabled: !!jobId && stage === 'running',
    refetchInterval: 2000,
  });

  // 任务完成时自动切换状态
  useEffect(() => {
    if (!jobStatus) return;
    if (jobStatus.status === 'completed' || jobStatus.status === 'failed' || jobStatus.status === 'canceled') {
      setStage('done');
    }
  }, [jobStatus]);

  // 自动应用策略Agent
  useEffect(() => {
    if (strategy && !applying && applyResult === '') {
      setApplying(true);
      stockAPI.applyStrategy(strategyId)
        .then((res) => setApplyResult(`已就绪 (${res.count}个Agent)`))
        .catch(() => setApplyResult('Agent就绪'))
        .finally(() => setApplying(false));
    }
  }, [strategy, strategyId, applying, applyResult]);

  const toggleCode = (code: string) => {
    setSelectedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const addManualCode = () => {
    const c = manualCode.trim();
    if (c && !selectedCodes.includes(c)) {
      setSelectedCodes((prev) => [...prev, c]);
    }
    setManualCode('');
  };

  const removeCode = (code: string) => {
    setSelectedCodes((prev) => prev.filter((c) => c !== code));
  };

  const handleStart = async () => {
    if (selectedCodes.length === 0) {
      setError('请至少选择1只股票');
      return;
    }
    setError('');
    setStage('running');

    try {
      const config = MODE_CONFIG[mode];
      const res = await stockAPI.runStrategy(strategyId, selectedCodes, config.analysisRounds, config.debateRounds);
      setJobId(res.data.job_id);
      setJobName(res.data.name);
    } catch (e: any) {
      setError(`启动失败: ${e.message}`);
      setStage('select');
    }
  };

  // 渲染Markdown报告
  const reportHtml = useMemo(() => {
    if (!jobStatus?.report_md) return '';
    const raw = marked.parse(jobStatus.report_md, { gfm: true, breaks: true });
    return DOMPurify.sanitize(raw as string);
  }, [jobStatus?.report_md]);

  const steps = jobStatus?.steps || [];
  const groupedSteps = useMemo(() => {
    const map = new Map<number, { agent_id: number; agent_name: string; items: DebateStep[] }>();
    steps.forEach((step) => {
      if (!map.has(step.agent_id)) {
        map.set(step.agent_id, { agent_id: step.agent_id, agent_name: step.agent_name, items: [] });
      }
      map.get(step.agent_id)?.items.push(step);
    });
    return Array.from(map.values());
  }, [steps]);

  if (strategyLoading || !strategy) {
    return (
      <div className="flex items-center justify-center py-20">
        <div className="text-center">
          <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-500">加载策略...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* 策略信息头部 */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 rounded-xl p-6 text-white shadow-lg">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">{strategy.name}</h1>
            <p className="mt-1 text-blue-100">{strategy.description?.slice(0, 120)}</p>
            <div className="mt-3 flex items-center gap-3 text-sm">
              <span className="px-2 py-1 bg-white/20 rounded-full">{strategy.agent_configs.length}个Agent</span>
              <span className="px-2 py-1 bg-white/20 rounded-full">
                {applyResult ? (applying ? '准备Agent中...' : applyResult) : '加载中...'}
              </span>
              {jobName && <span className="px-2 py-1 bg-green-400/30 rounded-full">运行中</span>}
            </div>
          </div>
        </div>
      </div>

      {stage === 'select' && (
        <>
          {/* 模式选择 */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">分析模式</h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
              {(['fast', 'balanced', 'deep'] as Mode[]).map((m) => {
                const cfg = MODE_CONFIG[m];
                return (
                  <button
                    key={m}
                    onClick={() => setMode(m)}
                    className={`p-4 rounded-lg text-left border-2 transition-all ${
                      mode === m
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-blue-300'
                    }`}
                  >
                    <div className="font-semibold text-gray-900 dark:text-white">{cfg.label}</div>
                    <div className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                      {cfg.analysisRounds}轮分析{cfg.debateRounds > 0 ? ` + ${cfg.debateRounds}轮辩论` : '（无辩论）'}
                    </div>
                  </button>
                );
              })}
            </div>
          </div>

          {/* 选股 */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-lg font-semibold text-gray-900 dark:text-white">选择股票</h2>
              <span className="text-sm text-gray-500">已选 {selectedCodes.length} 只</span>
            </div>

            {/* 按板块添加 */}
            <div className="mb-4 p-3 bg-blue-50 dark:bg-blue-900/10 rounded-lg border border-blue-200 dark:border-blue-800">
              <label className="block text-sm font-medium text-blue-700 dark:text-blue-300 mb-2">📂 按板块批量添加</label>
              <div className="flex gap-2 mb-2">
                <select
                  id="sector-select"
                  className="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-lg dark:bg-gray-700 dark:text-white text-sm"
                  value=""
                  onChange={(e) => { if (e.target.value) addSector(e.target.value); e.target.value = ''; }}
                >
                  <option value="">-- 选择板块 --</option>
                  {sectors.map((s) => (
                    <option key={s} value={s} disabled={selectedSectors.includes(s)}>{s}</option>
                  ))}
                </select>
              </div>
              {/* 已选板块标签 */}
              {selectedSectors.length > 0 && (
                <div className="flex flex-wrap gap-1.5 mt-2">
                  {selectedSectors.map((s) => (
                    <span key={s} className="inline-flex items-center gap-1 px-2 py-0.5 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded text-xs">
                      📁 {s}
                      <button onClick={() => removeSector(s)} className="hover:text-red-500">✕</button>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* 手动输入 */}
            <div className="flex gap-2 mb-4">
              <input
                type="text"
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addManualCode()}
                placeholder="输入股票代码（如 603290）"
                className="flex-1 px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
              />
              <button
                onClick={addManualCode}
                disabled={!manualCode.trim()}
                className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                添加
              </button>
            </div>

            {/* 已选股票标签 */}
            {selectedCodes.length > 0 && (
              <div className="flex flex-wrap gap-2 mb-4">
                {selectedCodes.map((code) => (
                  <span key={code} className="inline-flex items-center gap-1 px-3 py-1 bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded-full text-sm">
                    {code}
                    <button onClick={() => removeCode(code)} className="ml-1 hover:text-red-500">✕</button>
                  </span>
                ))}
              </div>
            )}

            {/* 自选股列表 */}
            <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">自选股</h3>
            {watchlist && watchlist.length > 0 ? (
              <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-2">
                {watchlist.map((item) => (
                  <button
                    key={item.code}
                    onClick={() => toggleCode(item.code)}
                    className={`flex items-center gap-2 p-2 rounded-lg border text-sm transition-all ${
                      selectedCodes.includes(item.code)
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 text-blue-700 dark:text-blue-400'
                        : 'border-gray-200 dark:border-gray-700 hover:border-blue-300 text-gray-700 dark:text-gray-300'
                    }`}
                  >
                    <span className="w-2 h-2 rounded-full flex-shrink-0 ${selectedCodes.includes(item.code) ? 'bg-blue-500' : 'bg-gray-300'}"></span>
                    <div className="text-left min-w-0">
                      <div className="font-medium truncate">{item.name}</div>
                      <div className="text-xs opacity-60">{item.code}</div>
                    </div>
                  </button>
                ))}
              </div>
            ) : (
              <div className="text-gray-400 text-sm text-center py-4">暂无自选股，请先在自选页面添加</div>
            )}
          </div>

          {/* Agent列表预览 */}
          <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
            <h2 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">参与Agent（{strategy.agent_configs.length}个）</h2>
            <div className="flex flex-wrap gap-2">
              {strategy.agent_configs.map((a, i) => (
                <span key={i} className="px-3 py-1.5 bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-full text-sm border border-gray-200 dark:border-gray-600">
                  {a.name}
                </span>
              ))}
            </div>
          </div>

          {/* 错误提示 */}
          {error && (
            <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-4 text-red-700 dark:text-red-400">
              {error}
            </div>
          )}

          {/* 启动按钮 */}
          <div className="flex justify-center">
            <button
              onClick={handleStart}
              disabled={selectedCodes.length === 0}
              className="flex items-center gap-3 px-10 py-4 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-xl text-lg font-semibold hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg transition-all"
            >
              <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              启动 {strategy.name} 分析
            </button>
          </div>
        </>
      )}

      {stage === 'running' && (
        <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
          <div className="text-center py-8">
            <div className="animate-spin h-12 w-12 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
            <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">
              {jobName || '分析进行中...'}
            </h3>
            <p className="text-gray-500 dark:text-gray-400 mb-2">
              进度：{jobStatus?.progress || 0}% | 状态：{jobStatus?.status || '排队中'}
            </p>
            <div className="w-full bg-gray-200 dark:bg-gray-700 rounded-full h-2 max-w-md mx-auto">
              <div
                className="bg-blue-600 h-2 rounded-full transition-all duration-500"
                style={{ width: `${jobStatus?.progress || 0}%` }}
              ></div>
            </div>
          </div>

          {/* Agent实时输出 */}
          {groupedSteps.length > 0 && (
            <div className="mt-4 space-y-3">
              <h4 className="font-semibold text-gray-900 dark:text-white">实时分析</h4>
              {groupedSteps.map((group) => (
                <details key={group.agent_id} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden" open>
                  <summary className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 cursor-pointer">
                    <span className="font-medium text-gray-900 dark:text-white">{group.agent_name}</span>
                    <span className="text-xs text-gray-500">{group.items.length}轮</span>
                  </summary>
                  <div className="p-3 space-y-2">
                    {group.items.map((step, i) => (
                      <div key={i} className="bg-gray-50 dark:bg-gray-900 p-3 rounded text-sm">
                        <div className="text-xs text-gray-400 mb-1">
                          第{step.round}轮 {step.phase === 'analysis' ? '分析' : '辩论'}
                        </div>
                        <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300 font-sans text-sm leading-relaxed">
                          {step.content.slice(0, 500)}{step.content.length > 500 ? '...' : ''}
                        </pre>
                      </div>
                    ))}
                  </div>
                </details>
              ))}
            </div>
          )}
        </div>
      )}

      {stage === 'done' && (
        <div className="space-y-6">
          {/* 完成状态 */}
          <div className={`rounded-lg p-6 ${jobStatus?.status === 'completed' ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800' : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'}`}>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                {jobStatus?.status === 'completed' ? (
                  <svg className="h-8 w-8 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                ) : (
                  <svg className="h-8 w-8 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                )}
                <div>
                  <h3 className="text-xl font-semibold text-gray-900 dark:text-white">
                    {jobStatus?.status === 'completed' ? '分析完成！' : '分析失败'}
                  </h3>
                  <p className="text-sm text-gray-500 dark:text-gray-400">{jobName}</p>
                </div>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => navigate(`/ai-debate?job_id=${jobId}&code=${selectedCodes.join(',')}`)}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  查看完整报告
                </button>
                <button
                  onClick={() => { setStage('select'); setJobId(''); setJobName(''); }}
                  className="px-4 py-2 bg-gray-200 dark:bg-gray-700 text-gray-900 dark:text-white rounded-lg hover:bg-gray-300 dark:hover:bg-gray-600"
                >
                  重新运行
                </button>
              </div>
            </div>
          </div>

          {/* 报告预览 */}
          {reportHtml && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 overflow-hidden">
              <div className="px-6 py-4 border-b border-gray-200 dark:border-gray-700 flex items-center justify-between">
                <h3 className="font-semibold text-gray-900 dark:text-white">分析报告</h3>
                <button
                  onClick={() => {
                    if (!jobStatus?.report_md) return;
                    const blob = new Blob([jobStatus.report_md], { type: 'text/markdown;charset=utf-8' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `strategy_report_${selectedCodes.join('_')}.md`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                  }}
                  className="px-3 py-1.5 text-sm bg-blue-600 text-white rounded hover:bg-blue-700"
                >
                  导出报告
                </button>
              </div>
              <div className="p-6 prose dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: reportHtml }} />
            </div>
          )}

          {/* 应用到模拟盘 */}
          {jobStatus?.status === 'completed' && (
            <ApplyToPaperPanel
              codes={selectedCodes}
              jobName={jobName}
              strategyRunId={jobId}
            />
          )}

          {/* 完整Agent输出 */}
          {groupedSteps.length > 0 && (
            <div className="bg-white dark:bg-gray-800 rounded-lg shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">完整Agent输出</h3>
              <div className="space-y-3">
                {groupedSteps.map((group) => (
                  <details key={group.agent_id} className="border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                    <summary className="flex items-center justify-between p-3 bg-gray-50 dark:bg-gray-900 cursor-pointer">
                      <span className="font-medium text-gray-900 dark:text-white">{group.agent_name}</span>
                      <span className="text-xs text-gray-500">{group.items.length}轮</span>
                    </summary>
                    <div className="p-3 space-y-2">
                      {group.items.map((step, i) => (
                        <div key={i} className="bg-gray-50 dark:bg-gray-900 p-4 rounded text-sm">
                          <div className="text-xs text-blue-500 font-medium mb-2">
                            {step.phase === 'analysis' ? '📝 分析' : '💬 辩论'} · 第{step.round}轮 · {new Date(step.timestamp).toLocaleTimeString()}
                          </div>
                          <pre className="whitespace-pre-wrap text-gray-700 dark:text-gray-300 font-sans text-sm leading-relaxed">{step.content}</pre>
                        </div>
                      ))}
                    </div>
                  </details>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}