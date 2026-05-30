import { useQuery, useQueryClient } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import { Button, Card, Table, Tag, Select, Modal, Form, Input, Space, Typography, Spin, Empty, Checkbox, Alert } from 'antd';
import { ReloadOutlined, WarningOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';

const { Title, Text } = Typography;

interface StrongStock {
  code: string;
  name: string;
  t1_limit_time: string;
  t2_limit_time: string;
  consecutive_days: number;
  break_count: number;
  industry: string;
  current_price: number | null;
  change_percent: number | null;
  volume: number | null;
  amount: number | null;
}

interface StrongStocksResponse {
  strategy: string;
  description: string;
  params: {
    limit_time: string;
  };
  trade_dates: {
    T: string;
    'T-1': string;
    'T-2': string;
  };
  count: number;
  stocks: StrongStock[];
}

const TIME_OPTIONS = [
  '09:30', '09:45', '10:00', '10:15', '10:30', '10:45',
  '11:00', '11:15', '11:30', '13:00', '13:30', '14:00', '14:30', '15:00'
];

export default function Strategy() {
  const [limitTime, setLimitTime] = useState('11:30');
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [showMultiModal, setShowMultiModal] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);
  const [multiMode, setMultiMode] = useState<'fast' | 'balanced' | 'deep'>('fast');
  const [multiError, setMultiError] = useState<string | null>(null);
  const [addingMap, setAddingMap] = useState<Record<string, boolean>>({});
  const [addedMap, setAddedMap] = useState<Record<string, boolean>>({});
  const [showPaperModal, setShowPaperModal] = useState(false);
  const [selectedPaperAccountId, setSelectedPaperAccountId] = useState<number | null>(null);
  const [paperQuantity, setPaperQuantity] = useState<string>('');
  const [paperTargetStock, setPaperTargetStock] = useState<{ code: string; name: string; currentPrice: number | null } | null>(null);
  const [paperLoading, setPaperLoading] = useState(false);
  const [paperError, setPaperError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  const { data, isLoading, error, refetch, isFetching } = useQuery<StrongStocksResponse>({
    queryKey: ['strong-stocks', limitTime],
    queryFn: () => stockAPI.getStrongStocks(limitTime),
    refetchInterval: 60000,
  });

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => stockAPI.getAgents(true),
    enabled: showMultiModal,
  });

  useEffect(() => {
    if (showMultiModal && agents && agents.length > 0 && selectedAgentIds.length === 0) {
      setSelectedAgentIds(agents.map((agent) => agent.id));
    }
  }, [showMultiModal, agents, selectedAgentIds.length]);

  const { data: paperAccounts, isLoading: paperAccountsLoading } = useQuery({
    queryKey: ['paper-accounts'],
    queryFn: async () => {
      const r = await fetch(`${stockAPI.getBaseURL()}/api/paper/accounts`);
      if (!r.ok) throw new Error('获取模拟盘账户列表失败');
      const d = await r.json();
      return d.accounts as any[];
    },
    enabled: showPaperModal,
  });

  useEffect(() => {
    if (showPaperModal && paperAccounts && paperAccounts.length > 0) {
      setSelectedPaperAccountId((prev) => prev ?? paperAccounts[0].id);
    }
  }, [showPaperModal, paperAccounts]);

  const formatNumber = (num: number | null | undefined): string => {
    if (num === null || num === undefined) return '-';
    if (num >= 100000000) {
      return (num / 100000000).toFixed(2) + '亿';
    } else if (num >= 10000) {
      return (num / 10000).toFixed(2) + '万';
    }
    return num.toFixed(2);
  };

  const formatLimitTime = (time: string | null | undefined): string => {
    if (!time) return '-';
    const str = String(time);
    if (str.includes(':')) return str;
    if (str.length === 6) {
      return `${str.slice(0, 2)}:${str.slice(2, 4)}:${str.slice(4, 6)}`;
    } else if (str.length === 5) {
      return `0${str.slice(0, 1)}:${str.slice(1, 3)}:${str.slice(3, 5)}`;
    }
    return str;
  };

  const toggleSelectCode = (code: string) => {
    setSelectedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleAddWatchlist = async (code: string, name: string) => {
    if (addingMap[code]) return;
    setAddingMap((prev) => ({ ...prev, [code]: true }));
    try {
      await stockAPI.addWatchlist(code, name);
      setAddedMap((prev) => ({ ...prev, [code]: true }));
    } catch (e) {
      console.error('加入自选失败:', e);
      alert('加入自选失败');
    } finally {
      setAddingMap((prev) => ({ ...prev, [code]: false }));
    }
  };

  const handleOpenMulti = () => {
    if (selectedCodes.length < 2) {
      setMultiError('请至少勾选2只股票');
      return;
    }
    setMultiError(null);
    setShowMultiModal(true);
  };

  const handleStartMulti = async () => {
    if (selectedCodes.length < 2) {
      setMultiError('请至少勾选2只股票');
      return;
    }
    if (selectedAgentIds.length < 2) {
      setMultiError('至少选择2个Agent参与辩论');
      return;
    }
    setMultiError(null);
    try {
      const modeConfig = {
        fast: { analysisRounds: 1, debateRounds: 1 },
        balanced: { analysisRounds: 2, debateRounds: 1 },
        deep: { analysisRounds: 3, debateRounds: 2 },
      }[multiMode];
      const res = await stockAPI.startMultiSelectDebate(
        selectedCodes,
        selectedAgentIds,
        modeConfig.analysisRounds,
        modeConfig.debateRounds
      );
      setShowMultiModal(false);
      const params = new URLSearchParams();
      params.set('job_id', res.job_id);
      params.set('code', selectedCodes.join(','));
      navigate(`/ai-debate?${params.toString()}`);
    } catch (e) {
      console.error('多选一任务启动失败:', e);
      setMultiError('启动多选一任务失败，请稍后重试');
    }
  };

  const handleOpenPaperPlan = (stock: StrongStock) => {
    setPaperTargetStock({ code: stock.code, name: stock.name, currentPrice: stock.current_price });
    setSelectedPaperAccountId(null);
    setPaperQuantity('');
    setPaperError(null);
    setShowPaperModal(true);
  };

  const handleSubmitPaperPlan = async () => {
    if (!paperTargetStock || !selectedPaperAccountId) {
      setPaperError('请选择模拟盘账户');
      return;
    }
    setPaperLoading(true);
    setPaperError(null);
    try {
      await stockAPI.batchCreatePlans(
        selectedPaperAccountId,
        paperTargetStock.code,
        paperTargetStock.name,
        paperTargetStock.currentPrice ?? undefined
      );
      setShowPaperModal(false);
      queryClient.invalidateQueries({ queryKey: ['paper-accounts'] });
      alert(`已为 ${paperTargetStock.name} (${paperTargetStock.code}) 创建模拟盘计划`);
    } catch (e) {
      console.error('创建计划失败:', e);
      setPaperError('创建计划失败，请稍后重试');
    } finally {
      setPaperLoading(false);
    }
  };

  const columns: ColumnsType<StrongStock> = [
    {
      title: '勾选',
      key: 'select',
      width: 60,
      render: (_, record) => (
        <Checkbox
          checked={selectedCodes.includes(record.code)}
          onChange={() => toggleSelectCode(record.code)}
        />
      ),
    },
    { title: '代码', dataIndex: 'code', key: 'code' },
    { title: '名称', dataIndex: 'name', key: 'name' },
    { title: '行业', dataIndex: 'industry', key: 'industry', render: (v) => v || '-' },
    { title: 'T-1涨停', dataIndex: 't1_limit_time', key: 't1_limit_time', render: (v) => formatLimitTime(v) },
    { title: 'T-2涨停', dataIndex: 't2_limit_time', key: 't2_limit_time', render: (v) => formatLimitTime(v) },
    {
      title: '连板',
      dataIndex: 'consecutive_days',
      key: 'consecutive_days',
      render: (v) => v > 0 ? <Tag color="red">{v}连板</Tag> : '-',
    },
    {
      title: '炸板',
      dataIndex: 'break_count',
      key: 'break_count',
      render: (v) => v > 0 ? <Tag color="gold">{v}次</Tag> : '-',
    },
    {
      title: '当前价',
      key: 'current_price',
      render: (_, record) => record.current_price ? `¥${record.current_price.toFixed(2)}` : '-',
    },
    {
      title: '涨跌幅',
      key: 'change_percent',
      render: (_, record) =>
        record.change_percent !== null ? (
          <Text style={{ color: record.change_percent >= 0 ? '#ff4d4f' : '#52c41a' }}>
            {record.change_percent >= 0 ? '+' : ''}{record.change_percent.toFixed(2)}%
          </Text>
        ) : '-',
    },
    { title: '成交量', dataIndex: 'volume', key: 'volume', render: (v) => formatNumber(v) },
    {
      title: '操作',
      key: 'actions',
      render: (_, record) => (
        <Space>
          <Link to={`/stock/${record.code}`}>
            <Button type="primary" size="small">详情</Button>
          </Link>
          <Button
            size="small"
            style={{ background: '#10b981', borderColor: '#10b981' }}
            disabled={addingMap[record.code] || addedMap[record.code]}
            onClick={() => handleAddWatchlist(record.code, record.name)}
          >
            {addedMap[record.code] ? '已加入' : addingMap[record.code] ? '加入中' : '加入自选'}
          </Button>
          <Button
            size="small"
            style={{ background: '#f97316', borderColor: '#f97316' }}
            onClick={() => handleOpenPaperPlan(record)}
          >
            📋 计划
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24, padding: '0 8px' }}>
      {/* 策略卡片 */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 24 }}>
        {/* 强势股策略 */}
        <Card style={{ background: 'linear-gradient(135deg, #1677ff, #0958d9)', color: '#fff', border: 'none' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 16 }}>
            <Title level={3} style={{ color: '#fff', margin: 0 }}>强势股策略</Title>
            {isLoading ? (
              <div style={{ textAlign: 'right' }}>
                <div style={{ width: 64, height: 40, background: 'rgba(255,255,255,0.2)', borderRadius: 4 }} />
                <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>加载中...</Text>
              </div>
            ) : (
              <div style={{ textAlign: 'right' }}>
                <Title level={1} style={{ color: '#fff', margin: 0 }}>{data?.count || 0}</Title>
                <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>符合条件</Text>
              </div>
            )}
          </div>

          {/* 参数设置 */}
          <div style={{ marginBottom: 16, padding: 12, background: 'rgba(255,255,255,0.15)', borderRadius: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 13 }}>涨停截止时间</Text>
                <div>
                  <Text style={{ color: 'rgba(255,255,255,0.5)', fontSize: 12 }}>T-1和T-2共用</Text>
                </div>
              </div>
              <Select
                value={limitTime}
                onChange={setLimitTime}
                style={{ width: 120 }}
                options={TIME_OPTIONS.map((t) => ({ value: t, label: t }))}
                popupMatchSelectWidth={false}
              />
            </div>
          </div>

          {isLoading ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ width: 128, height: 16, background: 'rgba(255,255,255,0.2)', borderRadius: 4 }} />
              <div style={{ width: 144, height: 16, background: 'rgba(255,255,255,0.2)', borderRadius: 4 }} />
              <div style={{ width: 144, height: 16, background: 'rgba(255,255,255,0.2)', borderRadius: 4 }} />
            </div>
          ) : data?.trade_dates ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>T 日: {data.trade_dates.T}</Text>
              <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>T-1日: {data.trade_dates['T-1']}</Text>
              <Text style={{ color: 'rgba(255,255,255,0.7)', fontSize: 13 }}>T-2日: {data.trade_dates['T-2']}</Text>
            </div>
          ) : null}
        </Card>

        {/* 其他策略待开发 */}
        <Card>
          <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: '100%', minHeight: 180 }}>
            <div style={{ textAlign: 'center' }}>
              <div style={{ fontSize: 48, color: '#d9d9d9', marginBottom: 12 }}>+</div>
              <Title level={4} type="secondary">其他策略</Title>
              <Text type="secondary" style={{ fontSize: 13 }}>正在开发中...</Text>
            </div>
          </div>
        </Card>
      </div>

      {/* 风险提示 */}
      <Alert
        message="固定策略筛选，仅供参考学习。股市有风险，投资需谨慎，不构成投资建议。"
        type="warning"
        showIcon
        icon={<WarningOutlined />}
        style={{ textAlign: 'center' }}
      />

      {/* 筛选结果标题和刷新按钮 */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={4} style={{ margin: 0 }}>筛选结果</Title>
        <Space>
          {selectedCodes.length >= 2 && (
            <Button style={{ background: '#722ed1', borderColor: '#722ed1', color: '#fff' }} onClick={handleOpenMulti}>
              多选一 AI分析
            </Button>
          )}
          <Button
            type="primary"
            icon={<ReloadOutlined spin={isFetching} />}
            onClick={() => refetch()}
            loading={isFetching}
          >
            {isFetching ? '刷新中...' : '刷新数据'}
          </Button>
        </Space>
      </div>

      {/* 股票列表 */}
      {isLoading ? (
        <Card>
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', padding: 48 }}>
            <Spin size="large" />
            <Text type="secondary" style={{ marginTop: 16 }}>正在加载数据...</Text>
          </div>
        </Card>
      ) : error ? (
        <Alert
          message="加载数据失败"
          description={String(error)}
          type="error"
          showIcon
          action={<Button onClick={() => refetch()}>重试</Button>}
        />
      ) : !data || data.stocks.length === 0 ? (
        <Card>
          <Empty description="暂无符合条件的股票" />
        </Card>
      ) : (
        <Card styles={{ body: { padding: 0 } }}>
          <Table
            columns={columns}
            dataSource={data.stocks}
            rowKey="code"
            pagination={false}
            scroll={{ x: 1100 }}
            size="middle"
          />
        </Card>
      )}

      {/* 多选一 模态 */}
      <Modal
        title="多选一 AI分析"
        open={showMultiModal}
        onCancel={() => { setShowMultiModal(false); setMultiError(null); }}
        footer={null}
        width={640}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <Text type="secondary" style={{ fontSize: 13 }}>
            本模式要求从所选股票中<strong>必须选择一只</strong>进行买入决策。
          </Text>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>选择模式</Text>
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 8 }}>
              <Button
                type={multiMode === 'fast' ? 'primary' : 'default'}
                style={multiMode === 'fast' ? { background: '#722ed1', borderColor: '#722ed1' } : {}}
                onClick={() => setMultiMode('fast')}
              >
                <div>快速模式</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>思考1 / 辩论1</div>
              </Button>
              <Button
                type={multiMode === 'balanced' ? 'primary' : 'default'}
                style={multiMode === 'balanced' ? { background: '#722ed1', borderColor: '#722ed1' } : {}}
                onClick={() => setMultiMode('balanced')}
              >
                <div>均衡模式</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>思考2 / 辩论1</div>
              </Button>
              <Button
                type={multiMode === 'deep' ? 'primary' : 'default'}
                style={multiMode === 'deep' ? { background: '#722ed1', borderColor: '#722ed1' } : {}}
                onClick={() => setMultiMode('deep')}
              >
                <div>深入模式</div>
                <div style={{ fontSize: 11, opacity: 0.7 }}>思考3 / 辩论2</div>
              </Button>
            </div>
          </div>

          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>选择参与辩论的Agent（至少2个）</Text>
            {agentsLoading ? (
              <Text type="secondary">加载中...</Text>
            ) : agents && agents.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
                {agents.map((agent) => (
                  <label key={agent.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: 8, border: '1px solid #d9d9d9', borderRadius: 8, cursor: 'pointer' }}>
                    <Checkbox
                      checked={selectedAgentIds.includes(agent.id)}
                      onChange={() =>
                        setSelectedAgentIds((prev) =>
                          prev.includes(agent.id) ? prev.filter((id) => id !== agent.id) : [...prev, agent.id]
                        )
                      }
                    />
                    <Text style={{ fontSize: 13 }}>{agent.name} ({agent.type})</Text>
                  </label>
                ))}
              </div>
            ) : (
              <Text type="secondary">暂无启用的Agent，请先在配置页面添加</Text>
            )}
          </div>

          {multiError && (
            <Alert message={multiError} type="error" showIcon closable onClose={() => setMultiError(null)} />
          )}

          <Button
            type="primary"
            block
            size="large"
            style={{ background: '#722ed1', borderColor: '#722ed1' }}
            onClick={handleStartMulti}
          >
            启动多选一分析
          </Button>
        </div>
      </Modal>

      {/* 添加到模拟盘 模态 */}
      <Modal
        title={`添加到模拟盘 - ${paperTargetStock?.name || ''} (${paperTargetStock?.code || ''})`}
        open={showPaperModal}
        onCancel={() => { setShowPaperModal(false); setPaperError(null); }}
        footer={null}
        width={480}
      >
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* 模拟盘账户选择 */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>模拟盘账户</Text>
            {paperAccountsLoading ? (
              <Text type="secondary" style={{ fontSize: 13 }}>加载中...</Text>
            ) : (
              <Select
                value={selectedPaperAccountId}
                onChange={(v) => setSelectedPaperAccountId(v ? Number(v) : null)}
                placeholder="-- 请选择 --"
                style={{ width: '100%' }}
                options={paperAccounts?.map((acct: any) => ({ value: acct.id, label: acct.name })) || []}
              />
            )}
          </div>

          {/* 买入数量 */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              买入数量 <Text type="secondary" style={{ fontWeight: 'normal', fontSize: 13 }}>（留空自动计算）</Text>
            </Text>
            <Input
              type="number"
              value={paperQuantity}
              onChange={(e) => setPaperQuantity(e.target.value)}
              placeholder="留空自动计算"
            />
          </div>

          {/* 错误提示 */}
          {paperError && (
            <Alert message={paperError} type="error" showIcon closable onClose={() => setPaperError(null)} />
          )}

          {/* 提交按钮 */}
          <Button
            type="primary"
            block
            loading={paperLoading}
            style={{ background: '#f97316', borderColor: '#f97316' }}
            onClick={handleSubmitPaperPlan}
          >
            {paperLoading ? '提交中...' : '确认添加'}
          </Button>
        </div>
      </Modal>
    </div>
  );
}
