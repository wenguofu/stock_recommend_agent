import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Card, Table, Tag, Button, Space, Typography, Spin, Empty, Alert, Segmented, Statistic, Row, Col, Descriptions } from "antd";
import { ReloadOutlined, SafetyCertificateOutlined, WarningOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface WinRate {
  "5d": number;
  "10d": number;
  "20d": number;
}

interface Recommendation {
  code: string;
  name: string;
  composite_score: number;
  key_win_rate: number;
  key_avg_return: number;
  win_rates: WinRate;
  avg_returns: WinRate;
  target_price?: number;
  stop_loss_price?: number;
  breakout_pct?: number;
  vol_ratio?: number;
  rsi?: number;
  max_dd_10d?: number;
}

interface PipelineStatus {
  layer1: { candidates_count: number; market_safe: boolean };
  layer2: { scored_count: number; top_count: number };
  layer3: { verified_count: number; recommended_count: number };
}

export default function HighWinRecommend() {
  const navigate = useNavigate();
  const [recType, setRecType] = useState<"short" | "mid">("short");

  const { data, isLoading, refetch } = useQuery({
    queryKey: ["high-win-recommend", recType],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/screening/recommend?type=${recType}&top_n=5`);
      if (!r.ok) throw new Error("获取推荐失败");
      return r.json();
    },
    staleTime: 60000,
  });

  const { data: marketCheck } = useQuery({
    queryKey: ["market-check"],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/screening/market-check`);
      if (!r.ok) throw new Error("获取大盘状态失败");
      return r.json();
    },
    staleTime: 30000,
  });

  const recommendations: Recommendation[] = data?.recommendations || [];
  const pipelineStatus: PipelineStatus = data?.pipeline_status || {};
  const isSafe = marketCheck?.is_safe ?? true;

  const columns: ColumnsType<Recommendation> = [
    {
      title: '代码', dataIndex: 'code', key: 'code', width: 90,
      render: (code: string) => (
        <Button type="link" onClick={() => navigate(`/stock/${code}`)} style={{ fontFamily: 'monospace', padding: 0 }}>
          {code}
        </Button>
      ),
    },
    { title: '名称', dataIndex: 'name', key: 'name', width: 100, render: (v: string) => <Text strong>{v}</Text> },
    {
      title: '综合评分', dataIndex: 'composite_score', key: 'composite_score', align: 'center', width: 90,
      render: (v: number) => <Tag color={v >= 70 ? 'green' : v >= 50 ? 'orange' : 'red'}>{v}</Tag>,
    },
    {
      title: '历史胜率', dataIndex: 'key_win_rate', key: 'key_win_rate', align: 'center', width: 90,
      render: (v: number) => (
        <Text style={{ color: v >= 0.75 ? '#52c41a' : v >= 0.70 ? '#faad14' : '#ff4d4f', fontWeight: 'bold' }}>
          {(v * 100).toFixed(0)}%
        </Text>
      ),
    },
    {
      title: '平均收益', dataIndex: 'key_avg_return', key: 'key_avg_return', align: 'center', width: 80,
      render: (v: number) => <Text style={{ color: '#1677ff' }}>{v?.toFixed(1)}%</Text>,
    },
    {
      title: '目标价', dataIndex: 'target_price', key: 'target_price', align: 'center', width: 80,
      render: (v: number) => v ? <Text>{v.toFixed(2)}</Text> : <Text type="secondary">--</Text>,
    },
    {
      title: '止损价', dataIndex: 'stop_loss_price', key: 'stop_loss_price', align: 'center', width: 80,
      render: (v: number) => v ? <Text type="danger">{v.toFixed(2)}</Text> : <Text type="secondary">--</Text>,
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={2}>🎯 高胜率精选推荐</Title>
          <Text type="secondary">四层筛选：大盘环境 → 技术面宽筛 → 多信号评分 → 历史胜率验证</Text>
        </div>
        <Button type="primary" icon={<ReloadOutlined />} onClick={() => refetch()}>
          刷新
        </Button>
      </div>

      {/* Market Safety Alert */}
      {!isSafe && (
        <Alert
          type="warning"
          showIcon
          icon={<WarningOutlined />}
          message="大盘环境不安全"
          description={`涨幅>8%仅${marketCheck?.details?.strong_count}只，跌停${marketCheck?.details?.limit_down_count}只，市场恐慌情绪较重，暂停筛选推荐。`}
        />
      )}

      {/* Pipeline Stats */}
      <Row gutter={16}>
        <Col span={6}>
          <Card>
            <Statistic
              title="候选股票"
              value={pipelineStatus?.layer1?.candidates_count || 0}
              prefix={<SafetyCertificateOutlined />}
              valueStyle={{ color: '#1677ff' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>Layer 1 筛选后</Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="评分排名"
              value={pipelineStatus?.layer2?.top_count || 0}
              suffix="只"
              valueStyle={{ color: '#52c41a' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>Layer 2 Top</Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="胜率验证"
              value={pipelineStatus?.layer3?.verified_count || 0}
              suffix="只"
              valueStyle={{ color: pipelineStatus?.layer3?.verified_count > 0 ? '#faad14' : '#ff4d4f' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>历史胜率≥70%</Text>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="精选推荐"
              value={recommendations.length}
              suffix="只"
              valueStyle={{ color: '#531dab' }}
            />
            <Text type="secondary" style={{ fontSize: 12 }}>最终推荐</Text>
          </Card>
        </Col>
      </Row>

      {/* Type Selection */}
      <Segmented
        value={recType}
        onChange={(val) => setRecType(val as "short" | "mid")}
        options={[
          { label: '⚡ 短线推荐 (5-20天)', value: 'short' },
          { label: '📈 中线推荐 (1-3月)', value: 'mid' },
        ]}
      />

      {/* Loading */}
      {isLoading && <Card><div style={{ textAlign: 'center', padding: 48 }}><Spin /></div></Card>}

      {/* Empty */}
      {!isLoading && recommendations.length === 0 && (
        <Empty
          image={Empty.PRESENTED_IMAGE_SIMPLE}
          description={!isSafe ? "大盘环境不安全，暂停筛选" : "暂无符合条件的股票"}
        />
      )}

      {/* Recommendations Table */}
      {recommendations.length > 0 && (
        <Card title="精选推荐" style={{ borderLeft: '4px solid #531dab' }}>
          <Table<Recommendation>
            columns={columns}
            dataSource={recommendations}
            rowKey="code"
            pagination={false}
            size="small"
            scroll={{ x: 800 }}
            expandable={{
              expandedRowRender: (record) => (
                <Descriptions size="small" column={4}>
                  <Descriptions.Item label="突破幅度">{record.breakout_pct}%</Descriptions.Item>
                  <Descriptions.Item label="量比">{record.vol_ratio}x</Descriptions.Item>
                  <Descriptions.Item label="RSI">{record.rsi}</Descriptions.Item>
                  <Descriptions.Item label="近10日最大回撤">{record.max_dd_10d}%</Descriptions.Item>
                  <Descriptions.Item label="5日胜率">{(record.win_rates?.["5d"] * 100).toFixed(0)}%</Descriptions.Item>
                  <Descriptions.Item label="10日胜率">{(record.win_rates?.["10d"] * 100).toFixed(0)}%</Descriptions.Item>
                  <Descriptions.Item label="20日胜率">{(record.win_rates?.["20d"] * 100).toFixed(0)}%</Descriptions.Item>
                  <Descriptions.Item label="平均收益(5日)">{record.avg_returns?.["5d"]?.toFixed(1)}%</Descriptions.Item>
                </Descriptions>
              ),
            }}
          />
        </Card>
      )}

      {/* Pipeline Info */}
      {pipelineStatus?.layer1 && (
        <Card title="筛选流程说明" size="small">
          <Row gutter={16}>
            <Col span={8}>
              <Text strong>Layer 1 大盘环境</Text>
              <br />
              <Text type="secondary">涨幅>8% ≥50只 且 跌停 ≤50只</Text>
              <br />
              <Text>热门板块 + 流动性 + 上市时间</Text>
            </Col>
            <Col span={8}>
              <Text strong>Layer 2 多信号评分</Text>
              <br />
              <Text type="secondary">短线: 量价突破 + 均线多头 + RSI + 资金</Text>
              <br />
              <Text>中线: 均线金叉 + 60日涨幅 + 突破信号</Text>
            </Col>
            <Col span={8}>
              <Text strong>Layer 3 历史胜率验证</Text>
              <br />
              <Text type="secondary">回溯历史相同信号模式</Text>
              <br />
              <Text>只推荐历史胜率 ≥70% 的股票</Text>
            </Col>
          </Row>
        </Card>
      )}
    </Space>
  );
}