import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import type { StrategySummary, StrategyDetail } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';

const CATEGORIES = [
  { value: '', label: '全部策略', icon: '📚' },
  { value: 'youzi', label: '游资策略', icon: '🐉' },
  { value: 'jichang', label: '基础工具', icon: '🔧' },
  { value: 'lianghua', label: '量化策略', icon: '📊' },
];

const CATEGORY_LABELS: Record<string, string> = {
  youzi: '游资策略',
  jichang: '基础工具',
  lianghua: '量化策略',
};

export default function StrategyLibrary() {
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyDetail | null>(null);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<{ message: string; count: number } | null>(null);
  const [expandedDoc, setExpandedDoc] = useState(false);
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['strategies', selectedCategory],
    queryFn: () => stockAPI.getStrategies(selectedCategory || undefined),
  });

  const handleSelect = async (id: number) => {
    try {
      const detail = await stockAPI.getStrategyDetail(id);
      setSelectedStrategy(detail);
      setExpandedDoc(false);
      setApplyResult(null);
    } catch (e) {
      console.error('获取策略详情失败:', e);
    }
  };

  const handleApply = async () => {
    if (!selectedStrategy) return;
    setApplying(true);
    try {
      const result = await stockAPI.applyStrategy(selectedStrategy.id);
      setApplyResult({ message: result.message, count: result.count });
    } catch (e) {
      console.error('应用策略失败:', e);
      setApplyResult({ message: '应用失败', count: 0 });
    } finally {
      setApplying(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold text-gray-900 dark:text-white">策略库</h1>
          <p className="text-gray-500 dark:text-gray-400 mt-1">浏览、选择并应用量化交易策略</p>
        </div>
        <button
          onClick={() => refetch()}
          className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
          刷新
        </button>
      </div>

      {/* 分类标签 */}
      <div className="flex flex-wrap gap-2">
        {CATEGORIES.map((cat) => (
          <button
            key={cat.value}
            onClick={() => {
              setSelectedCategory(cat.value);
              setSelectedStrategy(null);
              setApplyResult(null);
            }}
            className={`flex items-center gap-2 px-4 py-2 rounded-full text-sm font-medium transition-all ${
              selectedCategory === cat.value
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-white dark:bg-gray-800 text-gray-700 dark:text-gray-300 border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-700'
            }`}
          >
            <span>{cat.icon}</span>
            {cat.label}
          </button>
        ))}
      </div>

      {isLoading ? (
        <div className="text-center py-12">
          <div className="animate-spin h-10 w-10 border-4 border-blue-600 border-t-transparent rounded-full mx-auto mb-4"></div>
          <p className="text-gray-500 dark:text-gray-400">加载策略...</p>
        </div>
      ) : error ? (
        <div className="bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg p-6 text-center">
          <p className="text-red-600 dark:text-red-400">加载失败</p>
          <button onClick={() => refetch()} className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700">
            重试
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* 策略列表 */}
          <div className="lg:col-span-1 space-y-3">
            {data?.strategies.length === 0 ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-8 text-center">
                <p className="text-gray-500 dark:text-gray-400">暂无策略</p>
              </div>
            ) : (
              data?.strategies.map((s) => (
                <div
                  key={s.id}
                  onClick={() => handleSelect(s.id)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') handleSelect(s.id); }}
                  className={`w-full text-left p-4 rounded-lg border transition-all cursor-pointer ${
                    selectedStrategy?.id === s.id
                      ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/20 shadow-md'
                      : 'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 hover:shadow-md hover:border-blue-300'
                  }`}
                >
                  <div className="flex items-start justify-between">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-semibold text-gray-900 dark:text-white truncate">
                        {s.name}
                      </h3>
                      {s.category && (
                        <span className="inline-block mt-1 px-2 py-0.5 text-xs rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                          {CATEGORY_LABELS[s.category] || s.category}
                        </span>
                      )}
                    </div>
                    <div className="flex items-center gap-2 ml-2">
                      <button
                        onClick={(e) => { e.stopPropagation(); navigate(`/strategies/${s.id}/run`); }}
                        className="p-1.5 text-green-600 hover:bg-green-50 dark:hover:bg-green-900/20 rounded transition-colors"
                        title="立即运行"
                      >
                        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                        </svg>
                      </button>
                      <span className="px-2 py-1 text-xs font-medium bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 rounded-full whitespace-nowrap">
                        {s.agent_count}个Agent
                      </span>
                    </div>
                  </div>
                  {s.description && (
                    <p className="mt-2 text-sm text-gray-500 dark:text-gray-400 line-clamp-2">
                      {s.description}
                    </p>
                  )}
                </div>
              ))
            )}
          </div>

          {/* 策略详情 */}
          <div className="lg:col-span-2">
            {selectedStrategy ? (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 shadow-sm">
                {/* 标题栏 */}
                <div className="p-6 border-b border-gray-200 dark:border-gray-700">
                  <div className="flex items-start justify-between">
                    <div>
                      <h2 className="text-2xl font-bold text-gray-900 dark:text-white">
                        {selectedStrategy.name}
                      </h2>
                      {selectedStrategy.description && (
                        <p className="mt-2 text-gray-600 dark:text-gray-400">
                          {selectedStrategy.description}
                        </p>
                      )}
                    </div>
                    <button
                      onClick={handleApply}
                      disabled={applying}
                      className="flex items-center gap-2 px-6 py-3 bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg hover:from-blue-700 hover:to-purple-700 disabled:opacity-50 disabled:cursor-not-allowed shadow-lg transition-all"
                    >
                      {applying ? (
                        <>
                          <svg className="animate-spin h-5 w-5" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          应用中...
                        </>
                      ) : (
                        <>
                          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                          </svg>
                          应用配置
                        </>
                      )}
                    </button>
                    <button
                      onClick={() => navigate(`/strategies/${selectedStrategy.id}/run`)}
                      className="flex items-center gap-2 px-6 py-3 bg-green-600 text-white rounded-lg hover:bg-green-700 shadow-lg transition-all"
                    >
                      <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      </svg>
                      立即运行
                    </button>
                  </div>
                </div>

                {/* 应用结果 */}
                {applyResult && (
                  <div className={`mx-6 mt-4 p-4 rounded-lg ${
                    applyResult.count > 0
                      ? 'bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800'
                      : 'bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800'
                  }`}>
                    <div className="flex items-center gap-2">
                      {applyResult.count > 0 ? (
                        <svg className="h-5 w-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      ) : (
                        <svg className="h-5 w-5 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                        </svg>
                      )}
                      <span className={`text-sm font-medium ${
                        applyResult.count > 0 ? 'text-green-700 dark:text-green-400' : 'text-red-700 dark:text-red-400'
                      }`}>
                        {applyResult.count > 0
                          ? `✅ 策略应用成功！已创建/更新 ${applyResult.count} 个Agent。可到"设置"页面查看。`
                          : '❌ 策略应用失败'}
                      </span>
                    </div>
                  </div>
                )}

                {/* 包含的Agent列表 */}
                <div className="p-6">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white mb-4">
                    包含的Agent ({selectedStrategy.agent_configs.length}个)
                  </h3>
                  <div className="space-y-3">
                    {selectedStrategy.agent_configs.map((agent, idx) => (
                      <details key={idx} className="group border border-gray-200 dark:border-gray-700 rounded-lg overflow-hidden">
                        <summary className="flex items-center justify-between p-4 bg-gray-50 dark:bg-gray-900 cursor-pointer hover:bg-gray-100 dark:hover:bg-gray-750 transition-colors">
                          <div className="flex items-center gap-3">
                            <span className="flex items-center justify-center w-8 h-8 rounded-full bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400 text-sm font-bold">
                              {idx + 1}
                            </span>
                            <div>
                              <span className="font-medium text-gray-900 dark:text-white">{agent.name}</span>
                              <span className="ml-2 px-2 py-0.5 text-xs rounded bg-gray-200 dark:bg-gray-700 text-gray-600 dark:text-gray-400">
                                {agent.type}
                              </span>
                            </div>
                          </div>
                          <svg className="w-5 h-5 text-gray-400 group-open:rotate-180 transition-transform" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </summary>
                        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
                          <pre className="text-sm text-gray-600 dark:text-gray-400 whitespace-pre-wrap font-mono bg-gray-50 dark:bg-gray-900 p-4 rounded max-h-80 overflow-y-auto">
                            {agent.prompt}
                          </pre>
                        </div>
                      </details>
                    ))}
                  </div>
                </div>

                {/* 说明文档 */}
                {selectedStrategy.doc_md && (
                  <div className="p-6 border-t border-gray-200 dark:border-gray-700">
                    <button
                      onClick={() => setExpandedDoc(!expandedDoc)}
                      className="flex items-center gap-2 text-lg font-semibold text-gray-900 dark:text-white mb-2 w-full text-left"
                    >
                      <svg className={`w-5 h-5 transition-transform ${expandedDoc ? 'rotate-90' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
                      </svg>
                      策略说明文档
                    </button>
                    {expandedDoc && (
                      <div className="prose dark:prose-invert max-w-none text-sm text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-900 p-6 rounded-lg">
                        {selectedStrategy.doc_md.split('\n').map((line, i) => {
                          if (line.startsWith('# ')) return <h1 key={i} className="text-2xl font-bold text-gray-900 dark:text-white mt-4 mb-2">{line.slice(2)}</h1>;
                          if (line.startsWith('## ')) return <h2 key={i} className="text-xl font-semibold text-gray-900 dark:text-white mt-4 mb-2">{line.slice(3)}</h2>;
                          if (line.startsWith('### ')) return <h3 key={i} className="text-lg font-medium text-gray-900 dark:text-white mt-3 mb-1">{line.slice(4)}</h3>;
                          if (line.startsWith('| ')) return <div key={i} className="font-mono text-xs py-0.5">{line}</div>;
                          if (line.startsWith('> ')) return <blockquote key={i} className="border-l-4 border-blue-500 pl-4 italic my-2">{line.slice(2)}</blockquote>;
                          if (line.startsWith('- ')) return <li key={i} className="ml-4 list-disc text-sm">{line.slice(2)}</li>;
                          if (line.startsWith('---')) return <hr key={i} className="my-4 border-gray-300 dark:border-gray-700" />;
                          if (line.trim() === '') return <div key={i} className="h-2" />;
                          return <p key={i} className="text-sm leading-relaxed">{line}</p>;
                        })}
                      </div>
                    )}
                  </div>
                )}
              </div>
            ) : (
              <div className="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 p-12 text-center">
                <div className="text-6xl mb-4">📖</div>
                <h3 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">选择一个策略</h3>
                <p className="text-gray-500 dark:text-gray-400 max-w-md mx-auto">
                  从左侧选择一个策略，查看其包含的Agent配置和说明文档
                </p>
                <div className="mt-6 grid grid-cols-1 sm:grid-cols-3 gap-3 max-w-lg mx-auto">
                  <div className="p-3 rounded-lg bg-red-50 dark:bg-red-900/10 border border-red-100 dark:border-red-900/30">
                    <div className="text-2xl mb-1">🐉</div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300">游资策略</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">短线追涨打板</div>
                  </div>
                  <div className="p-3 rounded-lg bg-blue-50 dark:bg-blue-900/10 border border-blue-100 dark:border-blue-900/30">
                    <div className="text-2xl mb-1">🔧</div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300">基础工具</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">盯盘监控分析</div>
                  </div>
                  <div className="p-3 rounded-lg bg-green-50 dark:bg-green-900/10 border border-green-100 dark:border-green-900/30">
                    <div className="text-2xl mb-1">📊</div>
                    <div className="text-sm font-medium text-gray-700 dark:text-gray-300">量化策略</div>
                    <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">多因子评分</div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}