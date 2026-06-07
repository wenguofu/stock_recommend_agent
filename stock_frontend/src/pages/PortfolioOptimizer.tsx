/**
 * Sprint5: 组合优化 UI
 */
import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import {
  Card, Form, Input, InputNumber, Select, Button, Space, Row, Col,
  Table, Tag, Alert, Typography, Divider, Statistic,
} from 'antd';
import { stockAPI } from '../services/api';
import { stockUpColor, stockDownColor, semanticSuccess } from '../constants/tokens';

const { Text } = Typography;

export default function PortfolioOptimizer() {
  const [codes, setCodes] = useState('000001,600519,000858,300750');
  const [days, setDays] = useState(120);
  const [target, setTarget] = useState<number | null>(null);
  const [riskProfile, setRiskProfile] = useState<'conservative' | 'moderate' | 'aggressive'>('moderate');
  const [totalCapital, setTotalCapital] = useState(100000);

  // 相关性
  const corrMut = useMutation({
    mutationFn: () => stockAPI.portfolioCorrelation(codes.split(',').filter(Boolean), days),
  });

  // Markowitz
  const mwMut = useMutation({
    mutationFn: () => stockAPI.portfolioMarkowitz(
      codes.split(',').filter(Boolean), days, target ?? undefined,
    ),
  });

  // 有效前沿
  const frontierMut = useMutation({
    mutationFn: () => stockAPI.portfolioFrontier(codes.split(',').filter(Boolean), days),
  });

  // 风险平价
  const rpMut = useMutation({
    mutationFn: () => stockAPI.portfolioRiskParity(codes.split(',').filter(Boolean), days),
  });

  // 组合推荐
  const recMut = useMutation({
    mutationFn: () => stockAPI.portfolioRecommend({
      holdings: [],
      candidates: codes.split(',').filter(Boolean),
      total_capital: totalCapital,
      days,
      risk_profile: riskProfile,
      max_stocks: 5,
    }),
  });

  return (
    <div style={{ padding: 16 }}>
      <h2>组合优化</h2>
      <Card>
        <Form layout="inline">
          <Form.Item label="股票池(逗号分隔)">
            <Input
              value={codes}
              onChange={e => setCodes(e.target.value)}
              style={{ width: 280 }}
              placeholder="000001,600519,..."
            />
          </Form.Item>
          <Form.Item label="回看天数">
            <InputNumber value={days} onChange={v => setDays(v || 120)} min={30} max={720} />
          </Form.Item>
          <Form.Item label="目标收益(可选)">
            <InputNumber
              value={target}
              onChange={v => setTarget(v ?? null)}
              step={0.05}
              placeholder="如 0.15"
            />
          </Form.Item>
          <Form.Item label="风险偏好">
            <Select
              value={riskProfile}
              onChange={setRiskProfile}
              style={{ width: 120 }}
              options={[
                { value: 'conservative', label: '保守' },
                { value: 'moderate', label: '稳健' },
                { value: 'aggressive', label: '激进' },
              ]}
            />
          </Form.Item>
        </Form>
        <Divider />
        <Space>
          <Button loading={corrMut.isPending} onClick={() => corrMut.mutate()}>
            1. 相关性矩阵
          </Button>
          <Button loading={mwMut.isPending} type="primary" onClick={() => mwMut.mutate()}>
            2. Markowitz 优化
          </Button>
          <Button loading={frontierMut.isPending} onClick={() => frontierMut.mutate()}>
            3. 有效前沿
          </Button>
          <Button loading={rpMut.isPending} onClick={() => rpMut.mutate()}>
            4. 风险平价
          </Button>
        </Space>
        <Divider />
        <Form.Item label="推荐总资金(¥)">
          <InputNumber
            value={totalCapital}
            onChange={v => setTotalCapital(v || 100000)}
            step={10000}
            min={10000}
          />
        </Form.Item>
        <Button
          loading={recMut.isPending}
          type="primary"
          ghost
          onClick={() => recMut.mutate()}
        >
          5. 组合推荐(凯利+止损)
        </Button>
      </Card>

      {/* 1. 相关性 */}
      {corrMut.data?.success && (
        <Card title="相关性矩阵" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic
                title="平均相关性"
                value={corrMut.data.avg_correlation?.toFixed(4)}
                valueStyle={{ color: semanticSuccess }}
              />
            </Col>
            <Col span={6}>
              <Tag color={corrMut.data.avg_correlation > 0.7 ? 'red' : 'green'}>
                {corrMut.data.correlation_level}
              </Tag>
            </Col>
            <Col span={6}>
              <Statistic title="股票数" value={corrMut.data.n_stocks} />
            </Col>
            <Col span={6}>
              <Statistic
                title="高相关对(>0.7)"
                value={corrMut.data.high_corr_pairs?.length || 0}
              />
            </Col>
          </Row>
          {corrMut.data.high_corr_pairs?.length > 0 && (
            <Alert
              type="warning"
              showIcon
              style={{ marginTop: 12 }}
              message="存在高相关股票对, 分散化效果可能受限"
              description={
                <ul>
                  {corrMut.data.high_corr_pairs.map((p: any, i: number) => (
                    <li key={i}>{p.pair.join(' ↔ ')}: {p.correlation}</li>
                  ))}
                </ul>
              }
            />
          )}
        </Card>
      )}

      {/* 2. Markowitz */}
      {mwMut.data?.success && (
        <Card title="Markowitz 优化结果" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic
                title="组合年化收益(%)"
                value={mwMut.data.portfolio_return_annual_pct}
                valueStyle={{ color: stockUpColor }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="年化波动率(%)"
                value={mwMut.data.portfolio_volatility_annual_pct}
                valueStyle={{ color: stockDownColor }}
              />
            </Col>
            <Col span={6}>
              <Statistic title="Sharpe" value={mwMut.data.sharpe_ratio?.toFixed(4)} />
            </Col>
            <Col span={6}>
              <Tag color="blue">{mwMut.data.type}</Tag>
            </Col>
          </Row>
          <Divider />
          <Table
            size="small"
            dataSource={mwMut.data.allocations}
            rowKey="code"
            pagination={false}
            columns={[
              { title: '代码', dataIndex: 'code' },
              {
                title: '权重(%)', dataIndex: 'weight_pct',
                render: (v: number) => <Tag color="green">{v}%</Tag>,
                sorter: (a: any, b: any) => a.weight_pct - b.weight_pct,
                defaultSortOrder: 'descend',
              },
            ]}
          />
        </Card>
      )}

      {/* 3. 有效前沿 */}
      {frontierMut.data?.success && (
        <Card title={`有效前沿 (${frontierMut.data.n_points} 个点)`} style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={8}>
              <Text>最小方差组合:</Text>
              <div>收益 {frontierMut.data.mvp?.return_annual_pct}%</div>
              <div>波动 {frontierMut.data.mvp?.volatility_annual_pct}%</div>
            </Col>
            <Col span={8}>
              <Text>最大夏普组合:</Text>
              <div>收益 {frontierMut.data.max_sharpe?.return_annual_pct}%</div>
              <div>波动 {frontierMut.data.max_sharpe?.volatility_annual_pct}%</div>
              <div>Sharpe {frontierMut.data.max_sharpe?.sharpe_ratio?.toFixed(3)}</div>
            </Col>
          </Row>
          <Divider />
          <Table
            size="small"
            dataSource={frontierMut.data.frontier}
            rowKey={(_r, i) => String(i ?? 0)}
            pagination={false}
            scroll={{ y: 240 }}
            columns={[
              { title: '收益(%)', dataIndex: 'return_annual_pct' },
              { title: '波动(%)', dataIndex: 'volatility_annual_pct' },
              {
                title: 'Sharpe', dataIndex: 'sharpe_ratio',
                render: (v: number) => v?.toFixed(4),
              },
              { title: '持仓', dataIndex: 'allocations', render: (a: any[]) => a?.map((x: any) => x.code).join(', ') },
            ]}
          />
        </Card>
      )}

      {/* 4. 风险平价 */}
      {rpMut.data?.success && (
        <Card title="风险平价" style={{ marginTop: 16 }}>
          <Table
            size="small"
            dataSource={rpMut.data.allocations}
            rowKey="code"
            pagination={false}
            columns={[
              { title: '代码', dataIndex: 'code' },
              { title: '权重(%)', dataIndex: 'weight_pct' },
              { title: '风险贡献(%)', dataIndex: 'risk_contribution_pct' },
            ]}
          />
          <div style={{ marginTop: 8 }}>
            <Text>组合波动: {rpMut.data.portfolio_volatility_annual_pct}% | </Text>
            <Text>风险平衡分: {rpMut.data.risk_balance_score}</Text>
          </div>
        </Card>
      )}

      {/* 5. 推荐 */}
      {recMut.data?.success && (
        <Card title="组合推荐(凯利+ATR止损)" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Statistic title="风险偏好" value={recMut.data.risk_profile} />
            </Col>
            <Col span={6}>
              <Statistic
                title="组合年化收益(%)"
                value={recMut.data.portfolio_return_annual_pct}
                valueStyle={{ color: stockUpColor }}
              />
            </Col>
            <Col span={6}>
              <Statistic
                title="组合波动率(%)"
                value={recMut.data.portfolio_volatility_annual_pct}
                valueStyle={{ color: stockDownColor }}
              />
            </Col>
            <Col span={6}>
              <Statistic title="现金比例(%)" value={recMut.data.cash_pct} />
            </Col>
          </Row>
          <Divider />
          <Table
            size="small"
            dataSource={recMut.data.recommendations}
            rowKey="code"
            pagination={false}
            columns={[
              { title: '代码', dataIndex: 'code' },
              { title: '权重(%)', dataIndex: 'weight_pct' },
              { title: '金额', dataIndex: 'amount' },
              { title: '股数', dataIndex: 'shares' },
              { title: '现价', dataIndex: 'current_price' },
              { title: '止损', dataIndex: 'stop_loss' },
              { title: 'Kelly(%)', dataIndex: 'kelly_pct' },
            ]}
          />
        </Card>
      )}
    </div>
  );
}
