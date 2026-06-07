/**
 * Sprint5: 策略配置 UI
 *
 * 可视化编辑 backtest / 推荐 / 风险预算等参数
 * 持久化到 localStorage (无需后端)
 */
import { useState, useEffect } from 'react';
import {
  Card, Form, InputNumber, Switch, Select, Slider, Input, Button, Space,
  Row, Col, Typography, Divider, Tag, Alert, App, Tabs,
} from 'antd';
import { SaveOutlined, ReloadOutlined, DeleteOutlined } from '@ant-design/icons';

const { Text } = Typography;

const STORAGE_KEY = 'stock_trading_strategy_config_v1';

interface Config {
  // 基础工具
  jichang: {
    min_score: number;
    forward_days: number;
    top_pct: number;
    pe_max: number;
  };
  youzi: {
    min_score: number;
    min_turnover: number;
    min_momentum: number;
  };
  lianghua: {
    min_score: number;
    macd_fast: number;
    macd_slow: number;
  };
  sector_momentum: {
    min_score: number;
    min_sector_strength: number;
  };
  // 风控
  risk: {
    max_position_pct: number;
    max_single_stock_pct: number;
    max_drawdown_pct: number;
    stop_loss_pct: number;
    take_profit_pct: number;
    enable_kelly: boolean;
    kelly_fraction: number;
  };
  // 推荐
  recommend: {
    enable: boolean;
    risk_profile: 'conservative' | 'moderate' | 'aggressive';
    max_stocks: number;
    default_capital: number;
    min_corr_threshold: number;
  };
  // ML
  ml: {
    enable_short_term: boolean;
    enable_mid_term: boolean;
    shadow_ratio: number;
    auto_calibration: boolean;
    psi_alert: number;
  };
}

const DEFAULT_CONFIG: Config = {
  jichang: { min_score: 15, forward_days: 5, top_pct: 0.2, pe_max: 50 },
  youzi: { min_score: 25, min_turnover: 5, min_momentum: 0.03 },
  lianghua: { min_score: 20, macd_fast: 12, macd_slow: 26 },
  sector_momentum: { min_score: 30, min_sector_strength: 0.6 },
  risk: {
    max_position_pct: 80,
    max_single_stock_pct: 25,
    max_drawdown_pct: 15,
    stop_loss_pct: 8,
    take_profit_pct: 20,
    enable_kelly: false,
    kelly_fraction: 0.5,
  },
  recommend: {
    enable: true,
    risk_profile: 'moderate',
    max_stocks: 5,
    default_capital: 100000,
    min_corr_threshold: 0.75,
  },
  ml: {
    enable_short_term: true,
    enable_mid_term: true,
    shadow_ratio: 0.05,
    auto_calibration: true,
    psi_alert: 0.25,
  },
};

export default function StrategyConfig() {
  const { message } = App.useApp();
  const [config, setConfig] = useState<Config>(DEFAULT_CONFIG);

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY);
      if (saved) setConfig({ ...DEFAULT_CONFIG, ...JSON.parse(saved) });
    } catch (e) {
      console.warn('load config failed', e);
    }
  }, []);

  const updateSection = <K extends keyof Config>(key: K, value: Config[K]) => {
    setConfig(c => ({ ...c, [key]: value }));
  };

  const handleSave = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(config));
    message.success('已保存到浏览器 localStorage');
  };

  const handleReset = () => {
    setConfig(DEFAULT_CONFIG);
    localStorage.removeItem(STORAGE_KEY);
    message.info('已重置为默认');
  };

  return (
    <div style={{ padding: 16 }}>
      <h2>策略配置</h2>
      <Space style={{ marginBottom: 12 }}>
        <Button type="primary" icon={<SaveOutlined />} onClick={handleSave}>保存</Button>
        <Button icon={<ReloadOutlined />} onClick={handleReset}>重置</Button>
        <Tag>存储: localStorage</Tag>
      </Space>
      <Alert
        type="info"
        showIcon
        message="配置说明"
        description="本页面配置仅保存在本地浏览器, 用于个性化推荐与回测参数。生产参数请通过 .env 环境变量配置。"
        style={{ marginBottom: 16 }}
      />

      <Tabs defaultActiveKey="strategies" items={[
        {
          key: 'strategies',
          label: '策略参数',
          children: (
            <>
              <Card title="基础工具 (jichang)" style={{ marginBottom: 12 }}>
                <Row gutter={16}>
                  <Col span={6}>
                    <Form.Item label="最低分数">
                      <InputNumber
                        min={0} max={100}
                        value={config.jichang.min_score}
                        onChange={v => updateSection('jichang', { ...config.jichang, min_score: v || 15 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="前向天数">
                      <InputNumber
                        min={1} max={30}
                        value={config.jichang.forward_days}
                        onChange={v => updateSection('jichang', { ...config.jichang, forward_days: v || 5 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="Top比例">
                      <Slider
                        min={0.05} max={0.5} step={0.05}
                        value={config.jichang.top_pct}
                        onChange={v => updateSection('jichang', { ...config.jichang, top_pct: v })}
                      />
                      <Text type="secondary">{config.jichang.top_pct}</Text>
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="PE上限">
                      <InputNumber
                        min={5} max={200}
                        value={config.jichang.pe_max}
                        onChange={v => updateSection('jichang', { ...config.jichang, pe_max: v || 50 })}
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>

              <Card title="游资 (youzi)" style={{ marginBottom: 12 }}>
                <Row gutter={16}>
                  <Col span={8}>
                    <Form.Item label="最低分数">
                      <InputNumber
                        min={0} max={100}
                        value={config.youzi.min_score}
                        onChange={v => updateSection('youzi', { ...config.youzi, min_score: v || 25 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="最低换手率(%)">
                      <InputNumber
                        min={1} max={50}
                        value={config.youzi.min_turnover}
                        onChange={v => updateSection('youzi', { ...config.youzi, min_turnover: v || 5 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={8}>
                    <Form.Item label="最低动量">
                      <InputNumber
                        min={0} max={0.2} step={0.01}
                        value={config.youzi.min_momentum}
                        onChange={v => updateSection('youzi', { ...config.youzi, min_momentum: v || 0.03 })}
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>

              <Card title="量化 (lianghua) / 板块动量 (sector_momentum)">
                <Row gutter={16}>
                  <Col span={6}>
                    <Form.Item label="量化-最低分">
                      <InputNumber
                        value={config.lianghua.min_score}
                        onChange={v => updateSection('lianghua', { ...config.lianghua, min_score: v || 20 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="MACD 快线">
                      <InputNumber
                        value={config.lianghua.macd_fast}
                        onChange={v => updateSection('lianghua', { ...config.lianghua, macd_fast: v || 12 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="MACD 慢线">
                      <InputNumber
                        value={config.lianghua.macd_slow}
                        onChange={v => updateSection('lianghua', { ...config.lianghua, macd_slow: v || 26 })}
                      />
                    </Form.Item>
                  </Col>
                  <Col span={6}>
                    <Form.Item label="板块-最低分">
                      <InputNumber
                        value={config.sector_momentum.min_score}
                        onChange={v => updateSection('sector_momentum', { ...config.sector_momentum, min_score: v || 30 })}
                      />
                    </Form.Item>
                  </Col>
                </Row>
              </Card>
            </>
          ),
        },
        {
          key: 'risk',
          label: '风控',
          children: (
            <Card>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="最大仓位(%)">
                    <InputNumber
                      min={10} max={100}
                      value={config.risk.max_position_pct}
                      onChange={v => updateSection('risk', { ...config.risk, max_position_pct: v || 80 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="单股上限(%)">
                    <InputNumber
                      min={5} max={50}
                      value={config.risk.max_single_stock_pct}
                      onChange={v => updateSection('risk', { ...config.risk, max_single_stock_pct: v || 25 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="组合回撤熔断(%)">
                    <InputNumber
                      min={5} max={50}
                      value={config.risk.max_drawdown_pct}
                      onChange={v => updateSection('risk', { ...config.risk, max_drawdown_pct: v || 15 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="止损(%)">
                    <InputNumber
                      min={1} max={20}
                      value={config.risk.stop_loss_pct}
                      onChange={v => updateSection('risk', { ...config.risk, stop_loss_pct: v || 8 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="止盈(%)">
                    <InputNumber
                      min={5} max={100}
                      value={config.risk.take_profit_pct}
                      onChange={v => updateSection('risk', { ...config.risk, take_profit_pct: v || 20 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="凯利分数">
                    <Slider
                      min={0.1} max={1.0} step={0.05}
                      value={config.risk.kelly_fraction}
                      onChange={v => updateSection('risk', { ...config.risk, kelly_fraction: v })}
                    />
                    <Text type="secondary">{config.risk.kelly_fraction} (1=全凯利, 0.5=半凯利)</Text>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="启用凯利仓位">
                    <Switch
                      checked={config.risk.enable_kelly}
                      onChange={v => updateSection('risk', { ...config.risk, enable_kelly: v })}
                    />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          ),
        },
        {
          key: 'recommend',
          label: '组合推荐',
          children: (
            <Card>
              <Row gutter={16}>
                <Col span={6}>
                  <Form.Item label="启用推荐">
                    <Switch
                      checked={config.recommend.enable}
                      onChange={v => updateSection('recommend', { ...config.recommend, enable: v })}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="风险偏好">
                    <Select
                      value={config.recommend.risk_profile}
                      onChange={v => updateSection('recommend', { ...config.recommend, risk_profile: v })}
                      options={[
                        { value: 'conservative', label: '保守' },
                        { value: 'moderate', label: '稳健' },
                        { value: 'aggressive', label: '激进' },
                      ]}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="最大持股数">
                    <InputNumber
                      min={1} max={20}
                      value={config.recommend.max_stocks}
                      onChange={v => updateSection('recommend', { ...config.recommend, max_stocks: v || 5 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={6}>
                  <Form.Item label="默认资金(¥)">
                    <InputNumber
                      min={10000} step={10000}
                      value={config.recommend.default_capital}
                      onChange={v => updateSection('recommend', { ...config.recommend, default_capital: v || 100000 })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="相关性过滤阈值">
                    <Slider
                      min={0.5} max={0.95} step={0.05}
                      value={config.recommend.min_corr_threshold}
                      onChange={v => updateSection('recommend', { ...config.recommend, min_corr_threshold: v })}
                    />
                    <Text type="secondary">高于此值的股票被过滤 (避免重复配置)</Text>
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          ),
        },
        {
          key: 'ml',
          label: 'ML',
          children: (
            <Card>
              <Row gutter={16}>
                <Col span={8}>
                  <Form.Item label="启用短线模型">
                    <Switch
                      checked={config.ml.enable_short_term}
                      onChange={v => updateSection('ml', { ...config.ml, enable_short_term: v })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="启用中线模型">
                    <Switch
                      checked={config.ml.enable_mid_term}
                      onChange={v => updateSection('ml', { ...config.ml, enable_mid_term: v })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="影子流量比例">
                    <Slider
                      min={0} max={0.2} step={0.01}
                      value={config.ml.shadow_ratio}
                      onChange={v => updateSection('ml', { ...config.ml, shadow_ratio: v })}
                    />
                    <Text type="secondary">{(config.ml.shadow_ratio * 100).toFixed(0)}% 流量走影子</Text>
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="自动校准">
                    <Switch
                      checked={config.ml.auto_calibration}
                      onChange={v => updateSection('ml', { ...config.ml, auto_calibration: v })}
                    />
                  </Form.Item>
                </Col>
                <Col span={8}>
                  <Form.Item label="PSI 告警阈值">
                    <InputNumber
                      min={0.05} max={0.5} step={0.05}
                      value={config.ml.psi_alert}
                      onChange={v => updateSection('ml', { ...config.ml, psi_alert: v || 0.25 })}
                    />
                  </Form.Item>
                </Col>
              </Row>
            </Card>
          ),
        },
      ]} />
    </div>
  );
}
