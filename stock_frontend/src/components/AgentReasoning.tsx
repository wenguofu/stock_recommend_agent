// stock_frontend/src/components/AgentReasoning.tsx
import { Card, Collapse, Tag, Progress, Descriptions } from 'antd';
import {
  GlobalOutlined, LineChartOutlined, FundOutlined,
  SafetyCertificateOutlined, CheckCircleOutlined,
} from '@ant-design/icons';

interface AgentResult {
  stance?: string;
  confidence?: number;
  reasoning?: string;
  veto?: boolean;
  veto_reason?: string;
  risk_grade?: string;
  valuation?: string;
}

interface SpecialistResults {
  Macro?: AgentResult;
  Technical?: AgentResult;
  Fundamental?: AgentResult;
  Risk?: AgentResult;
}

interface DecisionResult {
  action?: string;
  confidence?: number;
  position_pct?: number;
  stop_loss_pct?: number;
  take_profit_pct?: number;
  reasoning?: string;
  risk_flags?: string[];
  horizon?: string;
}

interface AgentReasoningProps {
  specialists: SpecialistResults;
  decision: DecisionResult;
}

const agentIcons: Record<string, React.ReactNode> = {
  Macro: <GlobalOutlined />,
  Technical: <LineChartOutlined />,
  Fundamental: <FundOutlined />,
  Risk: <SafetyCertificateOutlined />,
};

const stanceColors: Record<string, string> = {
  bullish: '#cf1322',
  neutral: '#faad14',
  bearish: '#1677ff',
};

const actionColors: Record<string, string> = {
  buy: '#cf1322',
  sell: '#1677ff',
  hold: '#faad14',
  watch: '#d9d9d9',
};

const actionLabels: Record<string, string> = {
  buy: 'Buy',
  sell: 'Sell',
  hold: 'Hold',
  watch: 'Watch',
};

export default function AgentReasoning({ specialists, decision }: AgentReasoningProps) {
  const items = Object.entries(specialists).map(([name, result]) => ({
    key: name,
    label: (
      <span>
        {agentIcons[name]} {name}
        {result?.stance && (
          <Tag color={stanceColors[result.stance]} style={{ marginLeft: 8 }}>
            {result.stance}
          </Tag>
        )}
        {result?.veto && <Tag color="red">VETO</Tag>}
        {result?.risk_grade && (
          <Tag color={result.risk_grade === 'high' ? 'red' : 'green'}>
            Risk: {result.risk_grade}
          </Tag>
        )}
      </span>
    ),
    children: (
      <div>
        <p>{result?.reasoning || 'No analysis'}</p>
        {result?.confidence !== undefined && (
          <Progress percent={result.confidence} size="small" />
        )}
      </div>
    ),
  }));

  return (
    <Card title="AI Agent Reasoning" size="small">
      <Collapse items={items} size="small" />

      <Card
        type="inner"
        title={
          <span>
            <CheckCircleOutlined /> Final Decision
            {decision?.action && (
              <Tag color={actionColors[decision.action]} style={{ marginLeft: 8 }}>
                {actionLabels[decision.action] || decision.action}
              </Tag>
            )}
          </span>
        }
        style={{ marginTop: 12 }}
      >
        <Descriptions column={2} size="small">
          <Descriptions.Item label="Confidence">{decision?.confidence ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="Position">{decision?.position_pct ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="Stop Loss">{decision?.stop_loss_pct ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="Take Profit">{decision?.take_profit_pct ?? '-'}%</Descriptions.Item>
          <Descriptions.Item label="Horizon">{decision?.horizon ?? '-'}</Descriptions.Item>
          <Descriptions.Item label="Risk Flags">
            {decision?.risk_flags?.map((flag) => (
              <Tag key={flag} color="orange">{flag}</Tag>
            )) || '-'}
          </Descriptions.Item>
        </Descriptions>
        <p style={{ marginTop: 8 }}>{decision?.reasoning}</p>
      </Card>
    </Card>
  );
}
