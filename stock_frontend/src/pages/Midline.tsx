import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useState } from 'react';
import { Alert, Card, Table, Button, InputNumber, Space, Typography, Spin, Tag, Statistic, Modal, Form, Input, DatePicker, Tooltip, message } from 'antd';
import { PlusOutlined, DeleteOutlined, CalculatorOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';

const { Title, Text } = Typography;
const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

interface HealthItem {
  code: string;
  name: string;
  score: number;
  ma_score: number;
  macd_signal: string;
  rsi_score: number;
  trend: string;
  suggestion: string;
  error?: string;
  shares?: number | null;
  cost_price?: number | null;
  dl_direction?: string | null;
  dl_prob_up?: number | null;
  dl_prob_down?: number | null;
  dl_short_return?: number | null;
}

interface JournalItem {
  id: number;
  code: string;
  name: string;
  entry_date: string;
  entry_price: number;
  shares: number;
  stop_loss: number;
  exit_date: string | null;
  pnl: number | null;
  pnl_pct: number | null;
  reason_entry: string;
}

interface StatsData {
  total_trades: number;
  win_rate: number;
  wins: number;
  losses: number;
  total_pnl: number;
  profit_factor: number;
  max_win_streak: number;
  max_loss_streak: number;
  avg_win: number;
  avg_loss: number;
}

export default function Midline() {
  const queryClient = useQueryClient();
  const [healthPage, setHealthPage] = useState(1);
  const [healthPageSize, setHealthPageSize] = useState(20);
  const [journalPage, setJournalPage] = useState(1);
  const [journalPageSize, setJournalPageSize] = useState(15);

  // ═══ 自选池健康度 ═══
  const { data: healthData, isLoading: healthLoading, isError: healthIsError, error: healthError } = useQuery({
    queryKey: ['midline-health', healthPage, healthPageSize],
    queryFn: () => fetch(`${API}/api/midline/watchlist-health?page=${healthPage}&pageSize=${healthPageSize}`).then(r => r.json()),
    refetchInterval: 60000,
  });

  // ═══ 仓位计算器 ═══
  const [calcInput, setCalcInput] = useState({
    total_capital: 100000,
    risk_pct: 2,
    entry_price: 0,
    stop_loss_price: 0,
    target_price: 0,
    code: '',
    sector: '',
  });
  const [calcResult, setCalcResult] = useState<any>(null);
  const [calcLoading, setCalcLoading] = useState(false);

  // ═══ 仓位计算器 ═══
  const handleCalc = async () => {
    if (!calcInput.entry_price || !calcInput.stop_loss_price) {
      message.warning('请填写入场价和止损价');
      return;
    }
    setCalcLoading(true);
    try {
      const res = await fetch(`${API}/api/midline/position-calc`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(calcInput),
      });
      const data = await res.json();
      if (data.error) {
        message.error(data.error);
      } else {
        setCalcResult(data);
      }
    } catch {
      message.error('计算失败，请检查网络连接');
    }
    setCalcLoading(false);
  };

  // ═══ 交易日志 ═══
  const [journalFormVisible, setJournalFormVisible] = useState(false);
  const [journalForm] = Form.useForm();
  const [journalSubmitting, setJournalSubmitting] = useState(false);

  const { data: journalData, isLoading: journalLoading, isError: journalIsError } = useQuery({
    queryKey: ['midline-journal', journalPage, journalPageSize],
    queryFn: () => fetch(`${API}/api/midline/journal?page=${journalPage}&pageSize=${journalPageSize}`).then(r => r.json()),
  });

  const { data: statsData, isError: statsIsError } = useQuery({
    queryKey: ['midline-journal-stats'],
    queryFn: () => fetch(`${API}/api/midline/journal/stats`).then(r => r.json()),
  });

  const handleDelete = async (id: number) => {
    try {
      const res = await fetch(`${API}/api/midline/journal/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        message.error(data?.error || '删除失败');
        return;
      }
      queryClient.invalidateQueries({ queryKey: ['midline-journal'] });
      queryClient.invalidateQueries({ queryKey: ['midline-journal-stats'] });
      message.success('已删除');
    } catch (e: any) {
      message.error('网络错误，删除失败');
    }
  };

  const handleAddJournal = () => {
    journalForm.resetFields();
    journalForm.setFieldsValue({ shares: 100, entry_date: dayjs() });
    setJournalFormVisible(true);
  };

  const handleJournalSubmit = async () => {
    try {
      const values = await journalForm.validateFields();
      setJournalSubmitting(true);
      const body = {
        code: values.code,
        name: values.name,
        entry_date: values.entry_date.format('YYYY-MM-DD'),
        entry_price: values.entry_price,
        shares: values.shares,
        stop_loss: values.stop_loss || 0,
        reason_entry: values.reason_entry || '',
      };
      const res = await fetch(`${API}/api/midline/journal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData?.error || `HTTP ${res.status}`);
      }
      const data = await res.json();
      if (data.error) {
        message.error(data.error);
        return;
      }
      message.success('已添加');
      journalForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['midline-journal'] });
      queryClient.invalidateQueries({ queryKey: ['midline-journal-stats'] });
      setJournalFormVisible(false);
    } catch (e: any) {
      if (e?.errorFields) {
        // antd form validation error — handled by form
        return;
      }
      message.error(e?.message || '添加失败，请检查网络');
    } finally {
      setJournalSubmitting(false);
    }
  };

  const journals: JournalItem[] = journalData?.data || [];
  const journalTotal = journalData?.total || 0;
  const stats: StatsData = statsData?.data || {};
  const healthItems: HealthItem[] = healthData?.data || [];
  const healthTotal = healthData?.total || 0;

  // Health table columns
  const healthColumns: ColumnsType<HealthItem> = [
    {
      title: '代码', dataIndex: 'code', key: 'code',
      render: (code: string) => (
        <a href={`/stock/${code}`} style={{ fontFamily: 'monospace', color: '#1677ff' }}>{code}</a>
      ),
      width: 100,
    },
    {
      title: '名称', dataIndex: 'name', key: 'name',
      render: (name: string, record: HealthItem) => (
        <Space>
          <Text>{name}</Text>
          {record.shares && record.cost_price && (
            <Tag color="blue">持仓 {record.shares}股 @ ¥{record.cost_price.toFixed(2)}</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '评分', dataIndex: 'score', key: 'score', align: 'right',
      render: (score: number, record: HealthItem) => {
        if (record.error) {
          return (
            <Tooltip title={record.error}>
              <Tag color="red">错误</Tag>
            </Tooltip>
          );
        }
        return (
          <Text strong style={{
            fontSize: 18,
            color: score >= 70 ? '#52c41a' : score >= 40 ? '#faad14' : '#ff4d4f',
          }}>{score}</Text>
        );
      },
      width: 80,
    },
    {
      title: 'DL预测',
      key: 'dl_pred',
      width: 130,
      render: (_: any, record: HealthItem) => {
        if (!record.dl_direction) {
          return <Text type="secondary" style={{ fontSize: 12 }}>—</Text>;
        }
        const dirColor = record.dl_direction === 'up' ? '#cf1322'
          : record.dl_direction === 'down' ? '#1677ff' : '#999';
        const dirLabel = record.dl_direction === 'up' ? '↑涨'
          : record.dl_direction === 'down' ? '↓跌' : '→平';
        const prob = record.dl_direction === 'up' ? record.dl_prob_up
          : record.dl_direction === 'down' ? record.dl_prob_down
          : record.dl_prob_up;
        return (
          <Tooltip title={`预期收益: ${(record.dl_short_return || 0).toFixed(2)}%`}>
            <Space size={4}>
              <Text strong style={{ color: dirColor, fontSize: 13 }}>{dirLabel}</Text>
              {prob != null && (
                <Text style={{ fontSize: 11, color: '#666' }}>
                  {(prob * 100).toFixed(0)}%
                </Text>
              )}
            </Space>
          </Tooltip>
        );
      },
    },
    { title: '均线', dataIndex: 'ma_score', key: 'ma_score', align: 'center', render: (v: number) => `${v}分`, width: 80 },
    { title: 'MACD', dataIndex: 'macd_signal', key: 'macd_signal', align: 'center', width: 80 },
    { title: 'RSI', dataIndex: 'rsi_score', key: 'rsi_score', align: 'center', render: (v: number) => `${v}分`, width: 80 },
    { title: '趋势', dataIndex: 'trend', key: 'trend', width: 80 },
    { title: '建议', dataIndex: 'suggestion', key: 'suggestion', width: 100 },
  ];

  // Journal table columns
  const journalColumns: ColumnsType<JournalItem> = [
    {
      title: '代码', dataIndex: 'code', key: 'code',
      render: (code: string, record: JournalItem) => (
        <a href={`/stock/${code}`} style={{ fontFamily: 'monospace' }}>{code} {record.name}</a>
      ),
      width: 120,
    },
    { title: '入场日', dataIndex: 'entry_date', key: 'entry_date', width: 110 },
    { title: '入场价', dataIndex: 'entry_price', key: 'entry_price', align: 'right', render: (v: number) => `¥${v}`, width: 90 },
    { title: '股数', dataIndex: 'shares', key: 'shares', align: 'right', width: 70 },
    { title: '止损', dataIndex: 'stop_loss', key: 'stop_loss', align: 'right', render: (v: number) => <Text style={{ color: '#ff4d4f' }}>¥{v}</Text>, width: 90 },
    { title: '出场日', dataIndex: 'exit_date', key: 'exit_date', render: (v: string | null) => v || '—', width: 110 },
    {
      title: '盈亏', dataIndex: 'pnl', key: 'pnl', align: 'right',
      render: (pnl: number | null, record: JournalItem) => {
        if (pnl == null) return <Text>—</Text>;
        return <Text style={{ color: pnl >= 0 ? '#52c41a' : '#ff4d4f' }}>¥{pnl} ({record.pnl_pct}%)</Text>;
      },
      width: 130,
    },
    { title: '理由', dataIndex: 'reason_entry', key: 'reason_entry', ellipsis: true, width: 150 },
    {
      title: '', key: 'action', width: 50,
      render: (_: any, record: JournalItem) => (
        <Button type="link" danger size="small" icon={<DeleteOutlined />} onClick={() => handleDelete(record.id)} />
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={2}>📊 中长线交易看板</Title>

      {/* ═══════════ 自选池健康度 ═══════════ */}
      <Card
        title={<Text strong>📋 自选池趋势健康度</Text>}
        extra={<Text type="secondary" style={{ fontSize: 12 }}>基于均线排列+MACD+RSI 综合评分，满分100</Text>}
      >
        {healthLoading ? (
          <div style={{ textAlign: 'center', padding: 32 }}><Spin /></div>
        ) : healthIsError ? (
          <Alert type="error" message="健康数据加载失败" description={(healthError as any)?.message || '请检查网络连接'} />
        ) : (
          <Table<HealthItem>
            columns={healthColumns}
            dataSource={healthItems}
            rowKey="code"
            pagination={{
              current: healthPage,
              pageSize: healthPageSize,
              total: healthTotal,
              showSizeChanger: true,
              showTotal: (total: number) => `共 ${total} 只`,
              onChange: (p: number, ps: number) => {
                setHealthPage(p);
                setHealthPageSize(ps);
              },
            }}
            size="small"
            scroll={{ x: 900 }}
          />
        )}
      </Card>

      {/* ═══════════ 仓位计算器 + 统计 ═══════════ */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* 仓位计算器 */}
        <Card title={<Text strong>🧮 仓位计算器</Text>}>
          <Space direction="vertical" style={{ width: '100%' }}>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>总资金</Text>
                <InputNumber
                  style={{ width: '100%' }}
                  value={calcInput.total_capital}
                  onChange={v => setCalcInput({ ...calcInput, total_capital: v || 0 })}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>每笔风险(%)</Text>
                <InputNumber
                  style={{ width: '100%' }}
                  value={calcInput.risk_pct}
                  onChange={v => setCalcInput({ ...calcInput, risk_pct: v || 0 })}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>入场价</Text>
                <InputNumber
                  style={{ width: '100%' }}
                  value={calcInput.entry_price || undefined}
                  onChange={v => setCalcInput({ ...calcInput, entry_price: v || 0 })}
                  step={0.01}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>止损价</Text>
                <InputNumber
                  style={{ width: '100%' }}
                  value={calcInput.stop_loss_price || undefined}
                  onChange={v => setCalcInput({ ...calcInput, stop_loss_price: v || 0 })}
                  step={0.01}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>目标价(可选)</Text>
                <InputNumber
                  style={{ width: '100%' }}
                  value={calcInput.target_price || undefined}
                  onChange={v => setCalcInput({ ...calcInput, target_price: v || 0 })}
                  step={0.01}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>股票代码(可选)</Text>
                <Input
                  style={{ width: '100%' }}
                  value={calcInput.code}
                  onChange={e => setCalcInput({ ...calcInput, code: e.target.value })}
                  placeholder="000001"
                  maxLength={6}
                />
              </div>
              <div>
                <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>所属板块(可选)</Text>
                <Input
                  style={{ width: '100%' }}
                  value={calcInput.sector}
                  onChange={e => setCalcInput({ ...calcInput, sector: e.target.value })}
                  placeholder="Other"
                />
              </div>
            </div>
            <Button type="primary" block onClick={handleCalc} loading={calcLoading} icon={<CalculatorOutlined />}>
              计算仓位
            </Button>
            {calcResult && !calcResult.error && (
              <div style={{
                background: '#e6f4ff', padding: 16, borderRadius: 8, marginTop: 8,
              }}>
                <Space direction="vertical" style={{ width: '100%' }} size="small">
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text type="secondary">建议买入</Text>
                    <Text strong style={{ fontSize: 18, color: '#1677ff' }}>{calcResult.suggested_shares} 股</Text>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text type="secondary">占用资金</Text>
                    <Text>¥{calcResult.position_value?.toLocaleString()} ({calcResult.position_pct}%)</Text>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text type="secondary">最大亏损</Text>
                    <Text style={{ color: '#ff4d4f' }}>¥{calcResult.max_loss_amount?.toLocaleString()}</Text>
                  </div>
                  {calcResult.risk_reward_ratio && (
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                      <Text type="secondary">盈亏比</Text>
                      <Text strong style={{ color: calcResult.risk_reward_ratio >= 2 ? '#52c41a' : '#faad14' }}>
                        1:{calcResult.risk_reward_ratio}
                      </Text>
                    </div>
                  )}
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>每股价差</Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>¥{calcResult.risk_per_share}</Text>
                  </div>
                </Space>
                {calcResult?.risk_check && !calcResult.risk_check.passed && (
                  <Alert
                    type="warning"
                    message="AI风控提示"
                    description={
                      <ul style={{ margin: 0, paddingLeft: 16 }}>
                        {calcResult.risk_check.violations?.map((v: string, i: number) => (
                          <li key={i}>{v}</li>
                        ))}
                      </ul>
                    }
                    style={{ marginTop: 8 }}
                  />
                )}
                {calcResult?.risk_check?.passed && (
                  <Alert type="success" message="AI风控检查通过" style={{ marginTop: 8 }} />
                )}
              </div>
            )}
          </Space>
        </Card>

        {/* 交易统计 */}
        <Card title={<Text strong>📈 交易统计</Text>}>
          {statsIsError ? (
            <Alert type="error" message="交易统计加载失败" description="请检查网络连接" />
          ) : stats.total_trades > 0 ? (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Statistic title="总交易" value={stats.total_trades} />
              <Statistic title="胜率" value={stats.win_rate} suffix="%"
                valueStyle={{ color: stats.win_rate >= 50 ? '#52c41a' : '#ff4d4f' }} />
              <Statistic title="盈利次数" value={stats.wins} />
              <Statistic title="亏损次数" value={stats.losses} />
              <Statistic title="累计盈亏" value={`¥${(stats.total_pnl || 0).toLocaleString()}`}
                valueStyle={{ color: (stats.total_pnl || 0) >= 0 ? '#52c41a' : '#ff4d4f' }} />
              <Statistic title="盈亏比" value={`1:${stats.profit_factor}`}
                valueStyle={{ color: (stats.profit_factor || 0) >= 1.5 ? '#52c41a' : '#faad14' }} />
              <Statistic title="最大连胜" value={stats.max_win_streak} />
              <Statistic title="最大连败" value={stats.max_loss_streak}
                valueStyle={{ color: '#ff4d4f' }} />
              <Statistic title="均盈" value={`¥${(stats.avg_win || 0).toLocaleString()}`}
                valueStyle={{ color: '#52c41a' }} />
              <Statistic title="均亏" value={`¥${(stats.avg_loss || 0).toLocaleString()}`}
                valueStyle={{ color: '#ff4d4f' }} />
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: 32 }}>
              <Text type="secondary">暂无交易记录，开始记录你的第一笔交易吧</Text>
            </div>
          )}
        </Card>
      </div>

      {/* ═══════════ 交易日志 ═══════════ */}
      <Card
        title={<Text strong>📝 交易日志</Text>}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleAddJournal}>记录交易</Button>}
      >
        {/* ═══════════ 内联交易日志表单 ═══════════ */}
        {journalFormVisible && (
          <Card
            title="📝 记录新交易"
            size="small"
            extra={
              <Button type="link" onClick={() => setJournalFormVisible(false)}>
                收起
              </Button>
            }
            style={{ marginBottom: 16, borderLeft: '3px solid #1677ff' }}
          >
            <Form form={journalForm} layout="vertical">
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                <Form.Item name="code" label="股票代码" rules={[{ required: true, message: '请输入' }]}>
                  <Input placeholder="000001" maxLength={6} />
                </Form.Item>
                <Form.Item name="name" label="股票名称">
                  <Input placeholder="平安银行" />
                </Form.Item>
              </div>
              <Form.Item name="entry_date" label="入场日期" rules={[{ required: true }]}>
                <DatePicker style={{ width: '100%' }} />
              </Form.Item>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12 }}>
                <Form.Item name="entry_price" label="入场价格" rules={[{ required: true, message: '请输入' }]}>
                  <InputNumber style={{ width: '100%' }} step={0.01} min={0.01} />
                </Form.Item>
                <Form.Item name="shares" label="股数" rules={[{ required: true, message: '请输入' }]}>
                  <InputNumber style={{ width: '100%' }} min={100} step={100} />
                </Form.Item>
                <Form.Item name="stop_loss" label="止损价">
                  <InputNumber style={{ width: '100%' }} step={0.01} min={0} />
                </Form.Item>
              </div>
              <Form.Item name="reason_entry" label="入场理由">
                <Input.TextArea rows={2} placeholder="简要记录入场原因" />
              </Form.Item>
              <Space>
                <Button type="primary" onClick={handleJournalSubmit} loading={journalSubmitting}>
                  提交记录
                </Button>
                <Button onClick={() => setJournalFormVisible(false)}>
                  取消
                </Button>
              </Space>
            </Form>
          </Card>
        )}
        {journalLoading ? (
          <div style={{ textAlign: 'center', padding: 32 }}><Spin /></div>
        ) : journalIsError ? (
          <Alert type="error" message="交易日志加载失败" description="请检查网络连接" />
        ) : journals.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 32 }}>
            <Text type="secondary">暂无记录</Text>
          </div>
        ) : (
          <Table<JournalItem>
            columns={journalColumns}
            dataSource={journals}
            rowKey="id"
            pagination={{
              current: journalPage,
              pageSize: journalPageSize,
              total: journalTotal,
              showSizeChanger: true,
              showTotal: (total: number) => `共 ${total} 条`,
              onChange: (p: number, ps: number) => {
                setJournalPage(p);
                setJournalPageSize(ps);
              },
            }}
            size="small"
            scroll={{ x: 1000 }}
          />
        )}
      </Card>
    </Space>
  );
}
