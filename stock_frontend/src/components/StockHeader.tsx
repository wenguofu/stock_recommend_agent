import { Descriptions, Tag, Statistic, Space, Card } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import AIAnalyzeButton from './AIAnalyzeButton';
import { stockUpColor, stockDownColor } from '../constants/tokens';

interface StockHeaderProps {
  name?: string;
  code: string;
  currentPrice?: number;
  changePercent?: number;
  high?: number;
  low?: number;
  open?: number;
  yesterdayClose?: number;
  volume?: number;
  amount?: number;
}

const priceStyle = { fontSize: 28, fontWeight: 700 };

export default function StockHeader({
  name,
  code,
  currentPrice,
  changePercent,
  high,
  low,
  open,
  yesterdayClose,
  volume,
  amount,
}: StockHeaderProps) {
  const isUp = (changePercent ?? 0) >= 0;
  const upColor = stockUpColor;
  const downColor = stockDownColor;

  return (
    <Card
      style={{ marginBottom: 16 }}
      title={
        <Space align="center">
          <span style={{ fontSize: 24, fontWeight: 700, color: isUp ? upColor : downColor }}>
            {name || code}
          </span>
          <Tag color={isUp ? 'red' : 'green'}>
            {isUp ? '+' : ''}{changePercent?.toFixed(2)}%
          </Tag>
        </Space>
      }
      extra={<AIAnalyzeButton code={code} />}
    >
      <Descriptions column={{ xs: 2, sm: 3, md: 4 }} bordered size="small">
        <Descriptions.Item label="当前价">
          <Statistic
            value={currentPrice ?? 0}
            precision={2}
            prefix="¥"
            valueStyle={{ ...priceStyle, color: isUp ? upColor : downColor, fontSize: 20 }}
          />
        </Descriptions.Item>
        <Descriptions.Item label="涨跌幅">
          <Statistic
            value={changePercent ?? 0}
            precision={2}
            suffix="%"
            prefix={isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
            valueStyle={{ color: isUp ? upColor : downColor, fontSize: 20 }}
          />
        </Descriptions.Item>
        {high != null && (
          <Descriptions.Item label="最高">
            <Statistic value={high} precision={2} prefix="¥" valueStyle={{ fontSize: 16 }} />
          </Descriptions.Item>
        )}
        {low != null && (
          <Descriptions.Item label="最低">
            <Statistic value={low} precision={2} prefix="¥" valueStyle={{ fontSize: 16 }} />
          </Descriptions.Item>
        )}
        {open != null && (
          <Descriptions.Item label="开盘">
            <Statistic value={open} precision={2} prefix="¥" valueStyle={{ fontSize: 16 }} />
          </Descriptions.Item>
        )}
        {yesterdayClose != null && (
          <Descriptions.Item label="昨收">
            <Statistic value={yesterdayClose} precision={2} prefix="¥" valueStyle={{ fontSize: 16 }} />
          </Descriptions.Item>
        )}
        {volume != null && (
          <Descriptions.Item label="成交量">
            {(volume / 10000).toFixed(0)}万手
          </Descriptions.Item>
        )}
        {amount != null && (
          <Descriptions.Item label="成交额">
            {(amount / 100000000).toFixed(2)}亿
          </Descriptions.Item>
        )}
      </Descriptions>
    </Card>
  );
}
