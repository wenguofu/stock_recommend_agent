/**
 * Sprint4: ML 性能监控页面
 *
 * 功能:
 *  - 显示 PSI/KS/IC/ECE/Brier 实时指标
 *  - 30 天趋势图
 *  - 当前模型版本 + A/B 影子版本对比
 *  - 告警提示
 */
import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Card, Row, Col, Statistic, Alert, Tag, Space, Select, Spin, Table, Button, App, Tabs, Typography
} from 'antd';
import { stockAPI } from '../services/api';
import { stockUpColor, stockDownColor, semanticSuccess, semanticError, semanticWarning } from '../constants/tokens';

const { Text } = Typography;

export default function MLMonitoring() {
  const { message } = App.useApp();
  const [modelId, setModelId] = useState('short_term');
  const [days, setDays] = useState(30);

  // 1. 当日指标
  const { data: daily, isLoading: dailyLoading, refetch: refetchDaily } = useQuery({
    queryKey: ['ml-monitor-daily', modelId, days],
    queryFn: () => stockAPI.getMLMonitorDaily(modelId, days),
    refetchInterval: 60_000,
  });

  // 2. 趋势
  const { data: trend } = useQuery({
    queryKey: ['ml-monitor-trend', modelId, days],
    queryFn: () => stockAPI.getMLMonitorTrend(modelId, days),
  });

  // 3. A/B 影子对比
  const { data: shadow } = useQuery({
    queryKey: ['ml-shadow-compare', modelId],
    queryFn: () => stockAPI.getShadowCompare(modelId, 30),
  });

  // 4. 版本列表
  const { data: versions, refetch: refetchVersions } = useQuery({
    queryKey: ['ml-registry-list', modelId],
    queryFn: () => stockAPI.listModelVersions(modelId),
  });

  // 5. 校准
  const { data: calib } = useQuery({
    queryKey: ['ml-calibration', modelId],
    queryFn: () => stockAPI.getCalibration(modelId),
  });

  const handlePromote = async (versionId: number) => {
    try {
      const r = await stockAPI.promoteModelVersion(versionId);
      if (r.success) {
        message.success(`已升为 active: v${versionId}`);
        refetchVersions();
      } else {
        message.error('升级失败');
      }
    } catch (e) {
      message.error('升级失败: ' + (e as Error).message);
    }
  };

  const handleShadow = async (versionId: number) => {
    try {
      const r = await stockAPI.setShadowVersion(versionId);
      if (r.success) {
        message.success(`已设为 shadow: v${versionId}`);
        refetchVersions();
      } else {
        message.error('设置失败');
      }
    } catch (e) {
      message.error('设置失败: ' + (e as Error).message);
    }
  };

  const hasMetrics = (m: any) => m && (
    m.psi != null || m.ks != null || m.ic != null ||
    m.ece != null || m.brier != null
  );
  const fmt = (v: any, d: number) => v != null ? v.toFixed(d) : 'N/A';
  const metricCards = (m: any) => hasMetrics(m) ? [
    { name: 'PSI (漂移)', value: m.psi, warn: m.psi > 0.10, danger: m.psi > 0.25, fmt: (v: any) => fmt(v, 3) },
    { name: 'KS (区分度)', value: m.ks, warn: m.ks < 0.05, danger: m.ks < 0.02, fmt: (v: any) => fmt(v, 3) },
    { name: 'IC (预测力)', value: m.ic, warn: Math.abs(m.ic) < 0.01, danger: Math.abs(m.ic) < 0.005, fmt: (v: any) => fmt(v, 4) },
    { name: 'ECE (校准)', value: m.ece, warn: m.ece > 0.05, danger: m.ece > 0.10, fmt: (v: any) => fmt(v, 3) },
    { name: 'Brier (概率误差)', value: m.brier, warn: m.brier > 0.30, danger: m.brier > 0.40, fmt: (v: any) => fmt(v, 3) },
  ] : [];

  return (
    <div style={{ padding: 16 }}>
      <h2>ML 性能监控</h2>
      <Space style={{ marginBottom: 16 }}>
        <span>模型:</span>
        <Select value={modelId} onChange={setModelId} style={{ width: 150 }}
          options={[
            { value: 'short_term', label: '短线 (BiLSTM+Attn)' },
            { value: 'mid_term', label: '中线 (Transformer)' },
            { value: 'regime', label: '行情体制' },
          ]} />
        <span>窗口:</span>
        <Select value={days} onChange={setDays} style={{ width: 100 }}
          options={[
            { value: 7, label: '7 天' },
            { value: 30, label: '30 天' },
            { value: 60, label: '60 天' },
          ]} />
        <Button onClick={() => refetchDaily()}>刷新</Button>
      </Space>

      <Tabs defaultActiveKey="metrics" items={[
        {
          key: 'metrics',
          label: '📊 实时指标',
          children: (
            <Spin spinning={dailyLoading}>
              {daily?.alerts?.length > 0 && (
                <Alert
                  type="warning"
                  showIcon
                  message={`检测到 ${daily.alerts.length} 项指标告警`}
                  description={
                    <ul>
                      {daily.alerts.map((a: any, i: number) => (
                        <li key={i}>{a.msg}</li>
                      ))}
                    </ul>
                  }
                  style={{ marginBottom: 16 }}
                />
              )}
              <Row gutter={16}>
                {hasMetrics(daily?.metrics) ? (
                  metricCards(daily?.metrics).map((card, i) => (
                    <Col key={i} span={4}>
                      <Card>
                        <Statistic
                          title={card.name}
                          value={card.fmt(card.value)}
                          valueStyle={{
                            color: card.danger ? semanticError :
                                   card.warn ? semanticWarning :
                                   semanticSuccess,
                          }}
                        />
                      </Card>
                    </Col>
                  ))
                ) : (
                  <Col span={24}>
                    <Text type="secondary">
                      暂无监控指标({daily?.status === 'insufficient_data'
                        ? `调用样本不足(当前 n=${daily?.n ?? 0},需 ≥ 10)`
                        : '请先调用模型再查看'})
                    </Text>
                  </Col>
                )}
              </Row>

              <Card title="30 天指标趋势" style={{ marginTop: 16 }}>
                {trend?.trend && trend.trend.length > 0 ? (
                  <div>
                    <Text type="secondary">
                      数据点: {trend.n} | 模型: {modelId}
                    </Text>
                    <Table
                      size="small"
                      style={{ marginTop: 12 }}
                      dataSource={trend.trend}
                      rowKey="date"
                      pagination={false}
                      columns={[
                        { title: '日期', dataIndex: 'date' },
                        { title: '样本数', dataIndex: 'n' },
                        { title: 'PSI', dataIndex: 'psi', render: (v: number) => v?.toFixed(3) },
                        { title: 'KS', dataIndex: 'ks', render: (v: number) => v?.toFixed(3) },
                        { title: 'IC', dataIndex: 'ic', render: (v: number) => v?.toFixed(4) },
                        { title: 'ECE', dataIndex: 'ece', render: (v: number) => v?.toFixed(3) },
                        { title: 'Brier', dataIndex: 'brier', render: (v: number) => v?.toFixed(3) },
                        { title: '告警', dataIndex: 'alerts', render: (a: any[]) => a?.length || 0 },
                      ]}
                    />
                  </div>
                ) : (
                  <Text type="secondary">暂无趋势数据(可能调用样本不足 10 条)</Text>
                )}
              </Card>
            </Spin>
          ),
        },
        {
          key: 'shadow',
          label: '🔀 A/B 影子对比',
          children: (
            <Card>
              {shadow?.n > 0 ? (
                <Row gutter={16}>
                  <Col span={6}>
                    <Statistic title="样本数" value={shadow.n} />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="Active 准确率"
                      value={((shadow.active_acc || 0) * 100).toFixed(1) + '%'}
                      valueStyle={{ color: stockUpColor }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="Shadow 准确率"
                      value={((shadow.shadow_acc || 0) * 100).toFixed(1) + '%'}
                      valueStyle={{ color: stockDownColor }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="方向一致率"
                      value={((shadow.agree_rate || 0) * 100).toFixed(1) + '%'}
                    />
                  </Col>
                </Row>
              ) : (
                <Text type="secondary">影子调用样本不足,需积累流量(默认 5% 流量走 shadow)</Text>
              )}
            </Card>
          ),
        },
        {
          key: 'versions',
          label: '📦 模型版本',
          children: (
            <Card>
              {calib && (
                <Alert
                  type="info"
                  message={`当前 ${modelId} 校准温度: T = ${calib.temperature?.toFixed(3)}`}
                  style={{ marginBottom: 12 }}
                />
              )}
              <Table
                dataSource={versions?.versions || []}
                rowKey="id"
                size="small"
                columns={[
                  { title: 'ID', dataIndex: 'id', width: 60 },
                  { title: '版本', dataIndex: 'version' },
                  { title: 'SHA256', dataIndex: 'sha256', render: (s: string) => <code>{s?.slice(0, 8)}</code> },
                  { title: 'Acc', dataIndex: 'metrics', render: (m: any) => m?.acc?.toFixed(3) },
                  { title: '框架', dataIndex: 'metrics', render: (m: any) => m?.framework },
                  { title: '数据集', dataIndex: 'dataset_hash', render: (h: string) => <code>{h?.slice(0, 8)}</code> },
                  { title: '状态', render: (_: any, r: any) => (
                    <Space>
                      {r.is_active && <Tag color="green">Active</Tag>}
                      {r.is_shadow && <Tag color="orange">Shadow</Tag>}
                      {!r.is_active && !r.is_shadow && <Tag>Idle</Tag>}
                    </Space>
                  )},
                  { title: '操作', render: (_: any, r: any) => (
                    <Space>
                      <Button size="small" onClick={() => handlePromote(r.id)} disabled={r.is_active}>
                        Promote
                      </Button>
                      <Button size="small" onClick={() => handleShadow(r.id)} disabled={r.is_shadow}>
                        Set Shadow
                      </Button>
                    </Space>
                  )},
                ]}
              />
            </Card>
          ),
        },
      ]} />
    </div>
  );
}
