import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate, Link } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import TradeModal from "../components/TradeModal";
import { createChart, ColorType } from "lightweight-charts";
import {
  Card,
  Button,
  Table,
  Tag,
  Statistic,
  Modal,
  Form,
  Input,
  InputNumber,
  Select,
  Spin,
  Typography,
  Space,
  Row,
  Col,
  Pagination,
  message,
} from "antd";
import {
  ArrowLeftOutlined,
  PlusOutlined,
  CameraOutlined,
  EditOutlined,
  CloseCircleOutlined,
} from "@ant-design/icons";

const { Title, Text } = Typography;

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface Position {
  id: number; code: string; name: string; shares: number;
  avg_cost: number; current_price: number; market_value: number;
  profit_pct: number; today_profit_pct: number;
  etf_replaced: boolean; original_code: string | null;
}

interface Order {
  id: number; code: string; name: string; direction: string;
  price: number; quantity: number; amount: number;
  commission: number; tax: number; order_type: string;
  strategy_run_id: string | null; note: string | null; created_at: string;
}

interface Plan {
  id: number; code: string; name?: string; direction: string;
  target_price: number; quantity?: number; reason: string | null; status: string;
  created_at: string;
}

interface Summary {
  id: number; name: string; initial_capital: number;
  cash_balance: number; total_market_value: number;
  total_profit_pct: number; max_drawdown: number | null;
  win_rate: number | null; snapshot_interval: number;
  position_count: number; snapshot_count: number; order_count: number;
}

interface CurvePoint {
  snapshot_time: string; total_value: number;
  cash_balance: number; market_value: number;
  daily_pnl: number; daily_pnl_pct: number;
}

function formatMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + "亿";
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + "万";
  return v.toFixed(2);
}

function fmtPct(v: number | null): string {
  if (v == null) return "-";
  return (v >= 0 ? "+" : "") + v.toFixed(2) + "%";
}

const DIRECTION_OPTIONS = [
  { label: "买入", value: "buy" },
  { label: "卖出", value: "sell" },
];

export default function PaperDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const chartRef = useRef<HTMLDivElement>(null);
  const [showTrade, setShowTrade] = useState(false);
  const [ordersPage, setOrdersPage] = useState(1);
  const [editingInterval, setEditingInterval] = useState(false);
  const [newInterval, setNewInterval] = useState(60);
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [planModalCode, setPlanModalCode] = useState("");
  const [planDirection, setPlanDirection] = useState("buy");
  const [planTargetPrice, setPlanTargetPrice] = useState("");
  const [planReason, setPlanReason] = useState("");
  const [planForm] = Form.useForm();
  const [intervalForm] = Form.useForm();
  const accountId = parseInt(id || "0");

  const { data: summary, isLoading: summaryLoading } = useQuery({
    queryKey: ["paper-summary", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/summary`);
      if (!r.ok) throw new Error("获取摘要失败");
      const d = await r.json();
      return d.summary as Summary;
    },
    enabled: !!accountId,
    refetchInterval: 60000,
  });

  const { data: positions, isLoading: posLoading } = useQuery({
    queryKey: ["paper-positions", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/positions`);
      if (!r.ok) throw new Error("获取持仓失败");
      const d = await r.json();
      return d.positions as Position[];
    },
    enabled: !!accountId,
    refetchInterval: 30000,
  });

  const { data: ordersData } = useQuery({
    queryKey: ["paper-orders", accountId, ordersPage],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/orders?page=${ordersPage}&per_page=20`);
      if (!r.ok) throw new Error("获取订单失败");
      return r.json();
    },
    enabled: !!accountId,
  });

  const { data: curveData } = useQuery({
    queryKey: ["paper-curve", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/equity_curve?limit=200`);
      if (!r.ok) throw new Error("获取曲线失败");
      return r.json();
    },
    enabled: !!accountId,
  });

  const { data: plansData } = useQuery({
    queryKey: ["paper-plans", accountId],
    queryFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/plans/${accountId}`);
      if (!r.ok) throw new Error("获取计划失败");
      const d = await r.json();
      return d.plans as Plan[];
    },
    enabled: !!accountId,
    refetchInterval: 30000,
  });

  const snapshotMut = useMutation({
    mutationFn: async () => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}/snapshot`, { method: "POST" });
      if (!r.ok) throw new Error("快照失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-curve", accountId] });
      queryClient.invalidateQueries({ queryKey: ["paper-summary", accountId] });
      message.success("快照已更新");
    },
    onError: (err: Error) => {
      message.error(err.message);
    },
  });

  const intervalMut = useMutation({
    mutationFn: async (interval: number) => {
      const r = await fetch(`${API_BASE}/api/paper/accounts/${accountId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ snapshot_interval: interval }),
      });
      if (!r.ok) throw new Error("更新失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-summary", accountId] });
      setEditingInterval(false);
      message.success("快照间隔已更新");
    },
    onError: (err: Error) => {
      message.error(err.message);
    },
  });

  const createPlanMut = useMutation({
    mutationFn: async (data: { code: string; direction: string; target_price: number; reason: string }) => {
      const r = await fetch(`${API_BASE}/api/paper/plans/${accountId}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
      });
      if (!r.ok) throw new Error("创建计划失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-plans", accountId] });
      setPlanModalOpen(false);
      setPlanDirection("buy");
      setPlanTargetPrice("");
      setPlanReason("");
      planForm.resetFields();
      message.success("计划已创建");
    },
    onError: (err: Error) => {
      message.error(err.message);
    },
  });

  const cancelPlanMut = useMutation({
    mutationFn: async (planId: number) => {
      const r = await fetch(`${API_BASE}/api/paper/plans/${planId}/status`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: "cancelled" }),
      });
      if (!r.ok) throw new Error("取消计划失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-plans", accountId] });
      message.success("计划已取消");
    },
    onError: (err: Error) => {
      message.error(err.message);
    },
  });

  useEffect(() => {
    if (!chartRef.current || !curveData?.curve?.length) return;
    const isDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const chart = createChart(chartRef.current, {
      layout: {
        background: { type: ColorType.Solid, color: "transparent" },
        textColor: isDark ? "#9CA3AF" : "#6B7280",
      },
      grid: {
        vertLines: { color: isDark ? "#374151" : "#E5E7EB" },
        horzLines: { color: isDark ? "#374151" : "#E5E7EB" },
      },
      width: chartRef.current.clientWidth,
      height: 280,
      crosshair: { mode: 0 },
      timeScale: { timeVisible: true, secondsVisible: false },
    });
    const lineSeries = chart.addLineSeries({
      color: "#3B82F6",
      lineWidth: 2,
      crosshairMarkerVisible: true,
      priceFormat: { type: "custom", formatter: (v: number) => v.toFixed(2) },
    });
    const data = curveData.curve
      .slice()
      .reverse()
      .map((p: CurvePoint, i: number) => ({
        time: i as import("lightweight-charts").Time,
        value: p.total_value,
      }));
    lineSeries.setData(data);
    chart.timeScale().fitContent();
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        chart.applyOptions({ width: entry.contentRect.width });
      }
    });
    observer.observe(chartRef.current);
    return () => { observer.disconnect(); chart.remove(); };
  }, [curveData]);

  if (summaryLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", alignItems: "center", height: 256 }}>
        <Spin size="large" />
      </div>
    );
  }

  if (!summary) {
    return (
      <div style={{ textAlign: "center", padding: "64px 0" }}>
        <div style={{ fontSize: 48, marginBottom: 16 }}>📭</div>
        <Text type="secondary">模拟盘账户不存在</Text>
        <br />
        <Button type="primary" style={{ marginTop: 16 }} onClick={() => navigate("/paper")}>
          返回模拟盘列表
        </Button>
      </div>
    );
  }

  const totalValue = summary.cash_balance + summary.total_market_value;

  // Group plans by code
  const plansByCode: Record<string, Plan[]> = {};
  if (plansData) {
    for (const p of plansData) {
      if (!plansByCode[p.code]) plansByCode[p.code] = [];
      plansByCode[p.code].push(p);
    }
  }

  // Position table columns
  const positionColumns = [
    {
      title: "代码",
      dataIndex: "code",
      key: "code",
      render: (code: string, record: Position) => (
        <Space size={4}>
          <Link to={`/stock/${code}`}>
            <Text code>{code}</Text>
          </Link>
          {record.etf_replaced && <Tag color="gold">ETF</Tag>}
        </Space>
      ),
    },
    { title: "名称", dataIndex: "name", key: "name" },
    { title: "持股", dataIndex: "shares", key: "shares", align: "right" as const },
    {
      title: "均价",
      dataIndex: "avg_cost",
      key: "avg_cost",
      align: "right" as const,
      render: (v: number) => v.toFixed(2),
    },
    {
      title: "现价",
      dataIndex: "current_price",
      key: "current_price",
      align: "right" as const,
      render: (v: number) => v.toFixed(2),
    },
    {
      title: "市值",
      dataIndex: "market_value",
      key: "market_value",
      align: "right" as const,
      render: (v: number) => formatMoney(v),
    },
    {
      title: "盈亏",
      dataIndex: "profit_pct",
      key: "profit_pct",
      align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? "#cf1322" : "#3f8600" }} strong>
          {fmtPct(v)}
        </Text>
      ),
    },
    {
      title: "当日",
      dataIndex: "today_profit_pct",
      key: "today_profit_pct",
      align: "right" as const,
      render: (v: number) => (
        <Text style={{ color: v >= 0 ? "#cf1322" : "#3f8600" }} strong>
          {fmtPct(v)}
        </Text>
      ),
    },
    {
      title: "计划",
      key: "plans",
      render: (_: unknown, record: Position) => {
        const plans = plansByCode[record.code];
        if (plans?.length) {
          return (
            <Space size={4} wrap>
              {plans.map((pl) => {
                const isTakeProfit = pl.direction === "sell" && pl.status === "take_profit";
                const isStopLoss = pl.direction === "sell" && pl.status === "stop_loss";
                let color: string | undefined;
                let icon: string;
                if (isTakeProfit) { color = "red"; icon = "🔴"; }
                else if (isStopLoss) { color = "green"; icon = "🟢"; }
                else { color = "blue"; icon = "🔵"; }
                return (
                  <Tag key={pl.id} color={color}>
                    {icon} {pl.target_price.toFixed(2)}
                  </Tag>
                );
              })}
            </Space>
          );
        }
        return (
          <Button
            size="small"
            icon={<PlusOutlined />}
            onClick={() => {
              setPlanModalCode(record.code);
              setPlanDirection("buy");
              setPlanTargetPrice("");
              setPlanReason("");
              setPlanModalOpen(true);
            }}
          >
            添加计划
          </Button>
        );
      },
    },
  ];

  // Order table columns
  const orderColumns = [
    {
      title: "时间",
      dataIndex: "created_at",
      key: "created_at",
      render: (v: string) => new Date(v).toLocaleString("zh-CN"),
    },
    {
      title: "方向",
      dataIndex: "direction",
      key: "direction",
      render: (d: string) => (
        <Text style={{ color: d === "buy" ? "#cf1322" : "#3f8600" }} strong>
          {d === "buy" ? "买入" : "卖出"}
        </Text>
      ),
    },
    {
      title: "代码",
      dataIndex: "code",
      key: "code",
      render: (code: string) => <Text code>{code}</Text>,
    },
    { title: "名称", dataIndex: "name", key: "name" },
    {
      title: "价格",
      dataIndex: "price",
      key: "price",
      align: "right" as const,
      render: (v: number) => v.toFixed(2),
    },
    { title: "数量", dataIndex: "quantity", key: "quantity", align: "right" as const },
    {
      title: "金额",
      dataIndex: "amount",
      key: "amount",
      align: "right" as const,
      render: (v: number) => formatMoney(v),
    },
    {
      title: "类型",
      dataIndex: "order_type",
      key: "order_type",
      render: (t: string) => (
        <Tag>{t === "manual" ? "手动" : t === "signal" ? "信号" : t}</Tag>
      ),
    },
    {
      title: "备注",
      dataIndex: "note",
      key: "note",
      render: (n: string | null) => n || "-",
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8 }}>
          <Space>
            <Button
              icon={<ArrowLeftOutlined />}
              onClick={() => navigate("/paper")}
              type="text"
            />
            <Title level={3} style={{ margin: 0 }}>{summary.name}</Title>
          </Space>
          <Space>
            <Button
              icon={<CameraOutlined />}
              onClick={() => snapshotMut.mutate()}
              loading={snapshotMut.isPending}
            >
              {snapshotMut.isPending ? "更新中..." : "更新快照"}
            </Button>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setShowTrade(true)}
            >
              手动交易
            </Button>
          </Space>
        </div>

        {/* Summary Cards */}
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="总资产" value={formatMoney(totalValue)} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="可用现金" value={formatMoney(summary.cash_balance)} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic title="持仓市值" value={formatMoney(summary.total_market_value)} />
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Statistic
                title="总收益率"
                value={fmtPct(summary.total_profit_pct)}
                valueStyle={{
                  color: summary.total_profit_pct >= 0 ? "#cf1322" : "#3f8600",
                }}
              />
            </Card>
          </Col>
        </Row>

        {/* Secondary Stats */}
        <Row gutter={[16, 16]}>
          <Col xs={12} md={6}>
            <Card size="small">
              <Text type="secondary">初始资金</Text>
              <br />
              <Text strong>{formatMoney(summary.initial_capital)}</Text>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Text type="secondary">最大回撤</Text>
              <br />
              <Text strong>{fmtPct(summary.max_drawdown)}</Text>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <Text type="secondary">胜率</Text>
              <br />
              <Text strong>{fmtPct(summary.win_rate)}</Text>
            </Card>
          </Col>
          <Col xs={12} md={6}>
            <Card size="small">
              <div>
                <Text type="secondary">
                  快照间隔{" "}
                  <Button
                    type="link"
                    size="small"
                    icon={<EditOutlined />}
                    onClick={() => {
                      setNewInterval(summary.snapshot_interval);
                      intervalForm.setFieldsValue({ interval: summary.snapshot_interval });
                      setEditingInterval(true);
                    }}
                  >
                    编辑
                  </Button>
                </Text>
              </div>
              <Text strong>{summary.snapshot_interval} 分钟</Text>
            </Card>
          </Col>
        </Row>

        {/* Pending Buy Plans */}
        {(() => {
          const pendingBuys = plansData?.filter(p => p.direction === 'buy' && p.status === 'pending') || [];
          if (pendingBuys.length === 0) return null;
          const totalNeeded = pendingBuys.reduce((s, p) => s + (p.target_price * (p.quantity || 100)), 0);
          return (
            <Card
              title={`📋 待买入计划 (${pendingBuys.length})`}
              extra={
                <Text type="secondary" style={{ fontSize: 12 }}>
                  预计需 {formatMoney(totalNeeded)}（可用 {formatMoney(summary.cash_balance)}）
                </Text>
              }
            >
              {pendingBuys.map((p) => (
                <div
                  key={p.id}
                  style={{
                    display: "flex",
                    justifyContent: "space-between",
                    alignItems: "center",
                    padding: "12px 0",
                    borderBottom: "1px solid #f0f0f0",
                  }}
                >
                  <Space size={16}>
                    <Link to={`/stock/${p.code}`}>
                      <Text code strong>{p.code}</Text>
                    </Link>
                    <div>
                      <Text strong>{p.name || p.code}</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        目标 <Text type="danger" strong>¥{p.target_price.toFixed(2)}</Text>
                        {p.quantity ? ` · ${p.quantity}股 · 共${formatMoney(p.target_price * p.quantity)}` : ''}
                      </Text>
                      {p.reason && (
                        <div>
                          <Text type="secondary" style={{ fontSize: 12 }}>{p.reason}</Text>
                        </div>
                      )}
                      <div>
                        <Text type="secondary" style={{ fontSize: 11 }}>{p.created_at}</Text>
                      </div>
                    </div>
                  </Space>
                  <Space>
                    <Tag color="blue">待买入</Tag>
                    <Button
                      size="small"
                      danger
                      icon={<CloseCircleOutlined />}
                      onClick={() => cancelPlanMut.mutate(p.id)}
                      loading={cancelPlanMut.isPending}
                    />
                  </Space>
                </div>
              ))}
            </Card>
          );
        })()}

        {/* Edit Interval Modal */}
        <Modal
          title="设置快照间隔"
          open={editingInterval}
          onCancel={() => setEditingInterval(false)}
          onOk={() => intervalForm.submit()}
          confirmLoading={intervalMut.isPending}
          okText="保存"
          cancelText="取消"
        >
          <Form
            form={intervalForm}
            layout="vertical"
            onFinish={(values) => intervalMut.mutate(values.interval)}
          >
            <Form.Item
              name="interval"
              label="快照间隔（分钟）"
              rules={[{ required: true, message: "请输入快照间隔" }]}
            >
              <InputNumber style={{ width: "100%" }} min={0} max={1440} />
            </Form.Item>
            <Text type="secondary" style={{ fontSize: 12 }}>
              建议值: 15-240分钟，0=不自动快照
            </Text>
          </Form>
        </Modal>

        {/* Equity Curve */}
        <Card title="📈 收益曲线">
          {curveData?.curve?.length ? (
            <div ref={chartRef} style={{ width: "100%" }} />
          ) : (
            <div style={{ textAlign: "center", padding: "32px 0" }}>
              <Text type="secondary">暂无快照数据</Text>
              <br />
              <Text type="secondary" style={{ fontSize: 12 }}>
                点击「更新快照」开始记录收益曲线
              </Text>
            </div>
          )}
        </Card>

        {/* Positions Table */}
        <Card
          title={`📦 持仓 (${positions?.length || 0})`}
        >
          <Table
            dataSource={positions || []}
            columns={positionColumns}
            rowKey="id"
            loading={posLoading}
            pagination={false}
            size="small"
            locale={{ emptyText: "暂无持仓，点击「手动交易」开始模拟交易" }}
          />
        </Card>

        {/* Orders Table */}
        <Card
          title={`📝 交易记录 (${ordersData?.total || 0})`}
          extra={
            ordersData && (
              <Pagination
                current={ordersPage}
                total={ordersData.total || 0}
                pageSize={20}
                onChange={(page) => setOrdersPage(page)}
                size="small"
                showSizeChanger={false}
              />
            )
          }
        >
          <Table
            dataSource={ordersData?.orders || []}
            columns={orderColumns}
            rowKey="id"
            pagination={false}
            size="small"
            locale={{ emptyText: "暂无交易记录" }}
          />
        </Card>

        {showTrade && (
          <TradeModal
            accountId={accountId}
            onClose={() => setShowTrade(false)}
            onSuccess={() => {
              queryClient.invalidateQueries({ queryKey: ["paper-positions", accountId] });
              queryClient.invalidateQueries({ queryKey: ["paper-orders", accountId] });
              queryClient.invalidateQueries({ queryKey: ["paper-summary", accountId] });
              queryClient.invalidateQueries({ queryKey: ["paper-curve", accountId] });
            }}
          />
        )}

        {/* Add Plan Modal */}
        <Modal
          title={`添加买卖计划 - ${planModalCode}`}
          open={planModalOpen}
          onCancel={() => setPlanModalOpen(false)}
          onOk={() => planForm.submit()}
          confirmLoading={createPlanMut.isPending}
          okText="确认添加"
          cancelText="取消"
        >
          <Form
            form={planForm}
            layout="vertical"
            onFinish={(values) => {
              createPlanMut.mutate({
                code: planModalCode,
                direction: planDirection,
                target_price: parseFloat(values.target_price),
                reason: values.reason || "",
              });
            }}
          >
            <Form.Item label="方向">
              <Select
                value={planDirection}
                onChange={(v) => setPlanDirection(v)}
                options={DIRECTION_OPTIONS}
                style={{ width: "100%" }}
              />
            </Form.Item>
            <Form.Item
              label="目标价格"
              name="target_price"
              rules={[{ required: true, message: "请输入目标价格" }]}
            >
              <InputNumber style={{ width: "100%" }} min={0} step={0.01} precision={2} />
            </Form.Item>
            <Form.Item label="备注" name="reason">
              <Input placeholder="计划理由（可选）" />
            </Form.Item>
          </Form>
        </Modal>
      </Space>
  );
}
