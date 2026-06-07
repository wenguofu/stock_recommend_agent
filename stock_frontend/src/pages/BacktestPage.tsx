import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import { Link } from 'react-router-dom';
import {
  Card, Button, Select, DatePicker, InputNumber, Form, Table,
  Typography, Space, Tag, Row, Col, Spin, Input
} from 'antd';
import { LeftOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';

const { Title, Text } = Typography;

interface Preset {
  key: string; name: string; description: string; params: ParamDef[];
}
interface ParamDef {
  key: string; label: string; type: string; default: number; min: number; max: number;
}

function formatMoney(v: number): string {
  if (Math.abs(v) >= 1e8) return (v / 1e8).toFixed(2) + '亿';
  if (Math.abs(v) >= 1e4) return (v / 1e4).toFixed(2) + '万';
  return v.toFixed(2);
}

export default function BacktestPage() {
  const [code, setCode] = useState('000001');
  const [selectedStrategy, setSelectedStrategy] = useState('ma_cross');
  const [params, setParams] = useState<Record<string, number>>({ fast_period: 5, slow_period: 20 });
  const [startDate, setStartDate] = useState(() => {
    const d = new Date(); d.setFullYear(d.getFullYear() - 1);
    return d.toISOString().slice(0, 10);
  });
  const [endDate, setEndDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [capital, setCapital] = useState('100000');
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  const { data: presets = [] } = useQuery({
    queryKey: ['backtest-presets'],
    queryFn: () => stockAPI.getBacktestPresets(),
  });

  const handleStrategyChange = (key: string) => {
    setSelectedStrategy(key);
    const preset = presets.find((p: Preset) => p.key === key);
    if (preset) {
      const p: Record<string, number> = {};
      preset.params.forEach((def: ParamDef) => { p[def.key] = def.default; });
      setParams(p);
    }
    setResult(null);
    setError(null);
  };

  const handleParamChange = (key: string, val: number | null) => {
    if (val !== null) setParams(prev => ({ ...prev, [key]: val }));
  };

  const handleRun = async () => {
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const payload: any = { code, strategy: selectedStrategy, params };
      if (startDate) payload.start_date = startDate;
      if (endDate) payload.end_date = endDate;
      if (capital) payload.initial_capital = parseFloat(capital);
      const res = await stockAPI.runBacktest(payload);
      if (res.success === false) {
        setError(res.error || '回测失败');
      } else {
        setResult(res);
      }
    } catch (e: any) {
      setError(e.message || '回测请求失败');
    } finally {
      setRunning(false);
    }
  };

  const preset = presets.find((p: Preset) => p.key === selectedStrategy);

  // Table columns for trade records
  const tradeColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 100 },
    {
      title: '方向', dataIndex: 'type', key: 'type', width: 60,
      render: (t: string) => (
        <Tag color={t === 'buy' ? 'red' : 'green'}>
          {t === 'buy' ? '买入' : '卖出'}
        </Tag>
      ),
    },
    { title: '价格', dataIndex: 'price', key: 'price', width: 80, align: 'right' as const, render: (v: number) => v.toFixed(2) },
    { title: '数量', dataIndex: 'shares', key: 'shares', width: 80, align: 'right' as const },
    {
      title: '金额', key: 'amount', width: 100, align: 'right' as const,
      render: (_: any, r: any) => (r.type === 'buy' ? r.cost?.toFixed(2) : r.proceeds?.toFixed(2)),
    },
    {
      title: '手续费', dataIndex: 'commission', key: 'commission', width: 80, align: 'right' as const,
      render: (v: number) => v?.toFixed(2),
    },
    {
      title: '剩余现金', dataIndex: 'cash_after', key: 'cash_after', width: 100, align: 'right' as const,
      render: (v: number) => formatMoney(v),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Space align="center">
        <Link to="/strategies" style={{ color: 'inherit' }}>
          <Button type="text" icon={<LeftOutlined />} />
        </Link>
        <Title level={3} style={{ margin: 0 }}>策略回测</Title>
      </Space>

      {/* 参数表单 */}
      <Card>
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} md={12} lg={6}>
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>股票代码</Text>
            </div>
            <Input
              value={code}
              onChange={e => setCode(e.target.value)}
              placeholder="000001"
              style={{ fontFamily: 'monospace' }}
            />
          </Col>
          <Col xs={24} md={12} lg={6}>
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>开始日期</Text>
            </div>
            <DatePicker
              value={startDate ? dayjs(startDate) : null}
              onChange={(_, dateStr) => setStartDate(dateStr as string)}
              style={{ width: '100%' }}
              placeholder="选择开始日期"
            />
          </Col>
          <Col xs={24} md={12} lg={6}>
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>结束日期</Text>
            </div>
            <DatePicker
              value={endDate ? dayjs(endDate) : null}
              onChange={(_, dateStr) => setEndDate(dateStr as string)}
              style={{ width: '100%' }}
              placeholder="选择结束日期"
            />
          </Col>
          <Col xs={24} md={12} lg={6}>
            <div style={{ marginBottom: 4 }}>
              <Text type="secondary" style={{ fontSize: 12 }}>初始资金(元)</Text>
            </div>
            <InputNumber
              value={parseFloat(capital)}
              onChange={val => val !== null && setCapital(val.toString())}
              style={{ width: '100%' }}
              min={0}
              formatter={value => `${value}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',')}
              parser={value => value?.replace(/,/g, '') as any}
            />
          </Col>
        </Row>

        {/* 策略选择 */}
        <div style={{ marginBottom: 16 }}>
          <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>策略</Text>
          <Row gutter={[8, 8]}>
            {presets.map((p: Preset) => (
              <Col xs={24} sm={12} lg={6} key={p.key}>
                <Card
                  size="small"
                  hoverable
                  onClick={() => handleStrategyChange(p.key)}
                  style={{
                    cursor: 'pointer',
                    borderColor: selectedStrategy === p.key ? '#1677ff' : undefined,
                    backgroundColor: selectedStrategy === p.key ? '#e6f4ff' : undefined,
                  }}
                >
                  <Text strong style={{ display: 'block' }}>{p.name}</Text>
                  <Text type="secondary" style={{ fontSize: 12 }}>{p.description}</Text>
                </Card>
              </Col>
            ))}
          </Row>
        </div>

        {/* 策略参数 */}
        {preset && (
          <div style={{ marginBottom: 16 }}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 8 }}>策略参数</Text>
            <Space wrap>
              {preset.params.map((def: ParamDef) => (
                <div key={def.key}>
                  <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 2 }}>
                    {def.label} ({def.min}-{def.max})
                  </Text>
                  <InputNumber
                    value={params[def.key] ?? def.default}
                    onChange={val => handleParamChange(def.key, val)}
                    min={def.min}
                    max={def.max}
                    step={def.type === 'float' ? 0.1 : 1}
                    style={{ width: 96 }}
                  />
                </div>
              ))}
            </Space>
          </div>
        )}

        <Button
          type="primary"
          onClick={handleRun}
          loading={running}
          icon={running ? undefined : <span>🚀</span>}
        >
          {running ? '⏳ 回测运行中...' : '开始回测'}
        </Button>
        {error && <Text type="danger" style={{ display: 'block', marginTop: 8 }}>{error}</Text>}
      </Card>

      {/* 回测结果 */}
      {result && (
        <>
          {/* 核心指标 */}
          <Row gutter={[12, 12]}>
            {[
              { label: '总收益率', value: `${result.metrics.total_return}%`, color: result.metrics.total_return >= 0 ? '#cf1322' : '#389e0d' },
              { label: '年化收益', value: `${result.metrics.annual_return}%`, color: result.metrics.annual_return >= 0 ? '#cf1322' : '#389e0d' },
              { label: '最大回撤', value: `${result.metrics.max_drawdown}%`, color: '#389e0d' },
              { label: '夏普比率', value: result.metrics.sharpe_ratio, color: result.metrics.sharpe_ratio >= 1 ? '#cf1322' : undefined },
              { label: '胜率', value: `${result.metrics.win_rate}%`, color: result.metrics.win_rate >= 50 ? '#cf1322' : undefined },
              { label: '交易次数', value: result.metrics.total_trades },
              { label: '买入持有', value: `${result.metrics.buy_hold_return}%`, color: result.metrics.buy_hold_return >= 0 ? '#cf1322' : '#389e0d' },
            ].map((item, i) => (
              <Col xs={12} md={6} lg={Math.floor(24 / 7)} key={i}>
                <Card size="small">
                  <Text type="secondary" style={{ fontSize: 12 }}>{item.label}</Text>
                  <div>
                    <Text strong style={{ fontSize: 16, color: item.color }}>{item.value}</Text>
                  </div>
                </Card>
              </Col>
            ))}
          </Row>

          {/* 超额收益提示 */}
          <Card size="small" style={{ backgroundColor: '#e6f4ff', borderColor: '#91caff' }}>
            <Space size={4}>
              <Text strong>📊 策略 vs 买入持有：</Text>
              <Text style={{ color: result.metrics.excess_return >= 0 ? '#cf1322' : '#389e0d' }}>
                {result.metrics.excess_return >= 0 ? '+' : ''}{result.metrics.excess_return}%
              </Text>
              <Text type="secondary">
                · 回测区间 {result.period.start} ~ {result.period.end}（{result.period.trading_days}个交易日）
                · 初始资金 {formatMoney(result.initial_capital)} → 最终 {formatMoney(result.final_value)}
              </Text>
            </Space>
          </Card>

          {/* 交易记录 */}
          {result.trades.length > 0 && (
            <Card
              title={`📝 交易记录 (${result.trades.length}笔)`}
              styles={{ body: { padding: 0 } }}
            >
              <Table
                columns={tradeColumns}
                dataSource={result.trades.map((t: any, i: number) => ({ ...t, key: i }))}
                size="small"
                scroll={{ y: 400 }}
                pagination={false}
              />
            </Card>
          )}

          {/* 净值曲线 */}
          {result.equity_curve?.length > 0 && (
            <Card title="📈 净值曲线">
              <div style={{ overflowX: 'auto' }}>
                <svg viewBox="0 0 800 240" style={{ width: '100%', height: 240 }} preserveAspectRatio="xMidYMid meet">
                  <defs>
                    <linearGradient id="grid-grad" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="currentColor" stopOpacity="0.06" />
                      <stop offset="100%" stopColor="currentColor" stopOpacity="0.02" />
                    </linearGradient>
                  </defs>
                  {(() => {
                    const curve = result.equity_curve;
                    const values = curve.map((e: any) => e.total_value);
                    const minV = Math.min(...values);
                    const maxV = Math.max(...values);
                    const range = maxV - minV || 1;
                    const w = 800, h = 200;
                    const pad = 20;
                    const plotW = w - pad * 2;
                    const plotH = h - pad * 2;
                    const steps = curve.length;

                    const gridLines = [];
                    for (let i = 0; i <= 4; i++) {
                      const y = pad + plotH - (plotH * i / 4);
                      const val = minV + range * i / 4;
                      gridLines.push(<line key={`g${i}`} x1={pad} y1={y} x2={w - pad} y2={y} stroke="#e5e7eb" strokeWidth="0.5" />);
                      gridLines.push(<text key={`gt${i}`} x={pad - 4} y={y + 3} textAnchor="end" style={{ fontSize: 10, fill: '#9ca3af' }}>{formatMoney(val)}</text>);
                    }

                    const points = curve.map((e: any, i: number) => {
                      const x = pad + (steps > 1 ? (i / (steps - 1)) * plotW : plotW / 2);
                      const y = pad + plotH - ((e.total_value - minV) / range) * plotH;
                      return `${x},${y}`;
                    });

                    return (
                      <>
                        {gridLines}
                        <polyline fill="none" stroke="#3b82f6" strokeWidth="2" points={points.join(' ')} />
                        <circle cx={parseFloat(points[0].split(',')[0])} cy={parseFloat(points[0].split(',')[1])} r="3" fill="#3b82f6" />
                        <circle cx={parseFloat(points[points.length - 1].split(',')[0])} cy={parseFloat(points[points.length - 1].split(',')[1])} r="3" fill="#ef4444" />
                      </>
                    );
                  })()}
                </svg>
              </div>
            </Card>
          )}
        </>
      )}
    </Space>
  );
}
