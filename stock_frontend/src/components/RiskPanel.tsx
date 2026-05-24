import React from 'react';

interface RiskData {
  risk_grade?: string;
  var_95?: { var_pct?: number };
  cvar_95?: { cvar_pct?: number };
  max_drawdown?: { max_drawdown_pct?: number };
  sharpe?: { sharpe_ratio?: number };
  volatility?: { annual_pct?: number };
  kelly_position?: { fractional_pct?: number; risk_level?: string };
  atr_stop_loss?: { stop_loss_price?: number };
  max_1d_loss_pct?: number;
  position_analysis?: {
    var_95_max_loss?: number;
    suggested_stop_loss?: number;
    stop_loss_pct?: number;
    kelly_suggested_pct?: number;
  };
}

interface Props {
  riskData: RiskData;
}

const GRADE_COLORS: Record<string, string> = {
  '低风险': 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300',
  '中等风险': 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900 dark:text-yellow-300',
  '高风险': 'bg-orange-100 text-orange-700 dark:bg-orange-900 dark:text-orange-300',
};

export default function RiskPanel({ riskData }: Props) {
  if (!riskData?.risk_grade || riskData.risk_grade === 'data_insufficient') return null;

  const gradeColor = GRADE_COLORS[riskData.risk_grade] || 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300';
  const sharpeVal = riskData.sharpe?.sharpe_ratio ?? 0;
  const sharpeColor = sharpeVal >= 1 ? 'text-green-600' : sharpeVal >= 0 ? 'text-yellow-600' : 'text-red-600';

  return (
    <div className="bg-white dark:bg-gray-800 rounded-lg shadow p-4 border-l-4 border-orange-500">
      <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-3">
        ⚠️ 风险指标
        <span className={`ml-2 px-2 py-0.5 rounded text-xs font-medium ${gradeColor}`}>
          {riskData.risk_grade}
        </span>
      </h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
        <Metric label="VaR (95%/日)" value={riskData.var_95?.var_pct != null ? `${riskData.var_95.var_pct}%` : null} />
        <Metric label="最大回撤" value={riskData.max_drawdown?.max_drawdown_pct != null ? `${riskData.max_drawdown.max_drawdown_pct}%` : null} />
        <Metric label="年化波动率" value={riskData.volatility?.annual_pct != null ? `${riskData.volatility.annual_pct}%` : null} />
        <div>
          <div className="text-xs text-gray-500 dark:text-gray-400">夏普比率</div>
          <div className={`font-semibold ${sharpeColor}`}>
            {riskData.sharpe?.sharpe_ratio != null ? riskData.sharpe.sharpe_ratio.toFixed(2) : 'N/A'}
          </div>
        </div>
        <Metric label="建议仓位(半凯利)"
          value={riskData.kelly_position?.fractional_pct != null ? `${riskData.kelly_position.fractional_pct}%` : null}
          suffix={riskData.kelly_position?.risk_level ? `(${riskData.kelly_position.risk_level})` : undefined} />
        <Metric label="ATR止损价"
          value={riskData.atr_stop_loss?.stop_loss_price != null ? `¥${riskData.atr_stop_loss.stop_loss_price}` : null}
          className="font-semibold text-red-500" />
        <Metric label="最大单日跌幅"
          value={riskData.max_1d_loss_pct != null ? `${riskData.max_1d_loss_pct}%` : null}
          className="font-semibold text-red-500" />
        <Metric label="CVaR (95%)" value={riskData.cvar_95?.cvar_pct != null ? `${riskData.cvar_95.cvar_pct}%` : null} />
      </div>
      {riskData.position_analysis && (
        <div className="mt-3 pt-3 border-t border-gray-200 dark:border-gray-700">
          <div className="text-xs text-gray-500 dark:text-gray-400 mb-2">持仓风险评估</div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-sm">
            <div>
              <span className="text-gray-500 dark:text-gray-400">95%VaR最大损失:</span>{' '}
              <span className="font-semibold text-red-500">
                ¥{riskData.position_analysis.var_95_max_loss?.toFixed(0) || 'N/A'}
              </span>
            </div>
            {riskData.position_analysis.suggested_stop_loss && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">建议止损:</span>{' '}
                <span className="font-semibold text-red-500">
                  ¥{riskData.position_analysis.suggested_stop_loss}
                </span>
                <span className="text-xs text-gray-400 ml-1">
                  (-{riskData.position_analysis.stop_loss_pct}%)
                </span>
              </div>
            )}
            {riskData.position_analysis.kelly_suggested_pct && (
              <div>
                <span className="text-gray-500 dark:text-gray-400">凯利建议:</span>{' '}
                <span className="font-semibold text-blue-500">
                  {riskData.position_analysis.kelly_suggested_pct}%
                </span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function Metric({ label, value, suffix, className }: { label: string; value?: string | null; suffix?: string; className?: string }) {
  return (
    <div>
      <div className="text-xs text-gray-500 dark:text-gray-400">{label}</div>
      <div className={className || 'font-semibold text-gray-900 dark:text-white'}>
        {value ?? 'N/A'}
        {suffix && <span className="text-xs text-gray-400 ml-1">{suffix}</span>}
      </div>
    </div>
  );
}
