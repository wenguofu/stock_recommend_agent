import { useQuery, useQueryClient } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import { useEffect, useState } from 'react';
import {
  Card,
  Button,
  Space,
  Typography,
  Spin,
  Alert,
  Empty,
  Table,
  Tag,
  Modal,
  Select,
  Segmented,
  Checkbox,
  message,
} from 'antd';
import {
  ReloadOutlined,
  WarningOutlined,
  FireOutlined,
  TrophyOutlined,
  RocketOutlined,
  PlusOutlined,
} from '@ant-design/icons';

const { Title, Text } = Typography;

interface StrategyStock {
  code: string;
  name?: string;
  price?: number;
  score: number;
  roe?: number; gross_margin?: number; ret_60d?: number; ret_20d?: number;
  break_pct?: number; vol_ratio?: number; rsi?: number; ma_spread?: number;
  t1_limit_time?: string; t2_limit_time?: string;
  consecutive_days?: number; break_count?: number; industry?: string;
  current_price?: number | null; change_percent?: number | null;
  volume?: number | null; amount?: number | null;
}

interface StrategyData {
  strategy: string; name: string; description: string;
  count: number; stocks: StrategyStock[]; error?: string;
}

interface RecommendationsResponse {
  strategies: StrategyData[]; timestamp: string;
}

interface StrongStocksResponse {
  strategy: string; description: string; params: { limit_time: string };
  trade_dates: { T: string; 'T-1': string; 'T-2': string };
  count: number; stocks: any[];
}

const TIME_OPTIONS = ['09:30','09:45','10:00','10:15','10:30','10:45','11:00','11:15','11:30','13:00','13:30','14:00','14:30','15:00'];

const STRATEGY_TABS = [
  { key: 'strong_stocks', label: '强势股接力', color: '#1677ff', icon: <FireOutlined /> },
  { key: 'tenbagger', label: '十倍潜力股', color: '#722ed1', icon: <TrophyOutlined /> },
  { key: 'breakout', label: '突破形态', color: '#fa8c16', icon: <RocketOutlined /> },
];

export default function StrategyRecommend() {
  const [activeTab, setActiveTab] = useState('tenbagger');
  const [limitTime, setLimitTime] = useState('11:30');
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [showMultiModal, setShowMultiModal] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);
  const [multiMode, setMultiMode] = useState<'fast'|'balanced'|'deep'>('fast');
  const [multiError, setMultiError] = useState<string|null>(null);
  const [addingMap, setAddingMap] = useState<Record<string,boolean>>({});
  const [addedMap, setAddedMap] = useState<Record<string,boolean>>({});
  const [showPaperModal, setShowPaperModal] = useState(false);
  const [selectedPaperAccountId, setSelectedPaperAccountId] = useState<number|null>(null);
  const [paperTargetStock, setPaperTargetStock] = useState<{code:string;name:string;currentPrice:number|null}|null>(null);
  const [paperLoading, setPaperLoading] = useState(false);
  const [paperError, setPaperError] = useState<string|null>(null);
  const queryClient = useQueryClient();
  const navigate = useNavigate();

  // Strong stocks
  const { data: strongData, isLoading: strongLoading, error: strongError, refetch: strongRefetch, isFetching: strongFetching } = useQuery<StrongStocksResponse>({
    queryKey: ['strong-stocks', limitTime],
    queryFn: () => stockAPI.getStrongStocks(limitTime),
    enabled: activeTab === 'strong_stocks',
    refetchInterval: 60000,
  });

  // Tenbagger + Breakout
  const { data: recData, isLoading: recLoading, error: recError, refetch: recRefetch, isFetching: recFetching } = useQuery<RecommendationsResponse>({
    queryKey: ['strategy-recommendations'],
    queryFn: async () => {
      const r = await fetch(`${stockAPI.getBaseURL()}/api/strategy/recommendations`);
      if (!r.ok) throw new Error('Failed');
      return r.json();
    },
    enabled: activeTab !== 'strong_stocks',
    refetchInterval: 300000,
  });

  const { data: agents } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => stockAPI.getAgents(true),
    enabled: showMultiModal,
  });

  useEffect(() => {
    if (showMultiModal && agents && agents.length > 0 && selectedAgentIds.length === 0) {
      setSelectedAgentIds(agents.map(a => a.id));
    }
  }, [showMultiModal, agents, selectedAgentIds.length]);

  const { data: paperAccounts } = useQuery({
    queryKey: ['paper-accounts'],
    queryFn: async () => {
      const r = await fetch(`${stockAPI.getBaseURL()}/api/paper/accounts`);
      if (!r.ok) throw new Error('Failed');
      return (await r.json()).accounts as any[];
    },
    enabled: showPaperModal,
  });

  useEffect(() => {
    if (showPaperModal && paperAccounts && paperAccounts.length > 0 && !selectedPaperAccountId) {
      setSelectedPaperAccountId(paperAccounts[0].id);
    }
  }, [showPaperModal, paperAccounts, selectedPaperAccountId]);

  const activeStrategy = ((): StrategyData | null => {
    if (activeTab === 'strong_stocks' && strongData) {
      return {
        strategy: 'strong_stocks', name: '强势股接力',
        description: '前两日早盘涨停, 今日未涨停的接力候选',
        count: strongData.count || 0,
        stocks: (strongData.stocks || []).map((s: any) => ({
          code: s.code, name: s.name, price: s.current_price,
          score: (s.consecutive_days||0)*20 + (s.break_count||0)*10,
          t1_limit_time: s.t1_limit_time, t2_limit_time: s.t2_limit_time,
          consecutive_days: s.consecutive_days, break_count: s.break_count,
          industry: s.industry, current_price: s.current_price,
          change_percent: s.change_percent, volume: s.volume, amount: s.amount,
        })),
      };
    }
    if (recData) return recData.strategies.find(s => s.strategy === activeTab) || null;
    return null;
  })();

  const isLoading = activeTab === 'strong_stocks' ? strongLoading : recLoading;
  const isFetching = activeTab === 'strong_stocks' ? strongFetching : recFetching;
  const error = activeTab === 'strong_stocks' ? strongError : recError;
  const refetch = activeTab === 'strong_stocks' ? strongRefetch : recRefetch;
  const stocks = activeStrategy?.stocks || [];

  const formatNumber = (n: number|null|undefined) => {
    if (n==null) return '-';
    if (n>=1e8) return (n/1e8).toFixed(2)+'亿';
    if (n>=1e4) return (n/1e4).toFixed(2)+'万';
    return n.toFixed(2);
  };
  const formatTime = (t: string|null|undefined) => {
    if (!t) return '-'; const s=String(t);
    if (s.includes(':')) return s;
    if (s.length===6) return `${s.slice(0,2)}:${s.slice(2,4)}:${s.slice(4,6)}`;
    if (s.length===5) return `0${s.slice(0,1)}:${s.slice(1,3)}:${s.slice(3,5)}`;
    return s;
  };
  const toggleSelect = (code: string) => setSelectedCodes(p => p.includes(code)?p.filter(c=>c!==code):[...p,code]);
  const handleAddWatchlist = async (code: string, name: string) => {
    if (addingMap[code]) return;
    setAddingMap(p=>({...p,[code]:true}));
    try { await stockAPI.addWatchlist(code, name); setAddedMap(p=>({...p,[code]:true})); }
    catch { message.error('加入自选失败'); }
    finally { setAddingMap(p=>({...p,[code]:false})); }
  };
  const handleOpenMulti = () => {
    if (selectedCodes.length<2) { setMultiError('至少勾选2只'); return; }
    setMultiError(null); setShowMultiModal(true);
  };
  const handleStartMulti = async () => {
    if (selectedCodes.length<2) { setMultiError('至少勾选2只'); return; }
    if (selectedAgentIds.length<2) { setMultiError('至少2个Agent'); return; }
    try {
      const cfg={fast:{analysisRounds:1,debateRounds:1},balanced:{analysisRounds:2,debateRounds:1},deep:{analysisRounds:3,debateRounds:2}}[multiMode];
      const res = await stockAPI.startMultiSelectDebate(selectedCodes, selectedAgentIds, cfg.analysisRounds, cfg.debateRounds);
      setShowMultiModal(false);
      navigate(`/ai-debate?job_id=${res.job_id}&code=${selectedCodes.join(',')}`);
    } catch { setMultiError('启动失败'); }
  };
  const handleOpenPaper = (stock: StrategyStock) => {
    setPaperTargetStock({code:stock.code,name:stock.name||stock.code,currentPrice:stock.current_price??stock.price??null});
    setPaperError(null); setShowPaperModal(true);
  };
  const handleSubmitPaper = async () => {
    if (!paperTargetStock||!selectedPaperAccountId) { setPaperError('请选择账户'); return; }
    setPaperLoading(true);
    try {
      await stockAPI.batchCreatePlans(selectedPaperAccountId, paperTargetStock.code, paperTargetStock.name, paperTargetStock.currentPrice??undefined);
      setShowPaperModal(false);
      queryClient.invalidateQueries({queryKey:['paper-accounts']});
    } catch { setPaperError('创建失败'); }
    finally { setPaperLoading(false); }
  };

  const tab = STRATEGY_TABS.find(t=>t.key===activeTab) || STRATEGY_TABS[0];

  // Build table columns based on active tab
  const buildColumns = () => {
    const baseCols: any[] = [
      {
        title: '',
        dataIndex: 'code',
        key: 'select',
        width: 50,
        render: (_: any, record: StrategyStock) => (
          <Checkbox checked={selectedCodes.includes(record.code)} onChange={() => toggleSelect(record.code)} />
        ),
      },
      {
        title: '代码',
        dataIndex: 'code',
        key: 'code',
        width: 100,
        render: (code: string) => <Text code style={{ fontWeight: 500 }}>{code}</Text>,
      },
      {
        title: '名称',
        dataIndex: 'name',
        key: 'name',
        ellipsis: true,
        render: (name: string) => name || '-',
      },
    ];

    if (activeTab === 'strong_stocks') {
      baseCols.push(
        { title: '行业', dataIndex: 'industry', key: 'industry', render: (v: string) => v || '-' },
        { title: 'T-1', dataIndex: 't1_limit_time', key: 't1', render: (v: string) => formatTime(v) },
        { title: 'T-2', dataIndex: 't2_limit_time', key: 't2', render: (v: string) => formatTime(v) },
        {
          title: '连板', dataIndex: 'consecutive_days', key: 'consecutive',
          render: (v: number) => (v ?? 0) > 0 ? <Tag color="red">{v}连板</Tag> : '-',
        },
        {
          title: '炸板', dataIndex: 'break_count', key: 'break',
          render: (v: number) => (v ?? 0) > 0 ? <Tag color="gold">{v}次</Tag> : '-',
        },
      );
    }

    if (activeTab === 'tenbagger') {
      baseCols.push(
        {
          title: '评分', dataIndex: 'score', key: 'score', align: 'right' as const,
          render: (v: number) => <Text strong style={{ color: v >= 80 ? '#ff4d4f' : v >= 65 ? '#fa8c16' : '#8c8c8c' }}>{v}</Text>,
        },
        { title: 'ROE', dataIndex: 'roe', key: 'roe', align: 'right' as const, render: (v: number) => v != null ? `${v}%` : '-' },
        { title: '毛利', dataIndex: 'gross_margin', key: 'margin', align: 'right' as const, render: (v: number) => v != null ? `${v}%` : '-' },
        {
          title: '60日', dataIndex: 'ret_60d', key: 'ret60', align: 'right' as const,
          render: (v: number) => <Text style={{ color: (v ?? 0) >= 0 ? '#ff4d4f' : '#52c41a' }}>{(v ?? 0) > 0 ? '+' : ''}{v != null ? `${v}%` : '-'}</Text>,
        },
      );
    }

    if (activeTab === 'breakout') {
      baseCols.push(
        {
          title: '评分', dataIndex: 'score', key: 'score', align: 'right' as const,
          render: (v: number) => <Text strong style={{ color: v >= 80 ? '#ff4d4f' : v >= 65 ? '#fa8c16' : '#8c8c8c' }}>{v}</Text>,
        },
        { title: '突破%', dataIndex: 'break_pct', key: 'breakpct', align: 'right' as const, render: (v: number) => v != null ? <Text style={{ color: '#ff4d4f' }}>{v}%</Text> : '-' },
        { title: '量比', dataIndex: 'vol_ratio', key: 'vol', align: 'right' as const, render: (v: number) => v != null ? `${v}x` : '-' },
        { title: 'RSI', dataIndex: 'rsi', key: 'rsi', align: 'right' as const, render: (v: number) => v != null ? v : '-' },
      );
    }

    baseCols.push(
      {
        title: '现价', dataIndex: 'current_price', key: 'price', align: 'right' as const, width: 90,
        render: (_: any, record: StrategyStock) => {
          const p = record.current_price ?? record.price;
          return p != null ? `¥${p.toFixed(2)}` : '-';
        },
      },
      {
        title: '操作', key: 'actions', width: 200,
        render: (_: any, record: StrategyStock) => (
          <Space size={4}>
            <Link to={`/stock/${record.code}`}>
              <Button size="small" type="primary">详情</Button>
            </Link>
            <Button
              size="small"
              style={{ backgroundColor: '#10b981', borderColor: '#10b981', color: '#fff' }}
              disabled={addingMap[record.code] || addedMap[record.code]}
              onClick={() => handleAddWatchlist(record.code, record.name || record.code)}
            >
              {addedMap[record.code] ? '已加' : addingMap[record.code] ? '...' : '加自选'}
            </Button>
            <Button
              size="small"
              style={{ backgroundColor: '#fa8c16', borderColor: '#fa8c16', color: '#fff' }}
              icon={<PlusOutlined />}
              onClick={() => handleOpenPaper(record)}
            >
              计划
            </Button>
          </Space>
        ),
      },
    );

    return baseCols;
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%', padding: '0 24px' }}>
      {/* Strategy tabs */}
      <Segmented
        block
        size="large"
        value={activeTab}
        onChange={(val) => { setActiveTab(val as string); setSelectedCodes([]); }}
        options={STRATEGY_TABS.map(t => ({
          label: <span>{t.icon} {t.label}</span>,
          value: t.key,
        }))}
        style={{ backgroundColor: '#f5f5f5' }}
      />

      {/* Strategy info card */}
      <Card
        style={{
          background: `linear-gradient(135deg, ${tab.color} 0%, ${tab.color}dd 100%)`,
          border: 'none',
        }}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div>
            <Title level={3} style={{ color: '#fff', margin: 0 }}>
              {STRATEGY_TABS.find(t => t.key === activeTab)?.icon} {tab.label}
            </Title>
            <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 14 }}>
              {activeStrategy?.description || '加载中...'}
            </Text>
          </div>
          <div style={{ textAlign: 'right' }}>
            <div style={{ color: '#fff', fontSize: 48, fontWeight: 'bold', lineHeight: 1 }}>
              {activeStrategy?.count ?? '-'}
            </div>
            <Text style={{ color: 'rgba(255,255,255,0.8)', fontSize: 14 }}>符合条件</Text>
          </div>
        </div>
        {activeTab === 'strong_stocks' && (
          <div style={{
            marginTop: 16,
            padding: 12,
            background: 'rgba(255,255,255,0.1)',
            borderRadius: 8,
            display: 'flex',
            alignItems: 'center',
            gap: 12,
          }}>
            <Text style={{ color: '#fff', fontSize: 14 }}>涨停截止:</Text>
            <Select
              value={limitTime}
              onChange={setLimitTime}
              style={{ width: 100 }}
              options={TIME_OPTIONS.map(t => ({ label: t, value: t }))}
              popupMatchSelectWidth={false}
            />
          </div>
        )}
      </Card>

      {/* Warning */}
      <Alert
        message="固定策略筛选，仅供参考。不构成投资建议。"
        type="warning"
        showIcon
        icon={<WarningOutlined />}
        style={{ textAlign: 'center' }}
      />

      {/* Toolbar */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={5} style={{ margin: 0 }}>筛选结果 ({stocks.length}只)</Title>
        <Space>
          {selectedCodes.length >= 2 && (
            <Button type="primary" style={{ backgroundColor: '#722ed1', borderColor: '#722ed1' }} onClick={handleOpenMulti}>
              多选一 AI分析 ({selectedCodes.length})
            </Button>
          )}
          <Button icon={<ReloadOutlined />} loading={isFetching} onClick={() => refetch()}>
            {isFetching ? '刷新中...' : '刷新'}
          </Button>
        </Space>
      </div>

      {/* Content */}
      {isLoading ? (
        <Card>
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin size="large" />
            <div style={{ marginTop: 16 }}>加载中...</div>
          </div>
        </Card>
      ) : error ? (
        <Alert
          type="error"
          message={`加载失败: ${String(error)}`}
          action={<Button size="small" onClick={() => refetch()}>重试</Button>}
        />
      ) : stocks.length === 0 ? (
        <Card>
          <Empty
            description={
              <>
                <div style={{ marginBottom: 8 }}>当前暂无符合条件的股票</div>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  {activeTab === 'strong_stocks' ? '非交易时段可能无数据' : activeTab === 'breakout' ? '下跌市中突破信号稀少' : '数据加载中，请刷新'}
                </Text>
              </>
            }
          />
        </Card>
      ) : (
        <Card bodyStyle={{ padding: 0 }}>
          <Table
            dataSource={stocks}
            rowKey="code"
            columns={buildColumns()}
            pagination={false}
            size="small"
            scroll={{ x: 'max-content' }}
          />
        </Card>
      )}

      {/* Multi-select modal */}
      <Modal
        title="多选一 AI分析"
        open={showMultiModal}
        onCancel={() => { setShowMultiModal(false); setMultiError(null); }}
        footer={null}
        width={640}
      >
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Text type="secondary">已选: {selectedCodes.join(', ')}</Text>
          <Segmented
            block
            value={multiMode}
            onChange={(v) => setMultiMode(v as 'fast'|'balanced'|'deep')}
            options={[
              { label: '快速(1+1)', value: 'fast' },
              { label: '均衡(2+1)', value: 'balanced' },
              { label: '深入(3+2)', value: 'deep' },
            ]}
          />
          {agents && agents.length > 0 && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 4 }}>
              {agents.map((a: any) => (
                <Checkbox
                  key={a.id}
                  checked={selectedAgentIds.includes(a.id)}
                  onChange={() => setSelectedAgentIds(p => p.includes(a.id) ? p.filter(i => i !== a.id) : [...p, a.id])}
                >
                  {a.name}
                </Checkbox>
              ))}
            </div>
          )}
          {multiError && <Text type="danger">{multiError}</Text>}
          <Button type="primary" block onClick={handleStartMulti} style={{ backgroundColor: '#722ed1', borderColor: '#722ed1' }}>
            启动分析
          </Button>
        </Space>
      </Modal>

      {/* Paper modal */}
      <Modal
        title={paperTargetStock ? `添加模拟盘计划 - ${paperTargetStock.name}` : '添加模拟盘计划'}
        open={showPaperModal}
        onCancel={() => setShowPaperModal(false)}
        footer={null}
        width={400}
      >
        {paperTargetStock && (
          <Space direction="vertical" style={{ width: '100%' }} size="middle">
            <Text type="secondary">现价: ¥{paperTargetStock.currentPrice?.toFixed(2) || '未知'}</Text>
            <Select
              value={selectedPaperAccountId}
              onChange={setSelectedPaperAccountId}
              style={{ width: '100%' }}
              placeholder="选择账户"
              options={paperAccounts?.map((a: any) => ({ label: a.name, value: a.id })) || []}
            />
            {paperError && <Text type="danger">{paperError}</Text>}
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setShowPaperModal(false)}>取消</Button>
              <Button
                type="primary"
                loading={paperLoading}
                onClick={handleSubmitPaper}
                style={{ backgroundColor: '#fa8c16', borderColor: '#fa8c16' }}
              >
                {paperLoading ? '创建中...' : '创建计划'}
              </Button>
            </Space>
          </Space>
        )}
      </Modal>
    </Space>
  );
}
