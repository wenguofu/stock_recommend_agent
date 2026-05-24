import React from 'react';

interface MLData {
  success?: boolean;
  horizon_days?: number;
  confidence?: string;
  direction?: string;
  up_prob?: number;
  down_prob?: number;
  predicted_return_pct?: number;
  return_range?: string;
  key_factors?: string[];
}

interface Props {
  mlData: MLData;
}

export default function MLPredictPanel({ mlData }: Props) {
  if (!mlData?.success) return null;

  const confLabel = mlData.confidence === 'high' ? '高' : mlData.confidence === 'medium' ? '中' : '低';
  const confColor = mlData.confidence === 'high'
    ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
    : mlData.confidence === 'medium'
      ? 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300'
      : 'bg-gray-100 text-gray-700';

  const dirLabel = mlData.direction === 'up' ? '📈 看涨' : mlData.direction === 'down' ? '📉 看跌' : '➡️ 中性';
  const dirColor = mlData.direction === 'up' ? 'text-red-500' : mlData.direction === 'down' ? 'text-green-500' : 'text-gray-500';
  const retColor = (mlData.predicted_return_pct ?? 0) >= 0 ? 'text-red-500' : 'text-green-500';

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-l-4 border-purple-500">
      <div className="flex items-center gap-2 mb-3">
        <h3 className="text-sm font-semibold text-gray-900 dark:text-white">
          🤖 ML预测 (未来{mlData.horizon_days}日)
        </h3>
        <span className={`px-2 py-0.5 rounded text-xs font-medium ${confColor}`}>
          置信度: {confLabel}
        </span>
      </div>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">方向预测</div>
          <div className={`text-lg font-bold ${dirColor}`}>{dirLabel}</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">上涨概率</div>
          <div className="font-semibold text-red-500">{mlData.up_prob}%</div>
        </div>
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">预测收益率</div>
          <div className={`font-semibold ${retColor}`}>
            {mlData.predicted_return_pct != null
              ? `${mlData.predicted_return_pct > 0 ? '+' : ''}${mlData.predicted_return_pct}%`
              : 'N/A'}
          </div>
        </div>
        {mlData.return_range && (
          <div>
            <div className="text-xs text-gray-500 dark:text-gray-400">收益区间</div>
            <div className="font-semibold text-gray-900 dark:text-white">{mlData.return_range}</div>
          </div>
        )}
      </div>
      {mlData.key_factors && mlData.key_factors.length > 0 && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
          <span className="text-xs text-gray-500 dark:text-gray-400">驱动因子: </span>
          <span className="text-xs text-gray-700 dark:text-gray-300">
            {mlData.key_factors.join(', ')}
          </span>
        </div>
      )}
    </div>
  );
}
