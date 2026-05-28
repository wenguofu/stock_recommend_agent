import { Card, Typography, Row, Col } from 'antd';
import { DollarOutlined } from '@ant-design/icons';

const { Text } = Typography;

interface MoneyFlowItem {
  label: string;
  value: number | null;
  ratio?: number | null;
  unit: string;
}

interface MoneyFlowData {
  main_net_inflow?: number | null;
  main_net_ratio?: number | null;
  super_large_net_inflow?: number | null;
  super_large_net_ratio?: number | null;
  large_net_inflow?: number | null;
  large_net_ratio?: number | null;
  medium_net_inflow?: number | null;
  small_net_inflow?: number | null;
}

interface Props {
  moneyFlow: MoneyFlowData;
}

function MoneyFlowRow({ label, value, ratio, unit }: MoneyFlowItem) {
  if (value == null) return null;
  const isPositive = value >= 0;
  return (
    <Col span={8}>
      <Text type="secondary" style={{ fontSize: 13 }}>{label}</Text>
      <br />
      <Text strong style={{ fontSize: 18, color: isPositive ? '#cf1322' : '#3f8600' }}>
        {isPositive ? '+' : ''}{value.toFixed(2)}{unit}
      </Text>
      {ratio != null && (
        <div>
          <Text style={{ fontSize: 11, color: '#888' }}>占比: {ratio.toFixed(2)}%</Text>
        </div>
      )}
    </Col>
  );
}

export default function MoneyFlowPanel({ moneyFlow }: Props) {
  const items: MoneyFlowItem[] = [
    { label: '主力净流入', value: moneyFlow.main_net_inflow ?? null, ratio: moneyFlow.main_net_ratio ?? null, unit: '万' },
    { label: '超大单净流入', value: moneyFlow.super_large_net_inflow ?? null, ratio: moneyFlow.super_large_net_ratio ?? null, unit: '万' },
    { label: '大单净流入', value: moneyFlow.large_net_inflow ?? null, ratio: moneyFlow.large_net_ratio ?? null, unit: '万' },
    { label: '中单净流入', value: moneyFlow.medium_net_inflow ?? null, ratio: null, unit: '万' },
    { label: '小单净流入', value: moneyFlow.small_net_inflow ?? null, ratio: null, unit: '万' },
  ];

  return (
    <Card title={<span><DollarOutlined style={{ marginRight: 8 }} />今日资金流向</span>}>
      <Row gutter={[16, 16]}>
        {items.map((item, idx) => (
          <MoneyFlowRow key={idx} {...item} />
        ))}
      </Row>
    </Card>
  );
}
