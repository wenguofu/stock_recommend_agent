import { useState } from 'react';
import { Card, InputNumber, Input, Button, Space, Descriptions, Tag, Progress, Spin, Typography, Alert, Row, Col } from 'antd';
import { CalculatorOutlined, RiseOutlined, FallOutlined } from '@ant-design/icons';

const { Title, Text, Paragraph } = Typography;
const API = (import.meta as any).env?.VITE_API_BASE_URL || 'http://127.0.0.1:35000';

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
}

const scoreColor = (s: number) => s >= 65 ? '#52c41a' : s >= 50 ? '#faad14' : s >= 35 ? '#fa8c16' : '#ff4d4f';

export default function ValuationPanel({ stockCode }: { stockCode?: string }) {
  const [code, setCode] = useState(stockCode || '');
  const [growth6m, setGrowth6m] = useState<number | null>(null);
  const [growth1y, setGrowth1y] = useState<number | null>(null);
  const [sectorName, setSectorName] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ValuationData | null>(null);
  const [error, setError] = useState('');

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
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>股票代码</Text>
            <Input value={code} onChange={e => setCode(e.target.value)} placeholder="002916" maxLength={6} />
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              半年行业利润增速(%)
            </Text>
            <InputNumber
              value={growth6m}
              onChange={v => setGrowth6m(v)}
              placeholder="如 100 = 翻倍"
              style={{ width: '100%' }}
              min={-100}
              max={1000}
            />
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>
              一年行业利润增速(%)
            </Text>
            <InputNumber
              value={growth1y}
              onChange={v => setGrowth1y(v)}
              placeholder="如 150"
              style={{ width: '100%' }}
              min={-100}
              max={1000}
            />
          </Col>
          <Col span={6}>
            <Text type="secondary" style={{ fontSize: 12, display: 'block', marginBottom: 4 }}>板块名称</Text>
            <Input value={sectorName} onChange={e => setSectorName(e.target.value)} placeholder="如 PCB" />
          </Col>
        </Row>

        <Button type="primary" onClick={handleAnalyze} loading={loading} icon={<CalculatorOutlined />} block>
          开始估值分析
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
                <Tag color={scoreColor(result.composite_score)} style={{ marginTop: 4, fontSize: 13 }}>
                  {result.rating}
                </Tag>
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
          </Paragraph>
        </div>
      )}
    </Card>
  );
}
