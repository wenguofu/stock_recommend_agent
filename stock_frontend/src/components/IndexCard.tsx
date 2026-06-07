import { Card, Statistic, Skeleton } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { stockUpColor, stockDownColor } from '../constants/tokens';

export interface IndexData {
  current_price?: number;
  change_percent?: number;
  high?: number;
  low?: number;
  volume?: number;
  yesterday_close?: number;
}

interface IndexCardProps {
  title: string;
  data?: IndexData;
  isLoading: boolean;
  color: string;
}

export default function IndexCard({ title, data, isLoading, color }: IndexCardProps) {
  if (isLoading) {
    return (
      <Card title={title}>
        <Skeleton active paragraph={{ rows: 3 }} />
      </Card>
    );
  }

  if (!data || data.current_price == null) {
    return (
      <Card title={title} style={{ borderTop: `3px solid ${color}` }}>
        <Statistic value="--" />
      </Card>
    );
  }

  const changePercent = data.change_percent ?? 0;
  const isUp = changePercent >= 0;

  return (
    <Card title={title} style={{ borderTop: `3px solid ${color}` }}>
      <Statistic
        value={data.current_price}
        precision={2}
        formatter={(val) => (val as number).toFixed(2)}
        valueStyle={{ color: isUp ? stockUpColor : stockDownColor, fontSize: 28 }}
        prefix={isUp ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
        suffix={
          <span style={{ fontSize: 16, color: isUp ? stockUpColor : stockDownColor }}>
            {isUp ? '+' : ''}{changePercent.toFixed(2)}%
          </span>
        }
      />
      <div style={{ display: 'flex', gap: 16, marginTop: 12, fontSize: 12, color: '#888' }}>
        <span>高 {data.high?.toFixed(2) ?? '--'}</span>
        <span>低 {data.low?.toFixed(2) ?? '--'}</span>
        <span>量 {data.volume ? (data.volume / 10000).toFixed(0) + '万手' : '--'}</span>
      </div>
    </Card>
  );
}
