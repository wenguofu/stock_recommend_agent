import { useQuery } from '@tanstack/react-query';
import { Link, useLocation } from 'react-router-dom';
import { stockAPI } from '../services/api';
import { useWatchlistStore } from '../store/watchlistStore';
import { useEffect, useState } from 'react';
import AIAnalyzeButton from '../components/AIAnalyzeButton';
import { findEtfs } from '../constants/sectorEtfs';
import IndexCard from '../components/IndexCard';
import {
  Row, Col, Card, Segmented, Table, Tag, Descriptions,
  Progress, Typography, Spin, Space, Button, Empty,
} from 'antd';
import {
  ArrowUpOutlined, ArrowDownOutlined, RiseOutlined, FallOutlined,
} from '@ant-design/icons';

const { Text } = Typography;

function isTradingTime(): boolean {
  const now = new Date(); const hour = now.getHours(); const minute = now.getMinutes(); const day = now.getDay();
  if (day === 0 || day === 6) return false;
  return (hour === 9 && minute >= 30 || hour > 9 && hour < 11 || hour === 11 && minute <= 30) || (hour >= 13 && hour < 15);
}
function getRefetchInterval(): number { return isTradingTime() ? 5000 : 60000; }

const MARKET_SEGMENTED_OPTIONS = [
  { label: 'A股', value: 'a' },
  { label: '美股', value: 'us' },
];

export default function Home() {
  const { items, fetchWatchlist } = useWatchlistStore();
  const [market, setMarket] = useState<'a' | 'us'>('a');
  const [debateFilter, setDebateFilter] = useState<'active' | 'completed'>('active');
  const location = useLocation();

  useEffect(() => { fetchWatchlist(); }, [fetchWatchlist]);

  const { data: debateJobs = [], isLoading: debateLoading, refetch: refetchDebates } = useQuery({
    queryKey: ['debate-jobs', debateFilter],
    queryFn: () => stockAPI.listDebateJobs(debateFilter, 20),
    refetchInterval: 5000,
  });
  useEffect(() => { refetchDebates(); }, [location.pathname, debateFilter, refetchDebates]);

  const handleStopDebate = async (jobId: string) => { await stockAPI.stopDebateJob(jobId); refetchDebates(); };
  const handleDeleteDebate = async (jobId: string) => { await stockAPI.deleteDebateJob(jobId); refetchDebates(); };

  const fetchIndexData = async (code: string) => {
    const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
    const res = await fetch(`${apiUrl}/api/sina/realtime/${code}`);
    if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);
    const data = await res.json();
    if (data.error) throw new Error(data.message || data.error);
    return data;
  };

  // A股三大指数
  const { data: shIndex, isLoading: shLoading } = useQuery({queryKey: ['realtime','sh000001'], queryFn: () => fetchIndexData('sh000001'), refetchInterval: getRefetchInterval(), retry: 2});
  const { data: szIndex, isLoading: szLoading } = useQuery({queryKey: ['realtime','sz399001'], queryFn: () => fetchIndexData('sz399001'), refetchInterval: getRefetchInterval(), retry: 2});
  const { data: cybIndex, isLoading: cybLoading } = useQuery({queryKey: ['realtime','sz399006'], queryFn: () => fetchIndexData('sz399006'), refetchInterval: getRefetchInterval(), retry: 2});

  // 美股三大指数
  const { data: usDji, isLoading: usDjiLoading } = useQuery({queryKey: ['realtime','$dji'], queryFn: () => fetchIndexData('$dji'), refetchInterval: 30000, retry: 2});
  const { data: usInx, isLoading: usInxLoading } = useQuery({queryKey: ['realtime','$inx'], queryFn: () => fetchIndexData('$inx'), refetchInterval: 30000, retry: 2});
  const { data: usIxic, isLoading: usIxicLoading } = useQuery({queryKey: ['realtime','$ixic'], queryFn: () => fetchIndexData('$ixic'), refetchInterval: 30000, retry: 2});

  // 板块表现
  const { data: sectorPerf = [], isLoading: sectorLoading } = useQuery({
    queryKey: ['sector-performance'],
    queryFn: () => stockAPI.getSectorPerformance(),
    refetchInterval: 60000,
  });

  // 大盘研判
  const { data: outlook, isLoading: outlookLoading } = useQuery({
    queryKey: ['market-outlook'],
    queryFn: () => stockAPI.getMarketOutlook(),
    refetchInterval: 300000,
    retry: 3,
  });

  const filteredItems = items.filter((item) => {
    if (market === 'a') return /^\d{6}$/.test(item.code);
    return /^[A-Za-z]{1,5}$/.test(item.code);
  });

  const hotSectors = sectorPerf.filter((s: any) => s.avg_change > 0).slice(0, 10);
  const top5 = sectorPerf.slice(0, 5);
  const worst3 = sectorPerf.slice(-3).reverse();

  // Market outlook helpers
  const statusColorMap: Record<string, string> = {
    bull: 'red',
    bull_neutral: 'orange',
    neutral: 'blue',
    bear_neutral: 'gold',
    bear: 'green',
  };

  const outlookScorePercent = outlook ? ((outlook.score + 100) / 2) : 50;
  const rangePosition = outlook ? ((outlook.cur_price - outlook.low_6m) / (outlook.high_6m - outlook.low_6m) * 100) : 50;

  // Debate table columns
  const debateColumns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (name: string, record: any) => (
        <Link to={`/ai-debate?code=${record.code}&job_id=${record.job_id}`}>
          <Text strong>{name}</Text>
        </Link>
      ),
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (val: string) => <Text type="secondary" style={{ fontSize: 12 }}>{val}</Text>,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => {
        const colorMap: Record<string, string> = {
          completed: 'green',
          failed: 'red',
          canceled: 'default',
          queued: 'gold',
          running: 'gold',
        };
        const labelMap: Record<string, string> = {
          completed: '已完成',
          failed: '失败',
          canceled: '已终止',
          queued: '进行中',
          running: '进行中',
        };
        return <Tag color={colorMap[status] || 'default'}>{labelMap[status] || status}</Tag>;
      },
    },
    {
      title: '操作',
      key: 'actions',
      render: (_: any, record: any) => (
        <Space size="small">
          <Button
            size="small"
            danger
            onClick={() => handleStopDebate(record.job_id)}
            disabled={record.status !== 'queued' && record.status !== 'running'}
          >
            终止
          </Button>
          <Button
            size="small"
            type="primary"
            danger
            onClick={() => handleDeleteDebate(record.job_id)}
            disabled={record.status === 'queued' || record.status === 'running'}
          >
            删除
          </Button>
        </Space>
      ),
    },
  ];

  // Sector table columns
  const sectorColumns = [
    {
      title: '#',
      dataIndex: 'rank',
      key: 'rank',
      width: 40,
      render: (_: any, __: any, index: number) => (
        <span style={{
          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
          width: 22, height: 22, borderRadius: '50%',
          background: index < 3 ? '#f5222d' : '#1677ff',
          color: '#fff', fontSize: 10, fontWeight: 'bold',
        }}>{index + 1}</span>
      ),
    },
    {
      title: '板块',
      dataIndex: 'name',
      key: 'name',
      render: (name: string) => <Text strong>{name}</Text>,
    },
    {
      title: '涨跌',
      dataIndex: 'avg_change',
      key: 'avg_change',
      render: (val: number) => (
        <Text strong style={{ color: val >= 0 ? '#cf1322' : '#3f8600' }}>
          {val >= 0 ? '+' : ''}{val.toFixed(2)}%
        </Text>
      ),
    },
    {
      title: '上涨比例',
      key: 'ratio',
      render: (_: any, record: any) => (
        <Text type="secondary" style={{ fontSize: 11 }}>
          {record.valid_stocks}/{record.total_stocks}
        </Text>
      ),
    },
    {
      title: 'ETF',
      key: 'etf',
      render: (_: any, record: any) => {
        const etfs = findEtfs(record.name);
        if (!etfs) return null;
        return (
          <Link to={`/stock/${etfs[0].code}`}>
            <Tag color="blue" style={{ fontSize: 10 }}>{etfs[0].name.replace(/ETF$/, '')}</Tag>
          </Link>
        );
      },
    },
  ];

  const A_INDICES = [
    { title: '上证指数', data: shIndex, loading: shLoading, color: '#1677ff' },
    { title: '深证成指', data: szIndex, loading: szLoading, color: '#722ed1' },
    { title: '创业板指', data: cybIndex, loading: cybLoading, color: '#eb2f96' },
  ];

  const US_INDICES = [
    { title: '道琼斯', data: usDji, loading: usDjiLoading, color: '#1677ff' },
    { title: '标普500', data: usInx, loading: usInxLoading, color: '#13c2c2' },
    { title: '纳斯达克', data: usIxic, loading: usIxicLoading, color: '#2f54eb' },
  ];

  const indices = market === 'a' ? A_INDICES : US_INDICES;

  return (
    <Row gutter={[16, 16]}>
      {/* 左侧侧边栏 - 大盘研判 */}
      <Col xs={24} lg={6}>
        <Card
          title={<Space><span>📊</span><span>操作推荐 · 大盘研判</span></Space>}
          size="small"
        >
          {outlookLoading && !outlook ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <Spin />
              <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>分析大盘数据中...</div>
            </div>
          ) : outlook && outlook.success !== false ? (
            <div>
              {/* 判定标签 */}
              <div style={{ textAlign: 'center', marginBottom: 12 }}>
                <Tag color={statusColorMap[outlook.market_status] || 'default'} style={{ fontSize: 14, padding: '4px 12px' }}>
                  {outlook.verdict}
                </Tag>
              </div>

              {/* 分数 */}
              <div style={{ marginBottom: 12 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#999', marginBottom: 4 }}>
                  <span>偏空</span>
                  <Text strong style={{ fontSize: 12 }}>{outlook.score}分</Text>
                  <span>偏多</span>
                </div>
                <Progress
                  percent={outlookScorePercent}
                  showInfo={false}
                  strokeColor={
                    outlook.score >= 0
                      ? { '0%': '#f59e0b', '100%': outlook.score > 20 ? '#ef4444' : '#f97316' }
                      : { '0%': outlook.score < -20 ? '#22c55e' : '#eab308', '100%': '#f59e0b' }
                  }
                  size="small"
                />
              </div>

              {/* 关键均线 */}
              <Descriptions size="small" column={2} style={{ marginBottom: 8 }}>
                <Descriptions.Item label="当前">{outlook.cur_price?.toFixed(0)}</Descriptions.Item>
                <Descriptions.Item label="MA20">{outlook.ma20?.toFixed(0)}</Descriptions.Item>
                <Descriptions.Item label="MA60">{outlook.ma60?.toFixed(0)}</Descriptions.Item>
                <Descriptions.Item label="MA120">{outlook.ma120?.toFixed(0)}</Descriptions.Item>
              </Descriptions>

              {/* 近6月波动区间 */}
              <div style={{ marginBottom: 8 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 10, color: '#999', marginBottom: 4 }}>
                  <span>低 {outlook.low_6m?.toFixed(0)}</span>
                  <span>近6月区间</span>
                  <span>高 {outlook.high_6m?.toFixed(0)}</span>
                </div>
                <div style={{ height: 6, background: 'linear-gradient(90deg, #22c55e, #facc15, #ef4444)', borderRadius: 3, position: 'relative' }}>
                  <div style={{
                    position: 'absolute', top: -1, width: 2, height: 8,
                    background: '#000', borderRadius: 1,
                    left: `${Math.min(100, Math.max(0, rangePosition))}%`,
                  }} />
                </div>
              </div>

              {/* 近期涨跌 */}
              <Descriptions size="small" column={3} style={{ marginBottom: 8 }}>
                <Descriptions.Item label="近1月">
                  <Text style={{ color: outlook.pct_30d >= 0 ? '#cf1322' : '#3f8600', fontSize: 11 }}>
                    {outlook.pct_30d >= 0 ? '+' : ''}{outlook.pct_30d}%
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="近2月">
                  <Text style={{ color: outlook.pct_60d >= 0 ? '#cf1322' : '#3f8600', fontSize: 11 }}>
                    {outlook.pct_60d >= 0 ? '+' : ''}{outlook.pct_60d}%
                  </Text>
                </Descriptions.Item>
                <Descriptions.Item label="近6月">
                  <Text style={{ color: outlook.pct_120d >= 0 ? '#cf1322' : '#3f8600', fontSize: 11 }}>
                    {outlook.pct_120d >= 0 ? '+' : ''}{outlook.pct_120d}%
                  </Text>
                </Descriptions.Item>
              </Descriptions>

              {/* 操作建议 */}
              <Card size="small" style={{ marginBottom: 8, background: '#e6f4ff', border: '1px solid #91caff' }}>
                <Text strong style={{ fontSize: 11 }}>📋 操作建议</Text>
                <div style={{ fontSize: 11, color: '#595959', marginTop: 4 }}>{outlook.suggest}</div>
              </Card>

              {/* 未来1月展望 */}
              <Card size="small" style={{ marginBottom: 8, background: '#f9f0ff', border: '1px solid #d3adf7' }}>
                <Text strong style={{ fontSize: 11 }}>🔮 未来1月展望</Text>
                <div style={{ fontSize: 11, color: '#595959', marginTop: 4 }}>{outlook.outlook}</div>
              </Card>

              {/* 评分依据 */}
              <details style={{ fontSize: 11 }}>
                <summary style={{ color: '#999', cursor: 'pointer' }}>
                  评分依据 ({outlook.reasons?.length || 0}条)
                </summary>
                <ul style={{ marginTop: 4, paddingLeft: 16 }}>
                  {outlook.reasons?.map((r: string, i: number) => (
                    <li key={i} style={{ color: '#666', lineHeight: 1.6 }}>{r}</li>
                  ))}
                </ul>
              </details>
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '24px 0', color: '#999', fontSize: 12 }}>
              数据获取失败
            </div>
          )}
        </Card>
      </Col>

      {/* 主内容区 */}
      <Col xs={24} lg={12}>
        {/* 市场切换 */}
        <Segmented
          options={MARKET_SEGMENTED_OPTIONS}
          value={market}
          onChange={(val) => setMarket(val as 'a' | 'us')}
          style={{ marginBottom: 16 }}
        />

        {/* 三大指数 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          {indices.map((idx) => (
            <Col xs={24} md={8} key={idx.title}>
              <IndexCard
                title={idx.title}
                data={idx.data}
                isLoading={idx.loading}
                color={idx.color}
              />
            </Col>
          ))}
        </Row>

        {/* 自选股 */}
        <Card
          title={<Space>{market === 'a' ? 'A股自选' : '美股自选'}<Tag>{filteredItems.length}只</Tag></Space>}
          extra={<Link to="/watchlist">管理自选</Link>}
          style={{ marginBottom: 16 }}
        >
          {filteredItems.length === 0 ? (
            <Empty description={market === 'a' ? '暂无A股自选' : '暂无美股自选'}>
              <Link to="/watchlist">添加自选股</Link>
            </Empty>
          ) : (
            <Row gutter={[16, 16]}>
              {filteredItems.map((item) => (
                <Col xs={24} md={12} lg={8} key={item.code}>
                  <StockCard code={item.code} name={item.name} />
                </Col>
              ))}
            </Row>
          )}
        </Card>

        {/* 辩论记录 */}
        <Card
          title="辩论记录"
          extra={
            <Segmented
              options={[
                { label: '进行中', value: 'active' },
                { label: '已完成', value: 'completed' },
              ]}
              value={debateFilter}
              onChange={(val) => setDebateFilter(val as 'active' | 'completed')}
            />
          }
        >
          {debateLoading ? (
            <div style={{ textAlign: 'center', padding: '24px 0' }}>
              <Spin />
            </div>
          ) : debateJobs.length === 0 ? (
            <Empty description="暂无任务" />
          ) : (
            <Table
              dataSource={debateJobs}
              columns={debateColumns}
              rowKey="job_id"
              size="small"
              pagination={false}
            />
          )}
        </Card>
      </Col>

      {/* 右侧侧边栏 - 板块市场预览（仅A股） */}
      {market === 'a' && (
        <Col xs={24} lg={6}>
          {/* 今日热点板块 */}
          <Card
            title={
              <Space>
                <span>🔥</span>
                <span>今日热点板块</span>
                {sectorLoading && <Spin size="small" />}
              </Space>
            }
            size="small"
            style={{ marginBottom: 16 }}
          >
            {sectorLoading && hotSectors.length === 0 ? (
              <div style={{ textAlign: 'center', padding: '24px 0', color: '#999', fontSize: 12 }}>
                计算板块表现中...
              </div>
            ) : (
              <Table
                dataSource={hotSectors.slice(0, 8).map((s: any, i: number) => ({ ...s, key: s.name, rank: i + 1 }))}
                columns={sectorColumns.filter(c => c.key !== 'rank')}
                size="small"
                pagination={false}
                showHeader={false}
                rowKey="name"
              />
            )}
            <div style={{ textAlign: 'center', fontSize: 10, color: '#bbb', marginTop: 8 }}>
              {sectorPerf.reduce((a: number, s: any) => a + s.valid_stocks, 0)} 只成分股
            </div>
          </Card>

          {/* TOP 5 + 偏弱 */}
          <Row gutter={12} style={{ marginBottom: 16 }}>
            <Col span={12}>
              <Card title={<Space><RiseOutlined /><span>最强 TOP 5</span></Space>} size="small">
                {top5.map((s: any, i: number) => (
                  <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <Text style={{ fontSize: 11 }} ellipsis>{i + 1}. {s.name}</Text>
                    <Text strong style={{ color: '#cf1322', fontSize: 11 }}>+{s.avg_change.toFixed(1)}%</Text>
                  </div>
                ))}
              </Card>
            </Col>
            <Col span={12}>
              <Card title={<Space><FallOutlined /><span>偏弱 TOP 3</span></Space>} size="small">
                {worst3.map((s: any, i: number) => (
                  <div key={s.name} style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                    <Text style={{ fontSize: 11 }} ellipsis>{i + 1}. {s.name}</Text>
                    <Text strong style={{ color: '#3f8600', fontSize: 11 }}>{s.avg_change.toFixed(1)}%</Text>
                  </div>
                ))}
              </Card>
            </Col>
          </Row>

          {/* 下一个主线预测 */}
          <Card
            title={<Space><span>🔮</span><span>下一个主线预测</span></Space>}
            size="small"
            style={{ borderLeft: '4px solid #722ed1' }}
          >
            {hotSectors.length > 0 ? (
              <div>
                <Text style={{ fontSize: 12 }}>
                  当前：<Text strong style={{ color: '#cf1322' }}>{hotSectors[0]?.name}</Text>
                  {findEtfs(hotSectors[0]?.name) && (
                    <Link to={`/stock/${findEtfs(hotSectors[0]?.name)![0].code}`} style={{ marginLeft: 6, fontSize: 10 }}>
                      → {findEtfs(hotSectors[0]?.name)![0].name}
                    </Link>
                  )}
                </Text>
                <div style={{ fontSize: 11, color: '#999', marginTop: 8 }}>
                  {(() => {
                    if (hotSectors.length < 2) return '数据不足，难以预测';
                    const top = hotSectors[0];
                    const second = hotSectors[1];
                    const gap = (top.avg_change - second.avg_change).toFixed(2);
                    if (parseFloat(gap) > 2) return `💡 ${top.name} 领先优势明显（+${gap}%），预计仍为主线。关注低位补涨。`;
                    return `📊 ${top.name} 与 ${second.name} 差距仅 ${gap}%，若 ${second.name} 放量有望轮动为新主线。`;
                  })()}
                </div>
                <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {hotSectors.slice(0, 5).map((s: any) => {
                    const etfs = findEtfs(s.name);
                    return (
                      <Tag
                        key={s.name}
                        color={s.avg_change > 0 ? 'red' : 'green'}
                        style={{ fontSize: 10, opacity: !etfs ? 0.6 : 1, cursor: etfs ? 'pointer' : 'not-allowed' }}
                      >
                        {etfs ? (
                          <Link to={`/stock/${etfs[0].code}`} style={{ color: 'inherit' }}>
                            {s.name} {s.avg_change >= 0 ? '+' : ''}{s.avg_change.toFixed(1)}%
                          </Link>
                        ) : (
                          <span>{s.name} {s.avg_change >= 0 ? '+' : ''}{s.avg_change.toFixed(1)}%</span>
                        )}
                      </Tag>
                    );
                  })}
                </div>
              </div>
            ) : (
              <Text type="secondary" style={{ fontSize: 12 }}>计算板块表现中...</Text>
            )}
          </Card>
        </Col>
      )}
    </Row>
  );
}

function StockCard({ code, name }: { code: string; name?: string }) {
  const { data, isLoading } = useQuery({
    queryKey: ['realtime', code],
    queryFn: () => stockAPI.getRealtime(code),
    refetchInterval: getRefetchInterval(),
  });

  return (
    <Card size="small" hoverable>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
        <Link to={`/stock/${code}`}>
          <Text strong style={{ fontSize: 16 }}>{name || code}</Text>
          <br />
          <Text type="secondary" style={{ fontSize: 12 }}>{code}</Text>
        </Link>
      </div>
      {isLoading ? (
        <Spin size="small" />
      ) : data ? (
        <div>
          <Text strong style={{ fontSize: 20 }}>
            {/^\d{6}$/.test(code) ? '¥' : '$'}{data.current_price?.toFixed(2)}
          </Text>
          <br />
          <Text strong style={{ fontSize: 16, color: data.change_percent >= 0 ? '#cf1322' : '#3f8600' }}>
            {data.change_percent >= 0 ? '+' : ''}{data.change_percent?.toFixed(2)}%
          </Text>
          <div style={{ marginTop: 8 }}>
            <AIAnalyzeButton code={code} className="" />
          </div>
        </div>
      ) : (
        <Text type="secondary">数据获取失败</Text>
      )}
    </Card>
  );
}
