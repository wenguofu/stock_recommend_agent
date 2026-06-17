import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  Card,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  Checkbox,
  Tag,
  Statistic,
  Spin,
  Typography,
  Space,
  Row,
  Col,
  message,
} from "antd";
import { PlusOutlined, DeleteOutlined, EyeOutlined } from "@ant-design/icons";

const { Title, Text } = Typography;

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:35000";

interface PaperAccount {
  id: number;
  name: string;
  strategy_id: number | null;
  initial_capital: number;
  cash_balance: number;
  total_market_value: number;
  total_profit_pct: number;
  max_drawdown: number | null;
  win_rate: number | null;
  snapshot_interval: number;
  include_etf_replacement: boolean;
  enabled: boolean;
  created_at: string;
  position_count?: number;
}

function formatCurrency(value: number): string {
  if (Math.abs(value) >= 100000000) {
    return (value / 100000000).toFixed(2) + "亿";
  }
  if (Math.abs(value) >= 10000) {
    return (value / 10000).toFixed(2) + "万";
  }
  return value.toFixed(2);
}

function formatPercent(value: number | null): string {
  if (value === null || value === undefined) return "-";
  return (value >= 0 ? "+" : "") + value.toFixed(2) + "%";
}

export default function PaperAccounts() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [showCreate, setShowCreate] = useState(false);
  const [showDelete, setShowDelete] = useState<number | null>(null);
  const [createForm] = Form.useForm();

  const { data, isLoading, error } = useQuery({
    queryKey: ["paper-accounts"],
    queryFn: async () => {
      const res = await fetch(`${API_BASE}/api/paper/accounts`);
      if (!res.ok) throw new Error("获取模拟盘列表失败");
      const json = await res.json();
      return json.accounts as PaperAccount[];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (values: {
      name: string;
      initial_capital: number;
      snapshot_interval: number;
      include_etf_replacement: boolean;
    }) => {
      const res = await fetch(`${API_BASE}/api/paper/accounts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(values),
      });
      if (!res.ok) throw new Error("创建失败");
      return res.json();
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-accounts"] });
      setShowCreate(false);
      createForm.resetFields();
      message.success("创建成功");
    },
    onError: (err: Error) => {
      message.error(err.message);
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const res = await fetch(`${API_BASE}/api/paper/accounts/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("删除失败");
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["paper-accounts"] });
      setShowDelete(null);
      message.success("删除成功");
    },
    onError: (err: Error) => {
      message.error(err.message);
    },
  });

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
        {/* Header */}
        <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 12 }}>
          <div>
            <Title level={2} style={{ margin: 0 }}>模拟盘</Title>
            <Text type="secondary">管理模拟交易账户，跟踪验证量化策略</Text>
          </div>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setShowCreate(true)}>
            新建模拟盘
          </Button>
        </div>

        {/* Loading */}
        {isLoading && (
          <div style={{ textAlign: "center", padding: "48px 0" }}>
            <Spin size="large" />
            <div style={{ marginTop: 12 }}>
              <Text type="secondary">加载中...</Text>
            </div>
          </div>
        )}

        {/* Error */}
        {error && (
          <Card style={{ borderColor: "#ff4d4f", backgroundColor: "#fff2f0" }}>
            <Text type="danger">加载失败: {(error as Error).message}</Text>
          </Card>
        )}

        {/* Top-3 quick ranking */}
        {data && data.length >= 3 && (
          <Card
            title={<Space><span>🏆</span><span>收益排名 TOP 3</span></Space>}
            extra={
              <Button type="link" onClick={() => navigate('/paper/rankings')}>
                查看完整排名 →
              </Button>
            }
            size="small"
          >
            <Row gutter={[16, 16]}>
              {(() => {
                const top3 = [...data]
                  .sort((a, b) => (b.total_profit_pct ?? 0) - (a.total_profit_pct ?? 0))
                  .slice(0, 3);
                const medals = ['🥇', '🥈', '🥉'];
                return top3.map((acct, idx) => (
                  <Col xs={24} md={8} key={acct.id}>
                    <Card size="small" hoverable onClick={() => navigate(`/paper/${acct.id}`)}>
                      <Space align="center">
                        <span style={{ fontSize: 24 }}>{medals[idx]}</span>
                        <div>
                          <div style={{ fontWeight: 600 }}>{acct.name}</div>
                          <div
                            style={{
                              color: acct.total_profit_pct >= 0 ? '#cf1322' : '#3f8600',
                              fontSize: 18,
                              fontWeight: 700,
                            }}
                          >
                            {(acct.total_profit_pct >= 0 ? '+' : '') +
                              acct.total_profit_pct.toFixed(2) + '%'}
                          </div>
                        </div>
                      </Space>
                    </Card>
                  </Col>
                ));
              })()}
            </Row>
          </Card>
        )}

        {/* Empty */}
        {data && data.length === 0 && !isLoading && (
          <div style={{ textAlign: "center", padding: "64px 0" }}>
            <div style={{ fontSize: 48, marginBottom: 16 }}>📊</div>
            <Title level={4}>还没有模拟盘账户</Title>
            <Text type="secondary" style={{ display: "block", marginBottom: 24 }}>
              创建一个模拟盘账户来开始跟踪你的策略表现
            </Text>
            <Button type="primary" onClick={() => setShowCreate(true)}>
              创建第一个模拟盘
            </Button>
          </div>
        )}

        {/* Account Cards Grid */}
        {data && data.length > 0 && (
          <Row gutter={[16, 16]}>
            {data.map((account) => (
              <Col xs={24} md={12} lg={8} key={account.id}>
                <Card
                  hoverable
                  onClick={() => navigate(`/paper/${account.id}`)}
                  title={
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <span style={{ fontWeight: 600, fontSize: 16 }}>{account.name}</span>
                      <Space size={4}>
                        {account.strategy_id && <Tag color="purple">策略盘</Tag>}
                        {!account.enabled && <Tag>已停用</Tag>}
                      </Space>
                    </div>
                  }
                  actions={[
                    <Button
                      type="link"
                      icon={<EyeOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        navigate(`/paper/${account.id}`);
                      }}
                      key="view"
                    >
                      查看详情
                    </Button>,
                    <Button
                      type="link"
                      danger
                      icon={<DeleteOutlined />}
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowDelete(account.id);
                      }}
                      key="delete"
                    >
                      删除
                    </Button>,
                  ]}
                >
                  <Space direction="vertical" style={{ width: "100%" }} size="middle">
                    <Statistic
                      title="总资产"
                      value={formatCurrency(account.cash_balance + account.total_market_value)}
                      valueStyle={{ fontSize: 24 }}
                    />
                    <Row gutter={16}>
                      <Col span={12}>
                        <Statistic
                          title="收益率"
                          value={formatPercent(account.total_profit_pct)}
                          valueStyle={{
                            color: account.total_profit_pct >= 0 ? "#cf1322" : "#3f8600",
                            fontSize: 18,
                          }}
                        />
                      </Col>
                      <Col span={12}>
                        <Statistic
                          title="持仓数"
                          value={account.position_count ?? 0}
                          suffix="只"
                          valueStyle={{ fontSize: 18 }}
                        />
                      </Col>
                    </Row>
                    <Row gutter={16}>
                      <Col span={12}>
                        <Text type="secondary">初始资金</Text>
                        <br />
                        <Text strong>{formatCurrency(account.initial_capital)}</Text>
                      </Col>
                      <Col span={12}>
                        <Text type="secondary">最大回撤 / 胜率</Text>
                        <br />
                        <Text strong>
                          {formatPercent(account.max_drawdown)} / {formatPercent(account.win_rate)}
                        </Text>
                      </Col>
                    </Row>
                  </Space>
                </Card>
              </Col>
            ))}
          </Row>
        )}

        {/* Create Modal */}
        <Modal
          title="新建模拟盘账户"
          open={showCreate}
          onCancel={() => setShowCreate(false)}
          onOk={() => createForm.submit()}
          confirmLoading={createMutation.isPending}
          okText="创建"
          cancelText="取消"
        >
          <Form
            form={createForm}
            layout="vertical"
            initialValues={{
              name: "",
              initial_capital: 1000000,
              snapshot_interval: 60,
              include_etf_replacement: true,
            }}
            onFinish={(values) => createMutation.mutate(values)}
          >
            <Form.Item
              label="账户名称"
              name="name"
              rules={[{ required: true, message: "请输入账户名称" }]}
            >
              <Input placeholder="例如: 游资策略盘" />
            </Form.Item>
            <Form.Item
              label="初始资金"
              name="initial_capital"
              rules={[{ required: true, message: "请输入初始资金" }]}
            >
              <InputNumber
                style={{ width: "100%" }}
                min={0}
                step={10000}
                formatter={(value) => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ",")}
                parser={(value) => Number(value?.replace(/,/g, "")) as unknown as 0}
              />
            </Form.Item>
            <Form.Item
              label="快照间隔（分钟）"
              name="snapshot_interval"
              rules={[{ required: true, message: "请输入快照间隔" }]}
            >
              <InputNumber style={{ width: "100%" }} min={0} max={1440} />
            </Form.Item>
            <Form.Item name="include_etf_replacement" valuePropName="checked">
              <Checkbox>自动将科创板股票替换为ETF</Checkbox>
            </Form.Item>
          </Form>
        </Modal>

        {/* Delete Confirmation */}
        <Modal
          title="确认删除"
          open={showDelete !== null}
          onCancel={() => setShowDelete(null)}
          onOk={() => {
            if (showDelete !== null) deleteMutation.mutate(showDelete);
          }}
          confirmLoading={deleteMutation.isPending}
          okText="确认删除"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <p>删除后该模拟盘的所有持仓、交易记录和快照将被永久删除。</p>
          <Text type="danger">此操作不可撤销！</Text>
        </Modal>
      </Space>
  );
}
