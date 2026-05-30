import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useWatchlistStore } from '../store/watchlistStore';
import { stockAPI } from '../services/api';
import AIAnalyzeButton from '../components/AIAnalyzeButton';
import type { Agent } from '../services/api';
import {
  Card,
  Table,
  Input,
  Button,
  Modal,
  Segmented,
  Alert,
  Spin,
  Space,
  Checkbox,
  Typography,
  InputNumber,
  App,
} from 'antd';

const { Title } = Typography;

const API = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

type MultiMode = 'fast' | 'balanced' | 'deep';

// 判断是否在交易时间
function isTradingTime(): boolean {
  const now = new Date();
  const hour = now.getHours();
  const minute = now.getMinutes();
  const day = now.getDay();

  if (day === 0 || day === 6) return false;

  const morningStart = (hour === 9 && minute >= 30) || (hour > 9 && hour < 11) || (hour === 11 && minute <= 30);
  const afternoonStart = hour >= 13 && hour < 15;

  return morningStart || afternoonStart;
}

function getRefetchInterval(): number {
  return isTradingTime() ? 5000 : 60000;
}

export default function Watchlist() {
  const { addStock, removeStock, error: storeError } = useWatchlistStore();
  const { message } = App.useApp();
  const queryClient = useQueryClient();
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [codeInput, setCodeInput] = useState('');
  const [costInput, setCostInput] = useState<number | null>(null);
  const [sharesInput, setSharesInput] = useState<number | null>(null);
  const [showPositionFields, setShowPositionFields] = useState(false);
  const [adding, setAdding] = useState(false);
  const [editPosition, setEditPosition] = useState<string | null>(null);
  const [editCost, setEditCost] = useState<number | null>(null);
  const [editShares, setEditShares] = useState<number | null>(null);
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [showMultiModal, setShowMultiModal] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);
  const [multiMode, setMultiMode] = useState<MultiMode>('fast');
  const [multiError, setMultiError] = useState<string | null>(null);
  const navigate = useNavigate();

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

  // Paginated watchlist data
  const { data: watchlistPage, isLoading } = useQuery({
    queryKey: ['watchlist', page, pageSize],
    queryFn: () => fetch(`${API}/api/watchlist?page=${page}&pageSize=${pageSize}`).then(r => r.json()),
  });
  const items = watchlistPage?.data || [];
  const total = watchlistPage?.total || 0;

  const handleAdd = async () => {
    const code = codeInput.trim();
    if (!code) {
      message.error('请输入股票代码（A股6位数字 或 美股ticker，如 AAPL）');
      return;
    }
    const isACode = /^\d{6}$/.test(code);
    const isUsCode = /^[A-Za-z]{1,5}$/.test(code);
    if (!isACode && !isUsCode) {
      message.error('股票代码格式错误：A股输入6位数字(如 000001)，美股输入ticker(如 AAPL)');
      return;
    }

    setAdding(true);
    try {
      const realtime = await stockAPI.getRealtime(code);
      await addStock(code, realtime.name, costInput, sharesInput);
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
      setCodeInput('');
      setCostInput(null);
      setSharesInput(null);
      setShowPositionFields(false);
      message.success('添加成功');
    } catch (error) {
      message.error(`添加失败: ${(error as Error).message}`);
    } finally {
      setAdding(false);
    }
  };

  const toggleSelectCode = (code: string) => {
    setSelectedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const handleOpenMulti = () => {
    if (selectedCodes.length < 2) {
      setMultiError('请至少勾选2只股票');
      return;
    }
    setMultiError(null);
    setShowMultiModal(true);
  };

  const handleSavePosition = async (code: string) => {
    try {
      await stockAPI.updateWatchlistPosition(code, editCost, editShares);
      setEditPosition(null);
      queryClient.invalidateQueries({ queryKey: ['watchlist'] });
    } catch (error) {
      message.error(`更新失败: ${(error as Error).message}`);
    }
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

  // Table columns
  const columns = [
    {
      title: '',
      key: 'select',
      width: 50,
      render: (_: unknown, record: { code: string }) => (
        <Checkbox
          checked={selectedCodes.includes(record.code)}
          onChange={() => toggleSelectCode(record.code)}
          aria-label={`选择 ${record.code}`}
        />
      ),
    },
    {
      title: '股票',
      key: 'stock',
      render: (_: unknown, record: { code: string; name: string; cost_price?: number | null; shares?: number | null }) => {
        const hasPosition = record.cost_price != null && record.shares != null && record.shares > 0;
        return (
          <Link to={`/stock/${record.code}`} style={{ color: 'inherit', textDecoration: 'none' }}>
            <div style={{ fontWeight: 600 }}>{record.name || record.code}</div>
            <div style={{ fontSize: 12, color: '#999' }}>{record.code}</div>
            {hasPosition && (
              <div style={{ fontSize: 12, color: '#999', marginTop: 2 }}>
                成本{record.cost_price!.toFixed(2)} × {record.shares!.toLocaleString()}股
              </div>
            )}
          </Link>
        );
      },
    },
    {
      title: '现价',
      key: 'price',
      width: 100,
      render: (_: unknown, record: { code: string }) => (
        <WatchlistPriceCell code={record.code} />
      ),
    },
    {
      title: '涨跌幅',
      key: 'change',
      width: 100,
      render: (_: unknown, record: { code: string }) => (
        <WatchlistChangeCell code={record.code} />
      ),
    },
    {
      title: '持仓盈亏',
      key: 'pnl',
      width: 120,
      render: (_: unknown, record: { code: string; cost_price?: number | null; shares?: number | null }) => (
        <WatchlistPnlCell code={record.code} costPrice={record.cost_price} shares={record.shares} />
      ),
    },
    {
      title: '操作',
      key: 'actions',
      width: 220,
      render: (_: unknown, record: { code: string; name: string; cost_price?: number | null; shares?: number | null }) => {
        const hasPosition = record.cost_price != null && record.shares != null && record.shares > 0;
        return (
          <Space size="small" wrap>
            <AIAnalyzeButton code={record.code} />
            {!hasPosition ? (
              <Button
                size="small"
                onClick={() => {
                  setEditPosition(record.code);
                  setEditCost(null);
                  setEditShares(null);
                }}
              >
                设置持仓
              </Button>
            ) : (
              <Button
                size="small"
                onClick={() => {
                  setEditPosition(record.code);
                  setEditCost(record.cost_price ?? null);
                  setEditShares(record.shares ?? null);
                }}
              >
                编辑持仓
              </Button>
            )}
            <Button
              size="small"
              danger
              onClick={async () => {
                await removeStock(record.code);
                queryClient.invalidateQueries({ queryKey: ['watchlist'] });
              }}
            >
              删除
            </Button>
          </Space>
        );
      },
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>自选股管理</Title>
        <Space>
        {selectedCodes.length > 0 && (
          <Button size="small" onClick={() => setSelectedCodes(items.map((i: any) => i.code))}>
            全选
          </Button>
        )}
        {selectedCodes.length > 0 && (
          <Button size="small" onClick={() => setSelectedCodes([])}>
            取消全选
          </Button>
        )}
        {selectedCodes.length >= 2 && (
          <Button type="primary" style={{ backgroundColor: '#722ed1', borderColor: '#722ed1' }} onClick={handleOpenMulti}>
            多选一 AI分析 ({selectedCodes.length})
          </Button>
        )}
      </Space>
      </div>

      {/* Store Error */}
      {storeError && (
        <Alert
          type="error"
          message={storeError}
          showIcon
          closable
        />
      )}

      {/* Add Form */}
      <Card title="添加自选股">
        <Space direction="vertical" style={{ width: '100%' }}>
          <Space.Compact style={{ width: '100%' }}>
            <Input
              value={codeInput}
              onChange={(e) => setCodeInput(e.target.value)}
              placeholder="股票代码（A股6位数字 或 美股ticker，如 000001 / AAPL）"
              maxLength={10}
              style={{ flex: 1 }}
            />
            <Button
              type="primary"
              onClick={handleAdd}
              loading={adding}
            >
              {adding ? '添加中...' : '添加'}
            </Button>
          </Space.Compact>

          <Checkbox
            checked={showPositionFields}
            onChange={(e) => setShowPositionFields(e.target.checked)}
          >
            添加持仓信息
          </Checkbox>

          {showPositionFields && (
            <Space>
              <InputNumber
                value={costInput}
                onChange={(val) => setCostInput(val)}
                placeholder="持仓成本价（元）"
                step={0.01}
                style={{ width: 200 }}
              />
              <InputNumber
                value={sharesInput}
                onChange={(val) => setSharesInput(val)}
                placeholder="持股数量（股）"
                step={100}
                style={{ width: 200 }}
              />
            </Space>
          )}
        </Space>
      </Card>

      {/* Watchlist Table */}
      <Card title="我的自选">
        <Spin spinning={isLoading}>
          {items.length === 0 && !isLoading ? (
            <div style={{ textAlign: 'center', padding: 32, color: '#999' }}>暂无自选股</div>
          ) : (
            <Table
              dataSource={items}
              columns={columns}
              rowKey={(record) => record.code}
              pagination={{
                current: page,
                pageSize: pageSize,
                total: total,
                showSizeChanger: true,
                showTotal: (total: number) => `共 ${total} 只`,
                onChange: (p: number, ps: number) => {
                  setPage(p);
                  setPageSize(ps);
                },
              }}
              size="middle"
            />
          )}
        </Spin>
      </Card>

      {/* Edit Position Modal */}
      <Modal
        title={`编辑持仓 - ${items.find((it: any) => it.code === editPosition)?.name || editPosition || ''}`}
        open={editPosition !== null}
        onCancel={() => setEditPosition(null)}
        onOk={() => {
          if (editPosition) handleSavePosition(editPosition);
        }}
        okText="保存"
        cancelText="取消"
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          <InputNumber
            value={editCost}
            onChange={(val) => setEditCost(val)}
            placeholder="持仓成本价（元）"
            step={0.01}
            style={{ width: '100%' }}
          />
          <InputNumber
            value={editShares}
            onChange={(val) => setEditShares(val)}
            placeholder="持股数量（股）"
            step={100}
            style={{ width: '100%' }}
          />
        </Space>
      </Modal>

      {/* Multi-Select Modal */}
      <Modal
        title="多选一 AI分析"
        open={showMultiModal}
        onCancel={() => {
          setShowMultiModal(false);
          setMultiError(null);
        }}
        footer={
          <Button
            type="primary"
            block
            onClick={handleStartMulti}
            style={{ backgroundColor: '#722ed1', borderColor: '#722ed1' }}
          >
            启动多选一分析
          </Button>
        }
        width={640}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Typography.Text type="secondary">
            本模式要求从所选股票中<strong>必须选择一只</strong>进行买入决策。
          </Typography.Text>

          {/* Mode Selection */}
          <div>
            <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
              选择模式
            </Typography.Text>
            <Segmented
              value={multiMode}
              onChange={(val) => setMultiMode(val as MultiMode)}
              options={[
                { label: '快速模式\n思考1 / 辩论1', value: 'fast' },
                { label: '均衡模式\n思考2 / 辩论1', value: 'balanced' },
                { label: '深入模式\n思考3 / 辩论2', value: 'deep' },
              ]}
              block
            />
          </div>

          {/* Agent Selection */}
          <div>
            <Typography.Text strong style={{ display: 'block', marginBottom: 8 }}>
              选择参与辩论的Agent（至少2个）
            </Typography.Text>
            {agentsLoading ? (
              <Spin />
            ) : agents && agents.length > 0 ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                {agents.map((agent: Agent) => (
                  <Checkbox
                    key={agent.id}
                    checked={selectedAgentIds.includes(agent.id)}
                    onChange={() =>
                      setSelectedAgentIds((prev) =>
                        prev.includes(agent.id) ? prev.filter((id) => id !== agent.id) : [...prev, agent.id]
                      )
                    }
                  >
                    {agent.name} ({agent.type})
                  </Checkbox>
                ))}
              </Space>
            ) : (
              <Typography.Text type="secondary">暂无启用的Agent，请先在配置页面添加</Typography.Text>
            )}
          </div>

          {multiError && <Alert type="error" message={multiError} showIcon />}
        </Space>
      </Modal>
    </Space>
  );
}

// ---------- Inline table cell components ----------

function WatchlistPriceCell({ code }: { code: string }) {
  const { data: realtimeData, isLoading } = useQuery({
    queryKey: ['realtime', code],
    queryFn: () => stockAPI.getRealtime(code),
    refetchInterval: getRefetchInterval(),
    enabled: !!code,
  });

  if (isLoading) return <Spin size="small" />;
  if (!realtimeData || realtimeData.current_price == null || realtimeData.current_price <= 0) {
    return <span style={{ color: '#999' }}>--</span>;
  }
  const isUp = (realtimeData.change_percent ?? 0) >= 0;
  return (
    <span style={{ fontWeight: 700, color: isUp ? '#cf1322' : '#3f8600', fontSize: 16 }}>
      {realtimeData.current_price.toFixed(2)}
    </span>
  );
}

function WatchlistChangeCell({ code }: { code: string }) {
  const { data: realtimeData, isLoading } = useQuery({
    queryKey: ['realtime', code],
    queryFn: () => stockAPI.getRealtime(code),
    refetchInterval: getRefetchInterval(),
    enabled: !!code,
  });

  if (isLoading) return <Spin size="small" />;
  if (!realtimeData || realtimeData.current_price == null || realtimeData.current_price <= 0) {
    return <span style={{ color: '#999' }}>--</span>;
  }
  const changePercent = realtimeData.change_percent ?? 0;
  const changeValue = realtimeData.current_price - (realtimeData.yesterday_close ?? 0);
  const isUp = changePercent >= 0;
  const color = isUp ? '#cf1322' : '#3f8600';
  return (
    <div>
      <div style={{ fontWeight: 600, color, fontSize: 14 }}>
        {isUp ? '+' : ''}{changePercent.toFixed(2)}%
      </div>
      <div style={{ fontSize: 12, color }}>
        {isUp ? '+' : ''}{changeValue.toFixed(2)}
      </div>
    </div>
  );
}

function WatchlistPnlCell({
  code,
  costPrice,
  shares,
}: {
  code: string;
  costPrice?: number | null;
  shares?: number | null;
}) {
  const { data: realtimeData, isLoading } = useQuery({
    queryKey: ['realtime', code],
    queryFn: () => stockAPI.getRealtime(code),
    refetchInterval: getRefetchInterval(),
    enabled: !!code,
  });

  const hasPosition = costPrice != null && shares != null && shares > 0;

  if (!hasPosition) return <span style={{ color: '#ccc' }}>--</span>;
  if (isLoading) return <Spin size="small" />;

  const currentPrice = realtimeData?.current_price ?? 0;
  const positionValue = currentPrice * shares!;
  const positionCost = costPrice! * shares!;
  const positionPnl = positionValue - positionCost;
  const positionPnlPercent = costPrice! > 0 ? ((currentPrice - costPrice!) / costPrice!) * 100 : 0;

  const isUp = positionPnl >= 0;
  const color = isUp ? '#cf1322' : '#3f8600';

  return (
    <div style={{ textAlign: 'right' }}>
      <div style={{ fontWeight: 700, color, fontSize: 14 }}>
        {isUp ? '+' : ''}{positionPnl.toFixed(2)}
      </div>
      <div style={{ fontSize: 12, color }}>
        {isUp ? '+' : ''}{positionPnlPercent.toFixed(2)}%
      </div>
    </div>
  );
}
