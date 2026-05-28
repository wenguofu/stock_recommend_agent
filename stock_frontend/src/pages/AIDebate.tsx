import { useEffect, useMemo, useRef, useState } from 'react';
import { useLocation, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Card, Progress, Button, Space, Typography, Spin, Tag, Row, Col, Collapse, Empty, Descriptions, Input } from 'antd';
import {
  StopOutlined,
  DeleteOutlined,
  ExportOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  PauseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import { stockAPI } from '../services/api';
import type { DebateJobStatus, DebateStep, StockComprehensive, StockRealtime } from '../services/api';
import { marked } from 'marked';
import DOMPurify from 'dompurify';

const { Title, Text, Paragraph } = Typography;

export default function AIDebate() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const codeFromQuery = searchParams.get('code') || '';
  const jobIdFromQuery = searchParams.get('job_id') || searchParams.get('jobId') || '';
  const state = (location.state || {}) as {
    code?: string;
    agentIds?: number[];
    analysisRounds?: number;
    debateRounds?: number;
    modeLabel?: string;
  };
  const [jobId, setJobId] = useState(jobIdFromQuery);
  const [starting, setStarting] = useState(false);

  const { data, isLoading, isError, error } = useQuery<DebateJobStatus>({
    queryKey: ['ai-debate-status', jobId],
    queryFn: () => stockAPI.getDebateJobStatus(jobId),
    enabled: !!jobId,
    refetchInterval: (query) => {
      const d = query.state.data;
      if (!d) return 2000;
      return (d as DebateJobStatus).status === 'completed' || (d as DebateJobStatus).status === 'failed' ? false : 2000;
    },
  });

  const effectiveAnalysisRounds = data?.analysis_rounds || state.analysisRounds || parseInt(searchParams.get('ar') || '3', 10);
  const effectiveDebateRounds = data?.debate_rounds || state.debateRounds || parseInt(searchParams.get('dr') || '3', 10);

  const code = state.code || codeFromQuery || data?.code || '';
  const agentIds = state.agentIds || data?.agent_ids || [];
  const modeLabel = state.modeLabel || '自定义模式';

  useEffect(() => {
    if (!jobId && code && agentIds.length >= 2 && !starting) {
      setStarting(true);
      stockAPI
        .startDebateJob(code, agentIds, effectiveAnalysisRounds, effectiveDebateRounds)
        .then((res) => {
          setJobId(res.job_id);
          setSearchParams({ code, job_id: res.job_id, ar: String(effectiveAnalysisRounds), dr: String(effectiveDebateRounds) });
        })
        .catch((err) => {
          console.error('启动辩论失败:', err);
        })
        .finally(() => setStarting(false));
    }
  }, [jobId, code, agentIds, starting, setSearchParams, effectiveAnalysisRounds, effectiveDebateRounds]);

  const steps = useMemo(() => data?.steps || [], [data]);
  const reportMd = data?.report_md || '';
  const status = data?.status || (starting ? 'queued' : 'queued');

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

  const reportHtml = useMemo(() => {
    if (!reportMd) return '';
    const raw = marked.parse(reportMd, { gfm: true, breaks: true });
    return DOMPurify.sanitize(raw as string);
  }, [reportMd]);

  // 注入markdown-body样式
  useEffect(() => {
    const styleId = 'md-body-style';
    if (!document.getElementById(styleId)) {
      const style = document.createElement('style');
      style.id = styleId;
      style.textContent = `
        .markdown-body h1, .markdown-body h2, .markdown-body h3 {
          font-weight: 700;
          margin: 0.75rem 0 0.5rem;
        }
        .markdown-body table { width: 100%; border-collapse: collapse; margin: 0.75rem 0; }
        .markdown-body th, .markdown-body td { border: 1px solid #e5e7eb; padding: 6px 8px; text-align: left; }
        .markdown-body blockquote { border-left: 3px solid #cbd5e1; padding-left: 0.75rem; margin: 0.5rem 0; }
      `;
      document.head.appendChild(style);
    }
  }, []);

  useEffect(() => {
    if (!code && data?.code) {
      setSearchParams({ code: data.code, job_id: jobId });
    }
  }, [code, data?.code, jobId, setSearchParams]);

  const handleExport = () => {
    if (!reportMd) return;
    const blob = new Blob([reportMd], { type: 'text/markdown;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `ai_report_${code}.md`;
    a.click();
    window.URL.revokeObjectURL(url);
  };

  if (!code && !jobId) {
    return (
      <Card>
        <Empty description="缺少股票代码或任务ID，请从AI分析入口进入。" />
      </Card>
    );
  }

  const displayCode = code || data?.code || '';
  const displayName = data?.name || displayCode;
  const isMultiSelect = (data?.meta?.mode === 'multi_select') || displayCode.includes(',');

  const effectiveCode = !isMultiSelect ? displayCode : '';
  const { data: realtimeData } = useQuery<StockRealtime>({
    queryKey: ['realtime', effectiveCode],
    queryFn: () => stockAPI.getRealtime(effectiveCode),
    enabled: !!effectiveCode,
  });

  const { data: comprehensiveData } = useQuery<StockComprehensive>({
    queryKey: ['comprehensive', effectiveCode],
    queryFn: () => stockAPI.getComprehensive(effectiveCode),
    enabled: !!effectiveCode,
  });

  const { data: sentimentData } = useQuery({
    queryKey: ['sentiment', effectiveCode],
    queryFn: () => stockAPI.getSentiment(effectiveCode, 7),
    enabled: !!effectiveCode,
  });

  const formatNumber = (value?: number, digits: number = 2) => {
    if (value == null || Number.isNaN(value)) return '--';
    return Number(value).toFixed(digits);
  };

  const handleStop = async () => {
    if (!jobId) return;
    await stockAPI.stopDebateJob(jobId);
  };

  const handleDelete = async () => {
    if (!jobId) return;
    await stockAPI.deleteDebateJob(jobId);
    window.location.href = '/';
  };

  const getStatusTag = () => {
    switch (status) {
      case 'completed':
        return <Tag color="success" icon={<CheckCircleOutlined />}>分析完成</Tag>;
      case 'failed':
        return <Tag color="error" icon={<CloseCircleOutlined />}>分析失败</Tag>;
      case 'canceled':
        return <Tag color="warning" icon={<PauseCircleOutlined />}>已终止</Tag>;
      case 'queued':
        return <Tag icon={<ClockCircleOutlined />}>排队等待中</Tag>;
      case 'running':
        return <Tag color="processing" icon={<LoadingOutlined />}>分析中</Tag>;
      default:
        return <Tag>未知</Tag>;
    }
  };

  const getProgressPercent = () => {
    if (status === 'completed') return 100;
    if (status === 'failed' || status === 'canceled') return 100;
    if (data?.progress) return Math.max(data.progress, 3);
    return undefined;
  };

  const getProgressStatus = (): 'success' | 'exception' | 'active' | 'normal' => {
    if (status === 'completed') return 'success';
    if (status === 'failed' || status === 'canceled') return 'exception';
    if (data?.progress) return 'active';
    return 'active';
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <Row justify="space-between" align="middle">
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            TradingAgents 辩论分析 - {displayName || '未知股票'}
          </Title>
          <Text type="secondary">
            {modeLabel} · 思考{effectiveAnalysisRounds} / 辩论{effectiveDebateRounds}
          </Text>
        </Col>
        <Col>
          <Space>
            <Button
              icon={<StopOutlined />}
              onClick={handleStop}
              disabled={!jobId || status === 'completed' || status === 'failed' || status === 'canceled'}
              style={{ borderColor: '#faad14', color: '#faad14' }}
            >
              终止
            </Button>
            <Button
              danger
              icon={<DeleteOutlined />}
              onClick={handleDelete}
              disabled={!jobId || status === 'queued' || status === 'running'}
            >
              删除
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 进度条 */}
      <Card>
        <Text type="secondary">
          进度提示：多轮分析与辩论可能耗时较长（约10分钟），可离开页面后稍后回来查看
        </Text>
        <div style={{ marginTop: 12 }}>
          <Progress
            percent={getProgressPercent()}
            status={getProgressStatus()}
            strokeColor={{
              '0%': '#b37feb',
              '100%': '#722ed1',
            }}
          />
        </div>
        <div style={{ marginTop: 8 }}>
          <Space>
            {getStatusTag()}
            {data?.progress ? <Text strong>{data.progress}%</Text> : null}
            {data?.progress_detail?.length ? (
              <Tag color="purple">{data.progress_detail[data.progress_detail.length - 1]}</Tag>
            ) : null}
          </Space>
        </div>
        {/* 历史进度记录 */}
        {(() => {
          const progressDetail = data?.progress_detail;
          if (!progressDetail?.length) return null;
          return (
            <div style={{ marginTop: 12, maxHeight: 100, overflow: 'auto' }}>
              <Space direction="vertical" size={4}>
                {progressDetail.map((d: string, i: number) => (
                  <Text key={i} type={i === progressDetail.length - 1 && status === 'running' ? undefined : 'secondary'} style={{ fontSize: 12 }}>
                    {i === progressDetail.length - 1 && status === 'running' ? (
                      <LoadingOutlined style={{ marginRight: 8 }} />
                    ) : (
                      <CheckCircleOutlined style={{ color: '#52c41a', marginRight: 8 }} />
                    )}
                    {d}
                  </Text>
                ))}
              </Space>
            </div>
          );
        })()}
      </Card>

      {/* 思考过程 */}
      <Card title="专家思考过程（可滚动）" style={{ maxHeight: 520 }}>
        {isLoading && (
          <div style={{ textAlign: 'center', padding: 24 }}>
            <Spin tip="分析中，内容将自动加载..." />
          </div>
        )}
        {isError && (
          <Text type="danger">分析失败：{(error as Error).message}</Text>
        )}
        {data?.error && (
          <Text type="danger">分析失败：{data.error}</Text>
        )}
        {!isLoading && groupedSteps.length === 0 && !isError && (
          <Text type="secondary">暂无内容</Text>
        )}
        <Row gutter={[12, 12]}>
          {groupedSteps.map((group) => (
            <Col xs={24} md={12} key={group.agent_id}>
              <Card
                size="small"
                title={<Text strong>{group.agent_name}</Text>}
                style={{ maxHeight: 320, overflow: 'auto' }}
              >
                <Space direction="vertical" size="small" style={{ width: '100%' }}>
                  {group.items.map((step, index) => (
                    <Card
                      key={`${step.phase}-${step.round}-${step.agent_id}-${index}`}
                      size="small"
                      type="inner"
                    >
                      <Row justify="space-between" align="middle" style={{ marginBottom: 4 }}>
                        <Col>
                          <Tag color="purple">
                            {step.phase === 'analysis' ? '分析' : '辩论'} · 第{step.round}轮
                          </Tag>
                        </Col>
                        <Col>
                          <Text type="secondary" style={{ fontSize: 12 }}>{step.timestamp}</Text>
                        </Col>
                      </Row>
                      <Paragraph
                        style={{ whiteSpace: 'pre-wrap', marginBottom: 0, fontSize: 13 }}
                      >
                        {step.content}
                      </Paragraph>
                    </Card>
                  ))}
                </Space>
              </Card>
            </Col>
          ))}
        </Row>
      </Card>

      {/* 基础信息 */}
      <Card title="基础信息（接口数据）">
        {isMultiSelect ? (
          <div>
            <Text type="secondary">多选一候选股票</Text>
            <div style={{ marginTop: 8 }}>
              <Space wrap>
                {displayCode.split(',').filter(Boolean).map((item) => (
                  <Tag key={item} color="blue">{item}</Tag>
                ))}
              </Space>
            </div>
            <Text type="secondary" style={{ display: 'block', marginTop: 12, fontSize: 12 }}>
              多选一模式不展示单只股票的实时与舆情面板，请查看最终报告中的综合结论。
            </Text>
          </div>
        ) : (
          <Row gutter={[16, 16]}>
            <Col xs={24} md={12}>
              <Card size="small" title="实时行情">
                <Descriptions column={1} size="small">
                  {(() => {
                    const displayData = comprehensiveData?.realtime || realtimeData;
                    return (
                      <>
                        <Descriptions.Item label="名称">{displayData?.name || displayName}</Descriptions.Item>
                        <Descriptions.Item label="现价">{formatNumber(displayData?.current_price)}</Descriptions.Item>
                        <Descriptions.Item label="涨跌幅">{formatNumber(displayData?.change_percent)}%</Descriptions.Item>
                        <Descriptions.Item label="昨收">{formatNumber(displayData?.yesterday_close)}</Descriptions.Item>
                        <Descriptions.Item label="开盘">{formatNumber(displayData?.open)}</Descriptions.Item>
                        <Descriptions.Item label="最高">{formatNumber(displayData?.high)}</Descriptions.Item>
                        <Descriptions.Item label="最低">{formatNumber(displayData?.low)}</Descriptions.Item>
                        <Descriptions.Item label="成交量">
                          {displayData?.volume ? `${formatNumber(displayData.volume / 10000, 0)}万手` : '--'}
                        </Descriptions.Item>
                        <Descriptions.Item label="成交额">
                          {displayData?.amount ? `${formatNumber(displayData.amount / 100000000, 2)}亿` : '--'}
                        </Descriptions.Item>
                        <Descriptions.Item label="换手率">
                          {displayData?.turnover_rate != null ? `${formatNumber(displayData.turnover_rate, 2)}%` : '--'}
                        </Descriptions.Item>
                      </>
                    );
                  })()}
                </Descriptions>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card size="small" title="资金与基本面">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="主力净流入">
                    {comprehensiveData?.money_flow?.main_net_inflow != null ? `${formatNumber(comprehensiveData.money_flow.main_net_inflow, 2)}万` : '--'}
                  </Descriptions.Item>
                  <Descriptions.Item label="超大单净流入">
                    {comprehensiveData?.money_flow?.super_large_net_inflow != null ? `${formatNumber(comprehensiveData.money_flow.super_large_net_inflow, 2)}万` : '--'}
                  </Descriptions.Item>
                  <Descriptions.Item label="PE">{formatNumber(comprehensiveData?.fundamental?.pe)}</Descriptions.Item>
                  <Descriptions.Item label="PB">{formatNumber(comprehensiveData?.fundamental?.pb)}</Descriptions.Item>
                  <Descriptions.Item label="PS">{formatNumber(comprehensiveData?.fundamental?.ps)}</Descriptions.Item>
                  <Descriptions.Item label="ROE">{formatNumber(comprehensiveData?.fundamental?.roe)}%</Descriptions.Item>
                  <Descriptions.Item label="EPS">{formatNumber(comprehensiveData?.fundamental?.eps)}</Descriptions.Item>
                  <Descriptions.Item label="BPS">{formatNumber(comprehensiveData?.fundamental?.bps)}</Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card size="small" title="行业对比">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="行业">
                    {comprehensiveData?.industry_comparison?.industry_name || '--'}
                  </Descriptions.Item>
                  <Descriptions.Item label="行业排名">
                    {comprehensiveData?.industry_comparison?.rank != null ? `${comprehensiveData.industry_comparison.rank}` : '--'}
                  </Descriptions.Item>
                  <Descriptions.Item label="行业平均涨跌">
                    {formatNumber(comprehensiveData?.industry_comparison?.avg_change_percent)}%
                  </Descriptions.Item>
                  <Descriptions.Item label="行业总数">
                    {comprehensiveData?.industry_comparison?.total != null ? `${comprehensiveData.industry_comparison.total}` : '--'}
                  </Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card size="small" title="舆情摘要（近7天）">
                <Descriptions column={1} size="small">
                  <Descriptions.Item label="新闻数量">{sentimentData?.news?.count ?? '--'}</Descriptions.Item>
                  <Descriptions.Item label="帖子数量">{sentimentData?.posts?.total_count ?? '--'}</Descriptions.Item>
                  <Descriptions.Item label="最新帖子">{sentimentData?.posts?.latest_count ?? '--'}</Descriptions.Item>
                  <Descriptions.Item label="热门帖子">{sentimentData?.posts?.hot_count ?? '--'}</Descriptions.Item>
                </Descriptions>
              </Card>
            </Col>
          </Row>
        )}
      </Card>

      {/* 最终报告 */}
      <Card
        title="研究报告（Markdown）"
        extra={
          <Button
            type="primary"
            icon={<ExportOutlined />}
            onClick={handleExport}
            disabled={!reportMd}
          >
            导出Markdown
          </Button>
        }
      >
        {status !== 'completed' ? (
          <Text type="secondary">报告生成中...</Text>
        ) : reportHtml ? (
          <div
            className="markdown-body"
            style={{ padding: 16, border: '1px solid #f0f0f0', borderRadius: 8 }}
            dangerouslySetInnerHTML={{ __html: reportHtml }}
          />
        ) : (
          <Text type="secondary">暂无报告</Text>
        )}
      </Card>
    </Space>
  );
}
