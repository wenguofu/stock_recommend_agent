import { useState, useEffect, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Button, Card, Tag, Select, Input, Space, Typography, Spin, Progress, Alert, Modal, Empty, Descriptions } from 'antd';
import { PlayCircleOutlined, CheckCircleOutlined, CloseCircleOutlined, DownloadOutlined, ReloadOutlined, RightOutlined } from '@ant-design/icons';
import { stockAPI, type StrategyDetail, type WatchlistItem, type DebateStep } from '../services/api';
import ApplyToPaperPanel from '../components/ApplyToPaperPanel';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const { Title, Text, Paragraph } = Typography;

type Stage = 'select' | 'running' | 'done';
type Mode = 'fast' | 'balanced' | 'deep';

const MODE_CONFIG: Record<Mode, { analysisRounds: number; debateRounds: number; label: string }> = {
  fast: { analysisRounds: 1, debateRounds: 0, label: '快速模式' },
  balanced: { analysisRounds: 2, debateRounds: 1, label: '均衡模式' },
  deep: { analysisRounds: 3, debateRounds: 2, label: '深入模式' },
};

export default function StrategyRun() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const strategyId = parseInt(id || '0');

  const [stage, setStage] = useState<Stage>('select');
  const [selectedCodes, setSelectedCodes] = useState<string[]>([]);
  const [selectedSectors, setSelectedSectors] = useState<string[]>([]);
  const [manualCode, setManualCode] = useState('');
  const [mode, setMode] = useState<Mode>('balanced');
  const [jobId, setJobId] = useState('');
  const [jobName, setJobName] = useState('');
  const [error, setError] = useState('');
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<string>('');

  // 加载策略详情
  const { data: strategy, isLoading: strategyLoading } = useQuery<StrategyDetail>({
    queryKey: ['strategy-run', strategyId],
    queryFn: () => stockAPI.getStrategyDetail(strategyId),
    enabled: !!strategyId,
  });

  // 加载自选股
  const { data: watchlist } = useQuery<WatchlistItem[]>({
    queryKey: ['watchlist'],
    queryFn: () => stockAPI.getWatchlist(),
  });

  // 加载板块列表
  const { data: sectors = [] } = useQuery<string[]>({
    queryKey: ['sectors'],
    queryFn: () => stockAPI.listSectors(),
  });

  const addSector = async (sector: string) => {
    if (selectedSectors.includes(sector)) return;
    setSelectedSectors((prev) => [...prev, sector]);
    const stocks = await stockAPI.getSectorStocks(sector);
    const codes = stocks.map((s) => s.code).filter((c) => !selectedCodes.includes(c));
    setSelectedCodes((prev) => [...prev, ...codes]);
  };

  const removeSector = (sector: string) => {
    setSelectedSectors((prev) => prev.filter((s) => s !== sector));
    stockAPI.getSectorStocks(sector).then((stocks) => {
      const sectorCodes = stocks.map((s) => s.code);
      setSelectedCodes((prev) => prev.filter((c) => !sectorCodes.includes(c)));
    });
  };

  // 轮询任务状态
  const { data: jobStatus } = useQuery({
    queryKey: ['strategy-run-status', jobId],
    queryFn: () => stockAPI.getDebateJobStatus(jobId),
    enabled: !!jobId && stage === 'running',
    refetchInterval: 2000,
  });

  // 任务完成时自动切换状态
  useEffect(() => {
    if (!jobStatus) return;
    if (jobStatus.status === 'completed' || jobStatus.status === 'failed' || jobStatus.status === 'canceled') {
      setStage('done');
    }
  }, [jobStatus]);

  // 自动应用策略Agent
  useEffect(() => {
    if (strategy && !applying && applyResult === '') {
      setApplying(true);
      stockAPI.applyStrategy(strategyId)
        .then((res) => setApplyResult(`已就绪 (${res.count}个Agent)`))
        .catch(() => setApplyResult('Agent就绪'))
        .finally(() => setApplying(false));
    }
  }, [strategy, strategyId, applying, applyResult]);

  const toggleCode = (code: string) => {
    setSelectedCodes((prev) =>
      prev.includes(code) ? prev.filter((c) => c !== code) : [...prev, code]
    );
  };

  const addManualCode = () => {
    const c = manualCode.trim();
    if (c && !selectedCodes.includes(c)) {
      setSelectedCodes((prev) => [...prev, c]);
    }
    setManualCode('');
  };

  const removeCode = (code: string) => {
    setSelectedCodes((prev) => prev.filter((c) => c !== code));
  };

  const handleStart = async () => {
    if (selectedCodes.length === 0) {
      setError('请至少选择1只股票');
      return;
    }
    setError('');
    setStage('running');

    try {
      const config = MODE_CONFIG[mode];
      const res = await stockAPI.runStrategy(strategyId, selectedCodes, config.analysisRounds, config.debateRounds);
      setJobId(res.data.job_id);
      setJobName(res.data.name);
    } catch (e: any) {
      setError(`启动失败: ${e.message}`);
      setStage('select');
    }
  };

  // 渲染Markdown报告
  const reportHtml = useMemo(() => {
    if (!jobStatus?.report_md) return '';
    const raw = marked.parse(jobStatus.report_md, { gfm: true, breaks: true });
    return DOMPurify.sanitize(raw as string);
  }, [jobStatus?.report_md]);

  const steps = jobStatus?.steps || [];
  const groupedSteps = useMemo(() => {
    const map = new Map<number, { agent_id: number; agent_name: string; items: DebateStep[] }>();
    steps.forEach((step) => {
      if (!map.has(step.agent_id)) {
        map.set(step.agent_id, { agent_id: step.agent_id, agent_name: step.agent_name, items: [] });
      }
      map.get(step.agent_id)?.items.push(step);
    });
    return Array.from(map.values());
  }, [steps]);

  if (strategyLoading || !strategy) {
    return (
      <div style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', padding: '80px 0' }}>
        <div style={{ textAlign: 'center' }}>
          <Spin size="large" />
          <div style={{ marginTop: 16 }}>
            <Text type="secondary">加载策略...</Text>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* 策略信息头部 */}
      <Card style={{ background: 'linear-gradient(135deg, #1677ff, #722ed1)', border: 'none', color: '#fff' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <Title level={2} style={{ color: '#fff', margin: 0 }}>{strategy.name}</Title>
            <Paragraph style={{ color: 'rgba(255,255,255,0.8)', margin: '8px 0 12px' }}>
              {strategy.description?.slice(0, 120)}
            </Paragraph>
            <Space>
              <Tag style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: '#fff' }}>
                {strategy.agent_configs.length}个Agent
              </Tag>
              <Tag style={{ background: 'rgba(255,255,255,0.2)', border: 'none', color: '#fff' }}>
                {applyResult ? (applying ? '准备Agent中...' : applyResult) : '加载中...'}
              </Tag>
              {jobName && <Tag style={{ background: 'rgba(82,196,26,0.3)', border: 'none', color: '#fff' }}>运行中</Tag>}
            </Space>
          </div>
        </div>
      </Card>

      {stage === 'select' && (
        <>
          {/* 模式选择 */}
          <Card title="分析模式">
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: 12 }}>
              {(['fast', 'balanced', 'deep'] as Mode[]).map((m) => {
                const cfg = MODE_CONFIG[m];
                return (
                  <Card
                    key={m}
                    hoverable
                    onClick={() => setMode(m)}
                    style={{
                      borderColor: mode === m ? '#1677ff' : '#d9d9d9',
                      background: mode === m ? '#e6f4ff' : '#fff',
                      cursor: 'pointer',
                    }}
                    styles={{ body: { padding: 16 } }}
                  >
                    <Text strong>{cfg.label}</Text>
                    <div>
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        {cfg.analysisRounds}轮分析{cfg.debateRounds > 0 ? ` + ${cfg.debateRounds}轮辩论` : '（无辩论）'}
                      </Text>
                    </div>
                  </Card>
                );
              })}
            </div>
          </Card>

          {/* 选股 */}
          <Card
            title={
              <div style={{ display: 'flex', justifyContent: 'space-between', width: '100%' }}>
                <span>选择股票</span>
                <Text type="secondary" style={{ fontSize: 13 }}>已选 {selectedCodes.length} 只</Text>
              </div>
            }
          >
            {/* 按板块添加 */}
            <Card
              size="small"
              style={{ background: '#e6f4ff', borderColor: '#91caff', marginBottom: 16 }}
              styles={{ body: { padding: 12 } }}
            >
              <Text strong style={{ color: '#1677ff', display: 'block', marginBottom: 8 }}>📂 按板块批量添加</Text>
              <Select
                value={undefined}
                onChange={(value) => { if (value) addSector(value); }}
                placeholder="-- 选择板块 --"
                style={{ width: '100%' }}
                options={sectors.map((s) => ({
                  value: s,
                  label: s,
                  disabled: selectedSectors.includes(s),
                }))}
              />
              {selectedSectors.length > 0 && (
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 8 }}>
                  {selectedSectors.map((s) => (
                    <Tag key={s} closable onClose={() => removeSector(s)} color="blue" style={{ margin: 0 }}>
                      📁 {s}
                    </Tag>
                  ))}
                </div>
              )}
            </Card>

            {/* 手动输入 */}
            <Space.Compact style={{ width: '100%', marginBottom: 16 }}>
              <Input
                value={manualCode}
                onChange={(e) => setManualCode(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addManualCode()}
                placeholder="输入股票代码（如 603290）"
              />
              <Button type="primary" onClick={addManualCode} disabled={!manualCode.trim()}>
                添加
              </Button>
            </Space.Compact>

            {/* 已选股票标签 */}
            {selectedCodes.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 16 }}>
                {selectedCodes.map((code) => (
                  <Tag key={code} closable onClose={() => removeCode(code)} color="blue">
                    {code}
                  </Tag>
                ))}
              </div>
            )}

            {/* 自选股列表 */}
            <Text strong style={{ display: 'block', marginBottom: 8 }}>自选股</Text>
            {watchlist && watchlist.length > 0 ? (
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(150px, 1fr))', gap: 8 }}>
                {watchlist.map((item) => (
                  <Card
                    key={item.code}
                    hoverable
                    size="small"
                    onClick={() => toggleCode(item.code)}
                    style={{
                      borderColor: selectedCodes.includes(item.code) ? '#1677ff' : '#d9d9d9',
                      background: selectedCodes.includes(item.code) ? '#e6f4ff' : '#fff',
                    }}
                    styles={{ body: { padding: 8 } }}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      <div style={{
                        width: 8, height: 8, borderRadius: '50%',
                        background: selectedCodes.includes(item.code) ? '#1677ff' : '#d9d9d9',
                        flexShrink: 0,
                      }} />
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontWeight: 500, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 13 }}>
                          {item.name}
                        </div>
                        <Text type="secondary" style={{ fontSize: 11 }}>{item.code}</Text>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <Empty description="暂无自选股，请先在自选页面添加" image={Empty.PRESENTED_IMAGE_SIMPLE} />
            )}
          </Card>

          {/* Agent列表预览 */}
          <Card title={`参与Agent（${strategy.agent_configs.length}个）`}>
            <Space wrap>
              {strategy.agent_configs.map((a, i) => (
                <Tag key={i} style={{ padding: '4px 12px', fontSize: 13 }}>{a.name}</Tag>
              ))}
            </Space>
          </Card>

          {/* 错误提示 */}
          {error && (
            <Alert message={error} type="error" showIcon closable onClose={() => setError('')} />
          )}

          {/* 启动按钮 */}
          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <Button
              type="primary"
              size="large"
              icon={<PlayCircleOutlined />}
              onClick={handleStart}
              disabled={selectedCodes.length === 0}
              style={{
                padding: '12px 40px',
                height: 'auto',
                fontSize: 18,
                fontWeight: 600,
                background: 'linear-gradient(135deg, #1677ff, #722ed1)',
                border: 'none',
              }}
            >
              启动 {strategy.name} 分析
            </Button>
          </div>
        </>
      )}

      {stage === 'running' && (
        <Card>
          <div style={{ textAlign: 'center', padding: '32px 0' }}>
            <Spin size="large" />
            <Title level={3} style={{ margin: '16px 0 8px' }}>
              {jobName || '分析进行中...'}
            </Title>
            <Text type="secondary" style={{ display: 'block', marginBottom: 12 }}>
              进度：{jobStatus?.progress || 0}% | 状态：{jobStatus?.status || '排队中'}
            </Text>
            <div style={{ maxWidth: 400, margin: '0 auto' }}>
              <Progress percent={jobStatus?.progress || 0} status="active" />
            </div>
          </div>

          {/* Agent实时输出 */}
          {groupedSteps.length > 0 && (
            <div style={{ marginTop: 24 }}>
              <Title level={5}>实时分析</Title>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {groupedSteps.map((group) => (
                  <Card
                    key={group.agent_id}
                    size="small"
                    title={
                      <Space>
                        <Text strong>{group.agent_name}</Text>
                        <Tag>{group.items.length}轮</Tag>
                      </Space>
                    }
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {group.items.map((step, i) => (
                        <div key={i} style={{ padding: 12, background: '#fafafa', borderRadius: 6 }}>
                          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
                            第{step.round}轮 {step.phase === 'analysis' ? '分析' : '辩论'}
                          </Text>
                          <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13, fontFamily: 'inherit', lineHeight: 1.6, color: '#595959' }}>
                            {step.content.slice(0, 500)}{step.content.length > 500 ? '...' : ''}
                          </pre>
                        </div>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}
        </Card>
      )}

      {stage === 'done' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
          {/* 完成状态 */}
          <Alert
            type={jobStatus?.status === 'completed' ? 'success' : 'error'}
            showIcon
            icon={jobStatus?.status === 'completed' ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
            message={
              <Title level={4} style={{ margin: 0 }}>
                {jobStatus?.status === 'completed' ? '分析完成！' : '分析失败'}
              </Title>
            }
            description={jobName}
            action={
              <Space>
                <Button type="primary" onClick={() => navigate(`/ai-debate?job_id=${jobId}&code=${selectedCodes.join(',')}`)}>
                  查看完整报告
                </Button>
                <Button onClick={() => { setStage('select'); setJobId(''); setJobName(''); }}>
                  重新运行
                </Button>
              </Space>
            }
          />

          {/* 报告预览 */}
          {reportHtml && (
            <Card
              title="分析报告"
              extra={
                <Button
                  type="primary"
                  icon={<DownloadOutlined />}
                  size="small"
                  onClick={() => {
                    if (!jobStatus?.report_md) return;
                    const blob = new Blob([jobStatus.report_md], { type: 'text/markdown;charset=utf-8' });
                    const url = window.URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = `strategy_report_${selectedCodes.join('_')}.md`;
                    a.click();
                    window.URL.revokeObjectURL(url);
                  }}
                >
                  导出报告
                </Button>
              }
            >
              <div className="prose dark:prose-invert max-w-none" dangerouslySetInnerHTML={{ __html: reportHtml }} />
            </Card>
          )}

          {/* 应用到模拟盘 */}
          {jobStatus?.status === 'completed' && (
            <ApplyToPaperPanel
              codes={selectedCodes}
              jobName={jobName}
              strategyRunId={jobId}
            />
          )}

          {/* 完整Agent输出 */}
          {groupedSteps.length > 0 && (
            <Card title="完整Agent输出">
              <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
                {groupedSteps.map((group) => (
                  <Card
                    key={group.agent_id}
                    size="small"
                    title={
                      <Space>
                        <Text strong>{group.agent_name}</Text>
                        <Tag>{group.items.length}轮</Tag>
                      </Space>
                    }
                  >
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                      {group.items.map((step, i) => (
                        <div key={i} style={{ padding: 16, background: '#fafafa', borderRadius: 6 }}>
                          <Text style={{ color: '#1677ff', fontSize: 12, fontWeight: 500, display: 'block', marginBottom: 8 }}>
                            {step.phase === 'analysis' ? '📝 分析' : '💬 辩论'} · 第{step.round}轮 · {new Date(step.timestamp).toLocaleTimeString()}
                          </Text>
                          <pre style={{ whiteSpace: 'pre-wrap', margin: 0, fontSize: 13, fontFamily: 'inherit', lineHeight: 1.6, color: '#595959' }}>{step.content}</pre>
                        </div>
                      ))}
                    </div>
                  </Card>
                ))}
              </div>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
