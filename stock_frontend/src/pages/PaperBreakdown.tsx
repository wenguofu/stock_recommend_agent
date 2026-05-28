import { useParams, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Card, Table, Button, Tag, Space, Typography, Spin, Statistic, Collapse } from "antd";
import { ArrowLeftOutlined, CaretDownOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface Trade {
  order_id: number;
  direction: string;
  price: number;
  quantity: number;
  amount: number;
  commission: number;
  tax: number;
  order_type: string;
  note: string | null;
  created_at: string;
}

interface StockBreakdown {
  code: string;
  name: string;
  total_buy: number;
  total_sell: number;
  buy_count: number;
  sell_count: number;
  total_commission: number;
  total_tax: number;
  realized_pnl: number;
  current_position: number;
  current_market_value: number;
  current_unrealized_pnl: number;
  total_pnl: number;
  trade_count: number;
  trades: Trade[];
}

interface BreakdownData {
  account_id: number;
  account_name: string;
  initial_capital: number;
  total_value: number;
  cash_balance: number;
  total_pnl: number;
  total_profit_pct: number;
  max_drawdown: number | null;
  win_rate: number | null;
  stock_count: number;
  stocks: StockBreakdown[];
}

function fmtMoney(v: number): string {
  const abs = Math.abs(v);
  const sign = v < 0 ? "-" : "";
  if (abs >= 1e8) return sign + (abs / 1e8).toFixed(2) + "亿";
  if (abs >= 1e4) return sign + (abs / 1e4).toFixed(2) + "万";
  return v.toFixed(2);
}

function fmtPct(v: number | null): string {
  if (v == null) return "-";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

const tradeColumns: ColumnsType<Trade> = [
  {
    title: '时间', dataIndex: 'created_at', key: 'created_at', width: 160,
    render: (v: string) => <Text style={{ fontSize: 12 }}>{new Date(v).toLocaleString("zh-CN")}</Text>,
  },
  {
    title: '方向', dataIndex: 'direction', key: 'direction', width: 60,
    render: (v: string) => (
      <Tag color={v === "buy" ? "red" : "green"}>{v === "buy" ? "买入" : "卖出"}</Tag>
    ),
  },
  { title: '价格', dataIndex: 'price', key: 'price', align: 'right', width: 80, render: (v: number) => v.toFixed(2) },
  { title: '数量', dataIndex: 'quantity', key: 'quantity', align: 'right', width: 70 },
  { title: '金额', dataIndex: 'amount', key: 'amount', align: 'right', width: 100, render: (v: number) => fmtMoney(v) },
  { title: '佣金', dataIndex: 'commission', key: 'commission', align: 'right', width: 70, render: (v: number) => v.toFixed(2) },
  { title: '印花税', dataIndex: 'tax', key: 'tax', align: 'right', width: 70, render: (v: number) => v.toFixed(2) },
  {
    title: '类型', dataIndex: 'order_type', key: 'order_type', width: 70,
    render: (v: string) => <Tag>{v === "manual" ? "手动" : v === "signal" ? "信号" : v}</Tag>,
  },
  { title: '备注', dataIndex: 'note', key: 'note', width: 120, ellipsis: true, render: (v: string | null) => <Text type="secondary">{v || "-"}</Text> },
];

export default function PaperBreakdown() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const accountId = parseInt(id || "0");
  const [expandedStock, setExpandedStock] = useState<string | null>(null);

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-breakdown", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/profit-breakdown`);
      if (!r.ok) throw new Error("获取明细失败");
      return r.json() as Promise<BreakdownData>;
    },
    enabled: !!accountId,
  });

  if (isLoading) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 256 }}>
        <Spin />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div style={{ textAlign: 'center', padding: 64 }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
        <Text type="secondary">数据加载失败</Text>
        <br />
        <Button type="primary" style={{ marginTop: 16 }} onClick={() => navigate("/paper/rankings")}>
          返回排名
        </Button>
      </div>
    );
  }

  // Sort stocks by total_pnl desc
  const sortedStocks = [...data.stocks].sort((a, b) => b.total_pnl - a.total_pnl);

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Space>
          <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => navigate("/paper/rankings")} />
          <div>
            <Title level={3} style={{ margin: 0 }}>{data.account_name}</Title>
            <Text type="secondary">个股盈亏明细</Text>
          </div>
        </Space>
        <Button type="primary" onClick={() => navigate(`/paper/${accountId}`)}>
          查看账户详情
        </Button>
      </div>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: 16 }}>
        <Card size="small">
          <Statistic title="总资产" value={fmtMoney(data.total_value)}
            valueStyle={{ fontWeight: 'bold' }} />
        </Card>
        <Card size="small">
          <Statistic title="总盈亏" value={fmtMoney(data.total_pnl)}
            valueStyle={{ fontWeight: 'bold', color: data.total_pnl >= 0 ? '#ff4d4f' : '#52c41a' }} />
        </Card>
        <Card size="small">
          <Statistic title="收益率" value={fmtPct(data.total_profit_pct)}
            valueStyle={{ fontWeight: 'bold', color: data.total_profit_pct >= 0 ? '#ff4d4f' : '#52c41a' }} />
        </Card>
        <Card size="small">
          <Statistic title="交易股票数" value={`${data.stock_count} 只`}
            valueStyle={{ fontWeight: 'bold' }} />
        </Card>
      </div>

      {/* Per-Stock Breakdown */}
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {sortedStocks.map((stock) => {
          const isExpanded = expandedStock === stock.code;
          return (
            <Card
              key={stock.code}
              size="small"
              styles={{ body: { padding: 0 } }}
            >
              {/* Stock Header (clickable) */}
              <div
                style={{
                  padding: '12px 16px', display: 'flex', justifyContent: 'space-between',
                  alignItems: 'center', cursor: 'pointer',
                }}
                onClick={() => setExpandedStock(isExpanded ? null : stock.code)}
              >
                <Space>
                  <Text type="secondary" style={{ fontFamily: 'monospace', fontSize: 13 }}>{stock.code}</Text>
                  <Text strong>{stock.name}</Text>
                  <Tag color={stock.current_position > 0 ? "blue" : "default"}>
                    {stock.current_position > 0 ? `持仓${stock.current_position}股` : "已清仓"}
                  </Tag>
                </Space>
                <Space size="large">
                  <div style={{ textAlign: 'right' }}>
                    <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>总盈亏</Text>
                    <Text strong style={{ color: stock.total_pnl >= 0 ? '#ff4d4f' : '#52c41a' }}>
                      {fmtMoney(stock.total_pnl)}
                    </Text>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <Text type="secondary" style={{ fontSize: 11, display: 'block' }}>交易</Text>
                    <Text>{stock.trade_count}次</Text>
                  </div>
                  <CaretDownOutlined
                    style={{
                      transition: 'transform 0.3s',
                      transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)',
                      color: '#8c8c8c',
                    }}
                  />
                </Space>
              </div>

              {/* Expanded Detail */}
              {isExpanded && (
                <div style={{ borderTop: '1px solid #f0f0f0' }}>
                  {/* Summary Row */}
                  <div style={{
                    display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 16,
                    padding: 16, background: '#fafafa',
                  }}>
                    <Statistic title="买入总额" value={fmtMoney(stock.total_buy)}
                      valueStyle={{ fontSize: 14, fontWeight: 500 }} />
                    <Statistic title="卖出总额" value={fmtMoney(stock.total_sell)}
                      valueStyle={{ fontSize: 14, fontWeight: 500 }} />
                    <Statistic title="已实现盈亏" value={fmtMoney(stock.realized_pnl)}
                      valueStyle={{ fontSize: 14, fontWeight: 500, color: stock.realized_pnl >= 0 ? '#ff4d4f' : '#52c41a' }} />
                    <Statistic title="未实现盈亏" value={fmtMoney(stock.current_unrealized_pnl)}
                      valueStyle={{ fontSize: 14, fontWeight: 500, color: stock.current_unrealized_pnl >= 0 ? '#ff4d4f' : '#52c41a' }} />
                    <Statistic title="费用合计" value={fmtMoney(stock.total_commission + stock.total_tax)}
                      valueStyle={{ fontSize: 14, fontWeight: 500 }} />
                  </div>

                  {/* Trade Records */}
                  <Table<Trade>
                    columns={tradeColumns}
                    dataSource={stock.trades}
                    rowKey="order_id"
                    pagination={false}
                    size="small"
                    scroll={{ x: 900 }}
                  />
                </div>
              )}
            </Card>
          );
        })}
      </Space>
    </Space>
  );
}
