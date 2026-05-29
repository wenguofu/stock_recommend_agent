import { Card, Tag, Typography, Row, Col, Divider, Alert } from 'antd';
import { WarningOutlined } from '@ant-design/icons';

const { Text } = Typography;

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
  '低风险': 'green',
  '中等风险': 'gold',
  '高风险': 'orange',
};

export default function RiskPanel({ riskData }: Props) {
  if (!riskData?.risk_grade || riskData.risk_grade === 'data_insufficient') {
    return (
      <Card size="small" title="风险指标">
        <Alert message="风险数据不足" description="该股票历史数据不足60个交易日，无法计算风险指标" type="info" showIcon />
      </Card>
    );
  }

  const gradeColor = GRADE_COLORS[riskData.risk_grade] || 'red';
  const sharpeVal = riskData.sharpe?.sharpe_ratio ?? 0;
  const sharpeColor = sharpeVal >= 1 ? '#3f8600' : sharpeVal >= 0 ? '#d4b106' : '#cf1322';

  return (
    <Card
      size="small"
      title={<span><WarningOutlined style={{ marginRight: 8 }} />风险指标</span>}
      extra={<Tag color={gradeColor}>{riskData.risk_grade}</Tag>}
      style={{ borderLeft: '4px solid #fa8c16' }}
    >
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Metric label="VaR (95%/日)" value={riskData.var_95?.var_pct != null ? `${riskData.var_95.var_pct}%` : null} />
        </Col>
        <Col span={6}>
          <Metric label="最大回撤" value={riskData.max_drawdown?.max_drawdown_pct != null ? `${riskData.max_drawdown.max_drawdown_pct}%` : null} />
        </Col>
        <Col span={6}>
          <Metric label="年化波动率" value={riskData.volatility?.annual_pct != null ? `${riskData.volatility.annual_pct}%` : null} />
        </Col>
        <Col span={6}>
          <Text type="secondary" style={{ fontSize: 12 }}>夏普比率</Text>
          <br />
          <Text strong style={{ color: sharpeColor }}>
            {riskData.sharpe?.sharpe_ratio != null ? riskData.sharpe.sharpe_ratio.toFixed(2) : 'N/A'}
          </Text>
        </Col>
        <Col span={6}>
          <Metric label="建议仓位(半凯利)" value={riskData.kelly_position?.fractional_pct != null ? `${riskData.kelly_position.fractional_pct}%` : null} suffix={riskData.kelly_position?.risk_level ? `(${riskData.kelly_position.risk_level})` : undefined} />
        </Col>
        <Col span={6}>
          <Metric label="ATR止损价" value={riskData.atr_stop_loss?.stop_loss_price != null ? `¥${riskData.atr_stop_loss.stop_loss_price}` : null} color="#cf1322" />
        </Col>
        <Col span={6}>
          <Metric label="最大单日跌幅" value={riskData.max_1d_loss_pct != null ? `${riskData.max_1d_loss_pct}%` : null} color="#cf1322" />
        </Col>
        <Col span={6}>
          <Metric label="CVaR (95%)" value={riskData.cvar_95?.cvar_pct != null ? `${riskData.cvar_95.cvar_pct}%` : null} />
        </Col>
      </Row>
      {riskData.position_analysis && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>持仓风险评估</Text>
          <Row gutter={[16, 8]} style={{ marginTop: 8 }}>
            <Col span={8}>
              <Text type="secondary" style={{ fontSize: 12 }}>95%VaR最大损失: </Text>
              <Text strong style={{ color: '#cf1322' }}>
                ¥{riskData.position_analysis.var_95_max_loss?.toFixed(0) || 'N/A'}
              </Text>
            </Col>
            {riskData.position_analysis.suggested_stop_loss && (
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>建议止损: </Text>
                <Text strong style={{ color: '#cf1322' }}>
                  ¥{riskData.position_analysis.suggested_stop_loss}
                </Text>
                <Text style={{ fontSize: 11, color: '#999', marginLeft: 4 }}>
                  (-{riskData.position_analysis.stop_loss_pct}%)
                </Text>
              </Col>
            )}
            {riskData.position_analysis.kelly_suggested_pct && (
              <Col span={8}>
                <Text type="secondary" style={{ fontSize: 12 }}>凯利建议: </Text>
                <Text strong style={{ color: '#1677ff' }}>
                  {riskData.position_analysis.kelly_suggested_pct}%
                </Text>
              </Col>
            )}
          </Row>
        </>
      )}
    </Card>
  );
}

function Metric({ label, value, suffix, color }: { label: string; value?: string | null; suffix?: string; color?: string }) {
  return (
    <>
      <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
      <br />
      <Text strong style={color ? { color } : undefined}>
        {value ?? 'N/A'}
        {suffix && <Text style={{ fontSize: 11, color: '#999', marginLeft: 4 }}>{suffix}</Text>}
      </Text>
    </>
  );
}
