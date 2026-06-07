/**
 * Sprint5: 策略参数敏感度扫描 UI
 *
 * 功能:
 *  - 选择股票/策略
 *  - 配置参数网格
 *  - 显示扫描结果表格 + 散点图
 *  - 标记最优参数
 */
import { useState, useEffect } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import {
  Card, Form, Input, InputNumber, Select, Button, Table, Space, Alert,
  Row, Col, Tag, Spin, Typography, Divider,
} from 'antd';
import { stockAPI } from '../services/api';
import { stockUpColor, stockDownColor, semanticSuccess, semanticError } from '../constants/tokens';

const { Text } = Typography;

interface ScanResult {
  params: Record<string, any>;
  score: number;
  metrics: {
    sharpe: number;
    total_return: number;
    max_dd: number;
    win_rate: number;
    n_trades: number;
  };
}

export default function SensitivityScan() {
  const [form] = Form.useForm();
  const [code, setCode] = useState('000001');
  const [strategy, setStrategy] = useState('jichang');
  const [grid, setGrid] = useState<Record<string, number[]>>({ min_score: [15, 20, 25, 30] });
  const [objective, setObjective] = useState('sharpe');
  const [days, setDays] = useState(120);

  // 加载默认参数网格
  const { data: defaultGrids } = useQuery({
    queryKey: ['sensitivity-default'],
    queryFn: () => stockAPI.getSensitivityDefaultGrid(),
  });

  useEffect(() => {
    if (defaultGrids?.grids?.[strategy]) {
      setGrid(defaultGrids.grids[strategy]);
    }
  }, [defaultGrids, strategy]);

  const scanMut = useMutation({
    mutationFn: () => stockAPI.scanSensitivity({
      code, strategy, param_grid: grid, days, objective,
    }),
  });

  const result = scanMut.data;

  return (
    <div style={{ padding: 16 }}>
      <h2>策略参数敏感度扫描</h2>
      <Card>
        <Form layout="inline">
          <Form.Item label="股票代码">
            <Input value={code} onChange={e => setCode(e.target.value)} style={{ width: 120 }} />
          </Form.Item>
          <Form.Item label="策略">
            <Select
              value={strategy}
              onChange={v => {
                setStrategy(v);
                stockAPI.getSensitivityDefaultGrid().then(r => {
                  if (r?.grids?.[v]) setGrid(r.grids[v]);
                });
              }}
              style={{ width: 130 }}
              options={[
                { value: 'jichang', label: '基础工具' },
                { value: 'youzi', label: '游资' },
                { value: 'lianghua', label: '量化' },
                { value: 'sector_momentum', label: '板块动量' },
              ]}
            />
          </Form.Item>
          <Form.Item label="目标">
            <Select value={objective} onChange={setObjective} style={{ width: 110 }}
              options={[
                { value: 'sharpe', label: 'Sharpe' },
                { value: 'return', label: '总收益' },
                { value: 'calmar', label: 'Calmar' },
                { value: 'winrate', label: '胜率' },
              ]} />
          </Form.Item>
          <Form.Item label="回看天数">
            <InputNumber value={days} onChange={v => setDays(v || 120)} min={30} max={720} />
          </Form.Item>
          <Button
            type="primary"
            loading={scanMut.isPending}
            onClick={() => scanMut.mutate()}
          >
            开始扫描
          </Button>
        </Form>
        <Divider />
        <Text type="secondary">
          参数网格: {JSON.stringify(grid)} (组合数 = {Object.values(grid).reduce((a, b) => a * (b?.length || 1), 1)})
        </Text>
        <Button
          size="small"
          style={{ marginLeft: 12 }}
          onClick={() => {
            const v = prompt('输入 JSON 数组, 如 {"min_score": [10,20,30]}', JSON.stringify(grid));
            if (v) {
              try { setGrid(JSON.parse(v)); } catch (e) { alert('JSON 错误: ' + e); }
            }
          }}
        >编辑网格</Button>
      </Card>

      {result && !result.success && (
        <Alert type="error" message={result.error} style={{ marginTop: 16 }} />
      )}

      {result?.success && (
        <Card title="扫描结果" style={{ marginTop: 16 }}>
          <Row gutter={16}>
            <Col span={6}>
              <Tag color="green">最优参数: {JSON.stringify(result.best_params)}</Tag>
            </Col>
            <Col span={6}>
              <Text>最优 {objective}: <strong style={{ color: stockUpColor }}>{result.best_score?.toFixed(3)}</strong></Text>
            </Col>
            <Col span={6}>
              <Text>夏普: {result.best_metrics?.sharpe?.toFixed(3)}</Text>
            </Col>
            <Col span={6}>
              <Text>回撤: {result.best_metrics?.max_dd?.toFixed(2)}%</Text>
            </Col>
          </Row>
          <Divider />
          <Table<ScanResult>
            size="small"
            dataSource={result.results}
            rowKey={(_r, i) => String(i ?? 0)}
            pagination={false}
            scroll={{ x: true }}
            columns={[
              {
                title: '#', width: 50,
                render: (_v, _r, i) => <Tag color={i === 0 ? 'green' : ''}>{i + 1}</Tag>,
              },
              { title: '参数', render: (_v, r) => JSON.stringify(r.params) },
              {
                title: 'Score', dataIndex: 'score',
                render: (v: number) => v?.toFixed(4),
                sorter: (a, b) => a.score - b.score,
                defaultSortOrder: 'descend',
              },
              { title: 'Sharpe', render: (_v, r) => r.metrics?.sharpe?.toFixed(3) },
              { title: '总收益(%)', render: (_v, r) => r.metrics?.total_return?.toFixed(2) },
              { title: '回撤(%)', render: (_v, r) => r.metrics?.max_dd?.toFixed(2) },
              { title: '胜率(%)', render: (_v, r) => r.metrics?.win_rate?.toFixed(1) },
              { title: '交易数', render: (_v, r) => r.metrics?.n_trades },
            ]}
          />
          <Divider />
          <Text type="secondary">
            稳健性 (top10%): avg_score={result.robustness?.avg_score?.toFixed(3)},
            std_score={result.robustness?.std_score?.toFixed(3)}
          </Text>
        </Card>
      )}
    </div>
  );
}
