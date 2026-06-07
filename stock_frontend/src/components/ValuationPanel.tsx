import { useState, useEffect, useRef } from 'react';
import { Card, InputNumber, Input, Button, Space, Descriptions, Tag, Progress, Spin, Typography, Alert, Row, Col, Statistic, Divider } from 'antd';
import { CalculatorOutlined, RiseOutlined, FallOutlined, ThunderboltOutlined, EditOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const API = (import.meta as any).env?.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

interface ForecastPreview {
  has_data: boolean;
  source: 'institutional' | 'none';
  net_profit_2025a: number;
  net_profit_2026e: number;
  net_profit_2027e: number;
  eps_2026e: number;
  eps_2027e: number;
  analyst_count: number;
  rating_label: string;
  updated_at: string;
  growth_6m_implied: number;
  growth_1y_implied: number;
  message?: string;
}

interface ForecastInResult {
  source: string;
  has_data: boolean;
  net_profit_2025a: number;
  net_profit_2026e: number;
  net_profit_2027e: number;
  eps_2026e: number;
  eps_2027e: number;
  analyst_count: number;
  rating_label: string;
  updated_at: string;
  growth_6m_implied: number;
  growth_1y_implied: number;
  growth_2y_implied: number;
}

interface ValuationData {
  code: string;
  name: string;
  current_price: number;
  current_pe: number;
  eps_ttm: number;
  peg_ratio: number;
  peg_verdict: string;
  forward_pe_6m: number;
  forward_pe_1y: number;
  forward_pe_2y: number;
  fair_value_current: number;
  fair_value_growth: number;
  margin_of_safety: number;
  dcf_value: number;
  dcf_upside: number;
  composite_score: number;
  rating: string;
  summary: string;
  detail: Record<string, any>;
  forecast?: ForecastInResult;
}

const scoreColor = (s: number) => s >= 65 ? '#52c41a' : s >= 50 ? '#faad14' : s >= 35 ? '#fa8c16' : '#ff4d4f';

export default function ValuationPanel({ stockCode }: { stockCode?: string }) {
  const [code, setCode] = useState(stockCode || '');
  const [growth6m, setGrowth6m] = useState<number | null>(null);
  const [growth1y, setGrowth1y] = useState<number | null>(null);
  const [sectorName, setSectorName] = useState('');
  const [loading, setLoading] = useState(false);
  const [forecastPreview, setForecastPreview] = useState<ForecastPreview | null>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [forceManual, setForceManual] = useState(false);  // 用户强制手动模式
  const [result, setResult] = useState<ValuationData | null>(null);
  const [error, setError] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── 监听 code 变化, 自动查询机构预测 ──
  useEffect(() => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current);
    }
    if (!code || code.length !== 6) {
      setForecastPreview(null);
      return;
    }
    debounceRef.current = setTimeout(async () => {
      setForecastLoading(true);
      try {
        const res = await fetch(`${API}/api/valuation/forecast/${code}`);
        const data = await res.json();
        if (data.success) {
          setForecastPreview(data.data);
          // 如果有机构预测, 自动填入增速 (但允许用户覆盖)
          if (data.data.has_data) {
            setGrowth6m(data.data.growth_6m_implied || null);
            setGrowth1y(data.data.growth_1y_implied || null);
            setForceManual(false);
          }
        }
      } catch (e) {
        // 静默失败, 不影响主流程
        setForecastPreview(null);
      } finally {
        setForecastLoading(false);
      }
    }, 400);
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [code]);

  // 同步外部 stockCode prop
  useEffect(() => {
    if (stockCode && stockCode !== code) {
      setCode(stockCode);
    }
  }, [stockCode]);

  const useForecast = forecastPreview?.has_data && !forceManual;
  const hasForecast = !!forecastPreview?.has_data;

  const handleAnalyze = async () => {
    if (!code.trim()) {
      setError('请输入股票代码');
      return;
    }
    setLoading(true);
    setError('');
    try {
      const res = await fetch(`${API}/api/valuation/quick`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          code: code.trim(),
          industry_growth_6m: growth6m || 0,
          industry_growth_1y: growth1y || 0,
          sector_name: sectorName,
        }),
      });
      const data = await res.json();
      if (data.error) {
        setError(data.error);
        setResult(null);
      } else {
        setResult(data.data);
      }
    } catch (e: any) {
      setError(e.message || '请求失败');
      setResult(null);
    }
    setLoading(false);
  };

  return (
    <Card
      title={<span><CalculatorOutlined /> 定量估值分析</span>}
      size="small"
      style={{ marginBottom: 16 }}
    >
      {/* 输入区 */}
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <Row gutter={12}>
          <Col span={8}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              股票代码
              {forecastLoading && <Spin size="small" style={{ marginLeft: 8 }} />}
              {useForecast && <Tag color="green" icon={<ThunderboltOutlined />} style={{ marginLeft: 8 }}>机构预测</Tag>}
              {hasForecast && forceManual && <Tag color="orange" style={{ marginLeft: 8 }}>手动覆盖</Tag>}
            </Text>
            <Input
              value={code}
              onChange={e => {
                const v = e.target.value.replace(/\D/g, '').slice(0, 6);
                setCode(v);
              }}
              placeholder="002916"
              maxLength={6}
            />
          </Col>
          <Col span={4}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              半年行业利润增速(%)
              {useForecast && growth6m != null && (
                <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>自动</Tag>
              )}
            </Text>
            <InputNumber
              value={useForecast ? growth6m : null}
              onChange={v => {
                setGrowth6m(v);
                if (hasForecast && v !== null) setForceManual(true);
              }}
              disabled={useForecast}
              placeholder={useForecast ? "已用机构预测" : "如 100 = 翻倍"}
              style={{ width: '100%' }}
              min={-100}
              max={1000}
            />
          </Col>
          <Col span={4}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              一年行业利润增速(%)
              {useForecast && growth1y != null && (
                <Tag color="blue" style={{ marginLeft: 4, fontSize: 10 }}>自动</Tag>
              )}
            </Text>
            <InputNumber
              value={useForecast ? growth1y : null}
              onChange={v => {
                setGrowth1y(v);
                if (hasForecast && v !== null) setForceManual(true);
              }}
              disabled={useForecast}
              placeholder={useForecast ? "已用机构预测" : "如 150"}
              style={{ width: '100%' }}
              min={-100}
              max={1000}
            />
          </Col>
          <Col span={4}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>板块名称</Text>
            <Input value={sectorName} onChange={e => setSectorName(e.target.value)} placeholder="如 PCB" />
          </Col>
          <Col span={4}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>&nbsp;</Text>
            {hasForecast && !forceManual && (
              <Button block icon={<EditOutlined />} onClick={() => setForceManual(true)}>
                手动输入
              </Button>
            )}
            {hasForecast && forceManual && (
              <Button block type="dashed" icon={<ThunderboltOutlined />} onClick={() => {
                setForceManual(false);
                if (forecastPreview) {
                  setGrowth6m(forecastPreview.growth_6m_implied || null);
                  setGrowth1y(forecastPreview.growth_1y_implied || null);
                }
              }}>
                用机构预测
              </Button>
            )}
            {!hasForecast && <div style={{ fontSize: 11, color: '#999' }}>暂无机构预测, 需手动输入</div>}
          </Col>
        </Row>

        {/* 机构预测预览卡片 */}
        {hasForecast && forecastPreview && (
          <Alert
            type="success"
            showIcon
            icon={<ThunderboltOutlined />}
            message={
              <Space size="small" wrap>
                <Text strong>检测到机构预测数据</Text>
                {forecastPreview.analyst_count > 0 && (
                  <Tag color="cyan">{forecastPreview.analyst_count}家覆盖</Tag>
                )}
                {forecastPreview.rating_label && (
                  <Tag color="purple">评级: {forecastPreview.rating_label}</Tag>
                )}
                {forecastPreview.net_profit_2025a > 0 && (
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    2025A净利: <Text strong>{forecastPreview.net_profit_2025a.toFixed(2)}亿</Text>
                    {' → '}
                    2026E: <Text strong style={{ color: '#52c41a' }}>{forecastPreview.net_profit_2026e.toFixed(2)}亿</Text>
                    {' '}
                    ({forecastPreview.growth_6m_implied >= 0 ? '+' : ''}{forecastPreview.growth_6m_implied.toFixed(1)}%)
                  </Text>
                )}
              </Space>
            }
            style={{ fontSize: 12 }}
          />
        )}

        <Button type="primary" onClick={handleAnalyze} loading={loading} icon={<CalculatorOutlined />} block>
          {useForecast ? '使用机构预测数据估值' : '开始估值分析'}
        </Button>

        {error && <Alert type="error" message={error} showIcon />}
      </Space>

      {/* 结果区 */}
      {loading && <div style={{ textAlign: 'center', padding: 24 }}><Spin /></div>}

      {result && (
        <div style={{ marginTop: 16 }}>
          {/* 综合评分 */}
          <Card size="small" style={{ marginBottom: 12, background: '#fafafa' }}>
            <Row align="middle" gutter={16}>
              <Col>
                <Progress
                  type="circle"
                  percent={result.composite_score}
                  size={80}
                  strokeColor={scoreColor(result.composite_score)}
                  format={(p) => <span style={{ fontSize: 18, fontWeight: 'bold' }}>{p}</span>}
                />
              </Col>
              <Col flex={1}>
                <Title level={4} style={{ margin: 0 }}>{result.name || result.code}</Title>
                <Text style={{ fontSize: 16 }}>
                  当前价格 <Text strong>¥{result.current_price?.toFixed(2)}</Text>
                  {' '}| PE <Text strong>{result.current_pe?.toFixed(1)}</Text>
                </Text>
                <br />
                <Space size="small" style={{ marginTop: 4 }}>
                  <Tag color={scoreColor(result.composite_score)} style={{ fontSize: 13 }}>
                    {result.rating}
                  </Tag>
                  {result.forecast?.has_data && (
                    <Tag color="green" icon={<ThunderboltOutlined />}>
                      已用机构预测
                    </Tag>
                  )}
                </Space>
              </Col>
            </Row>
          </Card>

          {/* 核心指标 */}
          <Descriptions column={2} size="small" bordered>
            <Descriptions.Item label="PEG比率">
              <Text strong style={{ color: result.peg_ratio < 1 ? '#52c41a' : result.peg_ratio < 2 ? '#faad14' : '#ff4d4f' }}>
                {result.peg_ratio?.toFixed(2)}
              </Text>
              <br /><Text type="secondary" style={{ fontSize: 11 }}>{result.peg_verdict}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="安全边际">
              <Text strong style={{ color: result.margin_of_safety >= 0 ? '#52c41a' : '#ff4d4f' }}>
                {result.margin_of_safety >= 0 ? '+' : ''}{result.margin_of_safety?.toFixed(1)}%
              </Text>
            </Descriptions.Item>
            <Descriptions.Item label="Forward PE (6m)">
              {result.forward_pe_6m > 0 ? (
                <span>{result.forward_pe_6m?.toFixed(1)} <RiseOutlined style={{ color: result.forward_pe_6m < result.current_pe ? '#52c41a' : '#ff4d4f' }} /></span>
              ) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="Forward PE (1y)">
              {result.forward_pe_1y > 0 ? (
                <span>{result.forward_pe_1y?.toFixed(1)} <RiseOutlined style={{ color: result.forward_pe_1y < result.current_pe ? '#52c41a' : '#ff4d4f' }} /></span>
              ) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="公允价值(基准)">
              ¥{result.fair_value_current?.toFixed(2)}
            </Descriptions.Item>
            <Descriptions.Item label="公允价值(成长调整)">
              <Text strong>¥{result.fair_value_growth?.toFixed(2)}</Text>
            </Descriptions.Item>
            <Descriptions.Item label="DCF估值">
              ¥{result.dcf_value?.toFixed(2)}
            </Descriptions.Item>
            <Descriptions.Item label="DCF上行空间">
              <Text style={{ color: (result.dcf_upside || 0) >= 0 ? '#52c41a' : '#ff4d4f' }}>
                {(result.dcf_upside || 0) >= 0 ? '+' : ''}{result.dcf_upside?.toFixed(1)}%
              </Text>
            </Descriptions.Item>
          </Descriptions>

          {/* 机构预测明细 (Sprint 6 优化) */}
          {result.forecast?.has_data && (
            <>
              <Divider style={{ margin: '12px 0' }} />
              <Card size="small" title={<span><ThunderboltOutlined /> 机构预测详情</span>} type="inner">
                <Row gutter={16}>
                  <Col span={6}>
                    <Statistic
                      title="2025A 净利润"
                      value={result.forecast.net_profit_2025a}
                      precision={2}
                      suffix="亿"
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="2026E 净利润"
                      value={result.forecast.net_profit_2026e}
                      precision={2}
                      suffix="亿"
                      valueStyle={{ fontSize: 14, color: '#52c41a' }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="2027E 净利润"
                      value={result.forecast.net_profit_2027e}
                      precision={2}
                      suffix="亿"
                      valueStyle={{ fontSize: 14, color: '#52c41a' }}
                    />
                  </Col>
                  <Col span={6}>
                    <Statistic
                      title="覆盖机构"
                      value={result.forecast.analyst_count}
                      suffix="家"
                      valueStyle={{ fontSize: 14 }}
                    />
                  </Col>
                </Row>
                <Row gutter={16} style={{ marginTop: 12 }}>
                  <Col span={8}>
                    <Text type="secondary" style={{ fontSize: 12 }}>隐含半年增速: </Text>
                    <Text strong style={{ color: result.forecast.growth_6m_implied >= 0 ? '#52c41a' : '#ff4d4f' }}>
                      {result.forecast.growth_6m_implied >= 0 ? '+' : ''}{result.forecast.growth_6m_implied?.toFixed(2)}%
                    </Text>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary" style={{ fontSize: 12 }}>隐含年化增速: </Text>
                    <Text strong style={{ color: result.forecast.growth_1y_implied >= 0 ? '#52c41a' : '#ff4d4f' }}>
                      {result.forecast.growth_1y_implied >= 0 ? '+' : ''}{result.forecast.growth_1y_implied?.toFixed(2)}%
                    </Text>
                  </Col>
                  <Col span={8}>
                    <Text type="secondary" style={{ fontSize: 12 }}>综合评级: </Text>
                    <Text strong>{result.forecast.rating_label || '—'}</Text>
                  </Col>
                </Row>
              </Card>
            </>
          )}

          {/* 一句话总结 */}
          <Alert
            type={result.composite_score >= 50 ? 'success' : 'warning'}
            message={result.summary}
            style={{ marginTop: 12 }}
          />

          {/* 估值逻辑说明 */}
          <Paragraph type="secondary" style={{ marginTop: 12, fontSize: 12 }}>
            <Text strong>计算逻辑：</Text>
            Forward PE = 当前PE / (1 + 行业利润增速%)；
            PEG = PE / 增速%（{'>'}1低估，1-2合理，{'>'}2高估）；
            成长调整公允价值 = EPS × 合理PE基准 × (1 + 增速调整)；
            DCF简化版 = 3年自由现金流(EPS×0.7)折现(WACC=10%) + 永续终值。
            {result.forecast?.has_data && (
              <>
                <br />
                <Text strong style={{ color: '#52c41a' }}>本次估值已自动采用机构预测净利润数据 ({result.forecast.analyst_count}家覆盖, 评级 {result.forecast.rating_label || '—'})</Text>
              </>
            )}
          </Paragraph>
        </div>
      )}
    </Card>
  );
}
