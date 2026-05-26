import { Card, Select, InputNumber, Button, Tag, Table, Space, Typography, Alert } from 'antd';
import { useState } from 'react';
import { stockAPI } from '../services/api';

const { Text } = Typography;

interface StockAnalysisProps {
  code: string;
  currentPrice?: number;
}

const forecastStrategyOptions = [
  { value: 'ma_cross', label: '均线金叉' },
  { value: 'macd_cross', label: 'MACD金叉死叉' },
  { value: 'rsi_reversal', label: 'RSI超买超卖' },
  { value: 'bollinger_break', label: '布林带突破' },
  { value: 'sar_parabolic', label: 'SAR抛物线转向' },
];

export default function StockAnalysis({ code, currentPrice }: StockAnalysisProps) {
  const [forecastStrategy, setForecastStrategy] = useState('macd_cross');
  const [forecastDays, setForecastDays] = useState(22);
  const [forecastResult, setForecastResult] = useState<any>(null);
  const [forecastLoading, setForecastLoading] = useState(false);
  const [selectedScenario, setSelectedScenario] = useState(0);

  const handleRunForecast = async () => {
    if (!code) return;
    setForecastLoading(true);
    setForecastResult(null);
    setSelectedScenario(0);
    try {
      const res = await stockAPI.runForecast({
        code,
        strategy: forecastStrategy,
        params: {},
        forecast_days: forecastDays,
      });
      setForecastResult(res);
    } catch (e: any) {
      alert('预测失败: ' + (e.message || ''));
    } finally {
      setForecastLoading(false);
    }
  };

  const scenarioColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 120 },
    {
      title: '预测价',
      dataIndex: 'price',
      key: 'price',
      align: 'right' as const,
      width: 120,
      render: (v: number) => `¥${v.toFixed(2)}`,
    },
    {
      title: '信号',
      dataIndex: 'signal',
      key: 'signal',
      align: 'center' as const,
      width: 100,
      render: (sig: number, record: any) => (
        <Tag
          color={sig === 1 ? 'red' : sig === -1 ? 'green' : 'default'}
        >
          {record.action}
        </Tag>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card title="AI智能分析" styles={{ body: { padding: 24 } }}>
        <Alert
          type="info"
          message="AI分析功能开发中"
          description="即将接入多Agent分析引擎，为您提供智能化的技术分析和投资建议。"
          showIcon
        />
      </Card>

      {code && (
        <Card
          title={
            <Space>
              <span>🔮</span>
              <span>未来买卖预测</span>
            </Space>
          }
        >
          <Space wrap style={{ marginBottom: 16 }}>
            <Space direction="vertical" size={0}>
              <Text type="secondary" style={{ fontSize: 12 }}>策略</Text>
              <Select
                value={forecastStrategy}
                onChange={(v) => {
                  setForecastStrategy(v);
                  setForecastResult(null);
                }}
                options={forecastStrategyOptions}
                style={{ width: 180 }}
                size="small"
              />
            </Space>
            <Space direction="vertical" size={0}>
              <Text type="secondary" style={{ fontSize: 12 }}>预测天数</Text>
              <InputNumber
                value={forecastDays}
                onChange={(v) => setForecastDays(v ?? 22)}
                min={5}
                max={60}
                size="small"
                style={{ width: 80 }}
              />
            </Space>
            <Button
              type="primary"
              loading={forecastLoading}
              onClick={handleRunForecast}
              size="small"
            >
              {forecastLoading ? '预测中...' : '开始预测'}
            </Button>
          </Space>

          {forecastResult && (
            <Space direction="vertical" size="middle" style={{ width: '100%' }}>
              <Space wrap>
                <Text type="secondary">当前信号：</Text>
                <Tag
                  color={
                    forecastResult.current_signal === '买入'
                      ? 'red'
                      : forecastResult.current_signal === '卖出'
                        ? 'green'
                        : 'default'
                  }
                >
                  {forecastResult.current_signal}
                </Tag>
                <Text type="secondary">
                  最新价：<Text strong>¥{forecastResult.last_price?.toFixed(2)}</Text>
                </Text>
                <Text type="secondary">最新日期：{forecastResult.last_date}</Text>
              </Space>

              <Space wrap size={[8, 8]}>
                {forecastResult.scenarios?.map((s: any, i: number) => (
                  <Button
                    key={i}
                    type={selectedScenario === i ? 'primary' : 'default'}
                    size="small"
                    ghost={selectedScenario === i}
                    onClick={() => setSelectedScenario(i)}
                  >
                    <Space direction="vertical" size={0}>
                      <Text strong>{s.name}</Text>
                      <Text
                        style={{
                          fontSize: 10,
                          color: s.metrics.return >= 0 ? '#cf1322' : '#3f8600',
                        }}
                      >
                        {s.metrics.return >= 0 ? '+' : ''}{s.metrics.return}%
                      </Text>
                    </Space>
                  </Button>
                ))}
              </Space>

              {selectedScenario >= 0 && forecastResult.scenarios?.[selectedScenario] && (
                <div>
                  <Space wrap style={{ marginBottom: 8 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {forecastResult.scenarios[selectedScenario].description}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      交易：<Text strong>{forecastResult.scenarios[selectedScenario].metrics.trades}次</Text>
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      最大回撤：<Text strong style={{ color: '#3f8600' }}>
                        {forecastResult.scenarios[selectedScenario].metrics.max_drawdown}%
                      </Text>
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      买入：<Text strong style={{ color: '#cf1322' }}>
                        {forecastResult.scenarios[selectedScenario].metrics.buy_signals}
                      </Text>
                    </Text>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      卖出：<Text strong style={{ color: '#3f8600' }}>
                        {forecastResult.scenarios[selectedScenario].metrics.sell_signals}
                      </Text>
                    </Text>
                  </Space>
                  <Table
                    columns={scenarioColumns}
                    dataSource={forecastResult.scenarios[selectedScenario].prediction?.map(
                      (p: any, i: number) => ({ ...p, key: i })
                    )}
                    size="small"
                    pagination={false}
                    scroll={{ y: 300 }}
                  />
                </div>
              )}

              <Alert type="warning" message="预测基于策略模型+历史波动率模拟，仅供参考" banner />
            </Space>
          )}
        </Card>
      )}
    </Space>
  );
}
