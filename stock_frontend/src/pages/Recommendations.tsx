import { useState, useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Card, Table, Tag, Button, Space, Typography, Spin, Empty, Alert, Segmented } from "antd";
import { ReloadOutlined, PlusOutlined } from "@ant-design/icons";
import type { ColumnsType } from "antd/es/table";

const { Title, Text } = Typography;
const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface RecItem {
  id: number; rank: number; code: string; name: string;
  price: number; change_pct: number; turnover: number;
  score: number; reason: string; strategy: string;
  rec_type: string; created_at: string;
}

const STRATEGY_LABELS: Record<string, string> = {
  youzi: "游资策略",
  lianghua: "量化策略",
  jichang: "基础工具",
};

const STRATEGY_BG_COLORS: Record<string, string> = {
  youzi: "#fff2f0",
  lianghua: "#e6f4ff",
  jichang: "#f6ffed",
};
const STRATEGY_BORDER_COLORS: Record<string, string> = {
  youzi: "#ffccc7",
  lianghua: "#91caff",
  jichang: "#b7eb8f",
};
const STRATEGY_TEXT_COLORS: Record<string, string> = {
  youzi: "#cf1322",
  lianghua: "#0958d9",
  jichang: "#389e0d",
};

export default function Recommendations() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [activeTab, setActiveTab] = useState<"daily" | "weekly">("daily");

  const { data, isLoading } = useQuery({
    queryKey: ["recommendations", activeTab],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/recommendations/latest?type=${activeTab}`);
      if (!r.ok) throw new Error("获取推荐失败");
      return r.json();
    },
    refetchInterval: 120000,
  });

  const generateMutation = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${API_BASE}/api/recommendations/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ type: activeTab, top_n: 10 }),
      });
      if (!r.ok) throw new Error("生成失败");
      return r.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recommendations"] });
    },
  });

  const handleAddTracking = async (code: string, name: string) => {
    try {
      const r = await fetch(`${API_BASE}/api/paper/accounts`);
      const accts = await r.json();
      const autoAcct = accts.accounts?.find((a: any) => a.auto_trade);
      if (!autoAcct) {
        alert("没有自动跟踪账户，请先创建");
        return;
      }
      const r2 = await fetch(`${API_BASE}/api/paper/accounts/${autoAcct.id}/auto-rules`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          code, name,
          buy_price_low: null,
          buy_price_high: null,
          buy_quantity: 100,
          sell_target_price: null,
          sell_stop_loss: null,
          note: `推荐跟踪: ${activeTab}推荐`,
        }),
      });
      if (r2.ok) {
        alert(`已将 ${name}(${code}) 加入自动跟踪`);
      }
    } catch (e) {
      alert("添加跟踪失败");
    }
  };

  const strategies = data?.strategies || {};

  // 收集所有推荐股票代码，批量获取板块信息
  const allCodes = useMemo(() => {
    const codes = new Set<string>();
    Object.values(strategies).forEach((items: any) => {
      (items as RecItem[]).forEach((r) => {
        const c = r.code?.replace(/[^0-9]/g, '').slice(0, 6);
        if (c && c.length === 6) codes.add(c);
      });
    });
    return Array.from(codes);
  }, [strategies]);

  const { data: sectorMap = {} } = useQuery({
    queryKey: ['rec-sector-map', allCodes],
    queryFn: async () => {
      const map: Record<string, string> = {};
      for (const code of allCodes.slice(0, 20)) {
        try {
          const r = await fetch(`${API_BASE}/api/sectors/stock/${code}`);
          if (r.ok) {
            const d = await r.json();
            if (d?.sector) map[code] = d.sector;
          }
        } catch {}
      }
      return map;
    },
    enabled: allCodes.length > 0,
    staleTime: 300000,
  });

  const sectorColorMap: Record<string, { color: string; bg: string }> = {
    '半导体': { color: '#531dab', bg: '#f9f0ff' },
    '芯片': { color: '#531dab', bg: '#f9f0ff' },
    '消费电子': { color: '#0958d9', bg: '#e6f4ff' },
    '新能源': { color: '#389e0d', bg: '#f6ffed' },
  };

  const getSectorStyle = (rawCode: string) => {
    const code = rawCode?.replace(/[^0-9]/g, '').slice(0, 6);
    const sector = code ? sectorMap[code] : null;
    if (!sector) return { color: '#8c8c8c', bg: '#f5f5f5' };
    for (const [k, v] of Object.entries(sectorColorMap)) {
      if (sector.includes(k)) return v;
    }
    return { color: '#595959', bg: '#f5f5f5' };
  };

  const getScoreColor = (score: number) => {
    if (score >= 80) return 'red';
    if (score >= 60) return 'gold';
    return 'blue';
  };

  const recColumns: ColumnsType<RecItem> = [
    {
      title: '#', dataIndex: 'rank', key: 'rank', align: 'center', width: 48,
      render: (v: number) => <Text type="secondary" style={{ fontFamily: 'monospace' }}>{v}</Text>,
    },
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
      title: '所属板块', dataIndex: 'code', key: 'sector', width: 100,
      render: (code: string) => {
        const style = getSectorStyle(code);
        const cleanCode = code?.replace(/[^0-9]/g, '').slice(0, 6);
        const sector = cleanCode ? sectorMap[cleanCode] : null;
        return sector ? (
          <Tag style={{ background: style.bg, color: style.color, border: 'none' }}>{sector}</Tag>
        ) : <Text type="secondary">--</Text>;
      },
    },
    { title: '价格', dataIndex: 'price', key: 'price', align: 'right', width: 80, render: (v: number) => v?.toFixed(2) },
    {
      title: '涨跌幅', dataIndex: 'change_pct', key: 'change_pct', align: 'right', width: 80,
      render: (v: number) => (
        <Text style={{ color: (v || 0) >= 0 ? '#ff4d4f' : '#52c41a' }}>
          {(v || 0) >= 0 ? '+' : ''}{v?.toFixed(1)}%
        </Text>
      ),
    },
    { title: '换手率', dataIndex: 'turnover', key: 'turnover', align: 'right', width: 80, render: (v: number) => `${v?.toFixed(1)}%` },
    {
      title: '评分', dataIndex: 'score', key: 'score', align: 'center', width: 72,
      render: (v: number) => <Tag color={getScoreColor(v)}>{v}</Tag>,
    },
    { title: '推荐理由', dataIndex: 'reason', key: 'reason', ellipsis: true, width: 180,
      render: (v: string) => <Text type="secondary" style={{ fontSize: 12 }}>{v}</Text>,
    },
    {
      title: '操作', key: 'action', width: 80, align: 'center',
      render: (_: any, record: RecItem) => (
        <Button size="small" onClick={() => handleAddTracking(record.code, record.name)}>+跟踪</Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={2}>📋 股票推荐</Title>
          <Text type="secondary">基于多种策略自动筛选潜力股票</Text>
        </div>
        <Button
          type="primary"
          icon={<ReloadOutlined />}
          onClick={() => generateMutation.mutate()}
          loading={generateMutation.isPending}
        >
          {generateMutation.isPending ? "生成中..." : "立即生成"}
        </Button>
      </div>

      {/* Tabs */}
      <Segmented
        value={activeTab}
        onChange={(val) => setActiveTab(val as "daily" | "weekly")}
        options={[
          { label: '📅 每日推荐', value: 'daily' },
          { label: '📆 每周推荐', value: 'weekly' },
        ]}
      />

      {/* Loading */}
      {isLoading && (
        <Card><div style={{ textAlign: 'center', padding: 48 }}><Spin /></div></Card>
      )}

      {/* Empty */}
      {!isLoading && Object.keys(strategies).length === 0 && (
        <div style={{ textAlign: 'center', padding: 64 }}>
          <Text type="secondary" style={{ fontSize: 24, display: 'block', marginBottom: 8 }}>📭</Text>
          <Text type="secondary">暂无推荐数据</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>点击「立即生成」获取今日推荐</Text>
        </div>
      )}

      {/* Strategy Sections */}
      {Object.entries(strategies).map(([sname, items]) => {
        const recs = items as RecItem[];
        const bgColor = STRATEGY_BG_COLORS[sname] || '#f5f5f5';
        const borderColor = STRATEGY_BORDER_COLORS[sname] || '#d9d9d9';
        const textColor = STRATEGY_TEXT_COLORS[sname] || '#595959';
        return (
          <Card
            key={sname}
            styles={{ body: { padding: 0 } }}
            title={
              <Text strong style={{ color: textColor, fontSize: 16 }}>
                {STRATEGY_LABELS[sname] || sname}
              </Text>
            }
            style={{ borderLeft: `4px solid ${borderColor}` }}
          >
            <Table<RecItem>
              columns={recColumns}
              dataSource={recs}
              rowKey={(r) => `${r.id || r.code}`}
              pagination={false}
              size="small"
              scroll={{ x: 1000 }}
            />
          </Card>
        );
      })}

      {/* Generate result */}
      {generateMutation.data && (
        <Alert
          type="success"
          showIcon
          message={`✅ 生成完成！共 ${generateMutation.data.count} 条推荐，${generateMutation.data.total_unique} 只个股`}
        />
      )}
    </Space>
  );
}
