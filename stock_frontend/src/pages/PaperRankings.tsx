import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Card, Table, Button, Tag, Space, Typography, Spin, Segmented } from "antd";
import { ArrowLeftOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface RankingItem {
  account_id: number;
  account_name: string;
  strategy_id: number | null;
  initial_capital: number;
  total_value: number;
  total_pnl: number;
  total_profit_pct: number;
  max_drawdown: number | null;
  win_rate: number | null;
  stock_count: number;
  order_count: number;
  days_running: number;
  created_at: string;
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

export default function PaperRankings() {
  const navigate = useNavigate();
  const [sortBy, setSortBy] = useState<"profit_pct" | "total_pnl" | "win_rate">("profit_pct");

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-rankings"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/profit-ranking`);
      if (!r.ok) throw new Error("获取排名失败");
      const d = await r.json();
      return d.rankings as RankingItem[];
    },
    refetchInterval: 30000,
  });

  const sorted = data
    ? [...data].sort((a, b) => {
        if (sortBy === "profit_pct") return b.total_profit_pct - a.total_profit_pct;
        if (sortBy === "total_pnl") return b.total_pnl - a.total_pnl;
        if (sortBy === "win_rate") return (b.win_rate ?? -999) - (a.win_rate ?? -999);
        return 0;
      })
    : [];

  const rankEmoji = (idx: number) => {
    if (idx === 0) return "🥇";
    if (idx === 1) return "🥈";
    if (idx === 2) return "🥉";
    return idx + 1;
  };

  const rankColors = ["#faad14", "#8c8c8c", "#d48806"];

  const columns: ColumnsType<RankingItem> = [
    {
      title: '#', key: 'rank', align: 'center', width: 52,
      render: (_: any, __: RankingItem, idx: number) => (
        <Text strong style={{ fontSize: 18, color: rankColors[idx] || '#8c8c8c' }}>{rankEmoji(idx)}</Text>
      ),
    },
    {
      title: '账户名称', dataIndex: 'account_name', key: 'account_name',
      render: (name: string, record: RankingItem) => (
        <div>
          <Text strong>{name}</Text>
          <div>
            <Tag color={record.strategy_id ? "blue" : "default"} style={{ fontSize: 11 }}>
              {record.strategy_id ? "策略盘" : "手动盘"}
            </Tag>
          </div>
        </div>
      ),
    },
    {
      title: '收益率', dataIndex: 'total_profit_pct', key: 'profit_pct', align: 'right',
      render: (v: number) => (
        <Text strong style={{ fontSize: 16, color: v >= 0 ? '#ff4d4f' : '#52c41a' }}>{fmtPct(v)}</Text>
      ),
      sorter: (a, b) => a.total_profit_pct - b.total_profit_pct,
    },
    {
      title: '总盈亏', dataIndex: 'total_pnl', key: 'total_pnl', align: 'right',
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? '#ff4d4f' : '#52c41a' }}>{fmtMoney(v)}</Text>
      ),
    },
    {
      title: '总资产', dataIndex: 'total_value', key: 'total_value', align: 'right',
      render: (v: number) => <Text strong>{fmtMoney(v)}</Text>,
    },
    { title: '起始资金', dataIndex: 'initial_capital', key: 'initial_capital', align: 'right',
      render: (v: number) => <Text type="secondary">{fmtMoney(v)}</Text>,
    },
    { title: '胜率', dataIndex: 'win_rate', key: 'win_rate', align: 'right', render: (v: number | null) => fmtPct(v) },
    { title: '最大回撤', dataIndex: 'max_drawdown', key: 'max_drawdown', align: 'right', render: (v: number | null) => fmtPct(v) },
    { title: '持仓', dataIndex: 'stock_count', key: 'stock_count', align: 'center' },
    { title: '订单', dataIndex: 'order_count', key: 'order_count', align: 'center', render: (v: number) => <Text type="secondary">{v}</Text> },
    { title: '运行', dataIndex: 'days_running', key: 'days_running', align: 'center',
      render: (v: number) => <Text type="secondary" style={{ fontSize: 12 }}>{v}天</Text>,
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={2}>📊 收益排名</Title>
          <Text type="secondary">所有模拟盘按收益率倒序排列，评估各策略表现</Text>
        </div>
        <Button icon={<ArrowLeftOutlined />} onClick={() => navigate("/paper")}>
          返回模拟盘
        </Button>
      </div>

      {/* Sort Tabs */}
      <Segmented
        value={sortBy}
        onChange={(val) => setSortBy(val as "profit_pct" | "total_pnl" | "win_rate")}
        options={[
          { label: '收益率', value: 'profit_pct' },
          { label: '总盈亏', value: 'total_pnl' },
          { label: '胜率', value: 'win_rate' },
        ]}
      />

      {/* Loading */}
      {isLoading && (
        <Card><div style={{ textAlign: 'center', padding: 48 }}><Spin /></div></Card>
      )}

      {/* Error */}
      {error && (
        <Card>
          <Text type="danger">加载失败: {(error as Error).message}</Text>
        </Card>
      )}

      {/* Empty */}
      {!isLoading && sorted.length === 0 && (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <Text type="secondary" style={{ fontSize: 24, display: 'block', marginBottom: 8 }}>📭</Text>
          <Text type="secondary">暂无模拟盘数据</Text>
        </div>
      )}

      {/* Ranking Table */}
      {sorted.length > 0 && (
        <Card styles={{ body: { padding: 0 } }}>
          <Table<RankingItem>
            columns={columns}
            dataSource={sorted}
            rowKey="account_id"
            pagination={false}
            size="middle"
            scroll={{ x: 1100 }}
            onRow={(record) => ({
              onClick: () => navigate(`/paper/breakdown/${record.account_id}`),
              style: { cursor: 'pointer' },
            })}
          />
        </Card>
      )}
    </Space>
  );
}
