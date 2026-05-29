// stock_frontend/src/components/RegimeIndicator.tsx
import { Tag, Tooltip, Card } from 'antd';
import { RiseOutlined, FallOutlined, MinusOutlined } from '@ant-design/icons';

interface RegimeData {
  regime: 'bull' | 'bear' | 'sideways';
  confidence: number;
  probabilities: {
    bull: number;
    bear: number;
    sideways: number;
  };
  regime_score: number;
}

const regimeColors: Record<string, string> = {
  bull: '#cf1322',
  bear: '#1677ff',
  sideways: '#faad14',
};

const regimeIcons: Record<string, React.ReactNode> = {
  bull: <RiseOutlined />,
  bear: <FallOutlined />,
  sideways: <MinusOutlined />,
};

const regimeLabels: Record<string, string> = {
  bull: 'Bull',
  bear: 'Bear',
  sideways: 'Sideways',
};

export default function RegimeIndicator({ data }: { data: RegimeData | null }) {
  if (!data) {
    return (
      <Card size="small" title="Market Regime">
        <span style={{ color: '#999' }}>No data</span>
      </Card>
    );
  }

  const { regime, confidence, probabilities } = data;

  return (
    <Card
      size="small"
      title="Market Regime"
      extra={
        <Tooltip title={`Confidence: ${(confidence * 100).toFixed(0)}%`}>
          <Tag color={regimeColors[regime]} icon={regimeIcons[regime]}>
            {regimeLabels[regime]}
          </Tag>
        </Tooltip>
      }
    >
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        {(['bull', 'bear', 'sideways'] as const).map((r) => (
          <Tooltip key={r} title={`${regimeLabels[r]} probability`}>
            <div
              style={{
                flex: probabilities[r],
                height: 24,
                backgroundColor: regimeColors[r],
                borderRadius: 4,
                minWidth: 40,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#fff',
                fontSize: 12,
                fontWeight: regime === r ? 'bold' : 'normal',
                opacity: regime === r ? 1 : 0.6,
              }}
            >
              {(probabilities[r] * 100).toFixed(0)}%
            </div>
          </Tooltip>
        ))}
      </div>
    </Card>
  );
}
