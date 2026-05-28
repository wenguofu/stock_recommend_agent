import { Card, Tag, Typography, Row, Col, Divider } from 'antd';
import { RobotOutlined, ArrowUpOutlined, ArrowDownOutlined, MinusOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

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
  const confColor = mlData.confidence === 'high' ? 'green' : mlData.confidence === 'medium' ? 'gold' : 'default';

  const dirLabel = mlData.direction === 'up' ? '📈 看涨' : mlData.direction === 'down' ? '📉 看跌' : '➡️ 中性';

  return (
    <Card
      size="small"
      title={
        <span>
          <RobotOutlined style={{ marginRight: 8 }} />
          ML预测 (未来{mlData.horizon_days}日)
        </span>
      }
      extra={<Tag color={confColor}>置信度: {confLabel}</Tag>}
      style={{ borderLeft: '4px solid #722ed1' }}
    >
      <Row gutter={[16, 16]}>
        <Col span={6}>
          <Text type="secondary" style={{ fontSize: 12 }}>方向预测</Text>
          <br />
          <Text strong style={{ fontSize: 16, color: mlData.direction === 'up' ? '#cf1322' : mlData.direction === 'down' ? '#3f8600' : '#888' }}>
            {dirLabel}
          </Text>
        </Col>
        <Col span={6}>
          <Text type="secondary" style={{ fontSize: 12 }}>上涨概率</Text>
          <br />
          <Text strong style={{ color: '#cf1322' }}>{mlData.up_prob}%</Text>
        </Col>
        <Col span={6}>
          <Text type="secondary" style={{ fontSize: 12 }}>预测收益率</Text>
          <br />
          <Text strong style={{ color: (mlData.predicted_return_pct ?? 0) >= 0 ? '#cf1322' : '#3f8600' }}>
            {mlData.predicted_return_pct != null
              ? `${mlData.predicted_return_pct > 0 ? '+' : ''}${mlData.predicted_return_pct}%`
              : 'N/A'}
          </Text>
        </Col>
        {mlData.return_range && (
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 12 }}>收益区间</Text>
            <br />
            <Text strong>{mlData.return_range}</Text>
          </Col>
        )}
      </Row>
      {mlData.key_factors && mlData.key_factors.length > 0 && (
        <>
          <Divider style={{ margin: '12px 0' }} />
          <Text type="secondary" style={{ fontSize: 12 }}>驱动因子: </Text>
          <Text style={{ fontSize: 12 }}>{mlData.key_factors.join(', ')}</Text>
        </>
      )}
    </Card>
  );
}
