import { useState, useEffect, useRef } from 'react';
import { Card, Slider, Spin, Alert, Statistic, Row, Col, Typography, Space, Tag } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useApiUrl } from '../hooks/useApiUrl';

const { Text, Paragraph } = Typography;

interface Props {
  code: string;
}

interface DCFResult {
  code?: string;
  fair_value_per_share?: number;
  current_price?: number;
  upside_pct?: number | null;
  assumptions?: { growth: number; discount: number; terminal: number; years: number };
  error?: string;
}

/**
 * 基本面 tab DCF 估值卡 — 3 Slider (增长/折现/永续)
 * 防抖 300ms 后重新调 DCF API, 实时显示公允价值 + 上行空间
 */
export default function DCFValuation({ code }: Props) {
  const API = useApiUrl();
  const [growth, setGrowth] = useState(0.15);
  const [discount, setDiscount] = useState(0.10);
  const [terminal, setTerminal] = useState(0.03);
  const [debounced, setDebounced] = useState({ growth, discount, terminal });
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (timerRef.current) clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => {
      setDebounced({ growth, discount, terminal });
    }, 300);
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, [growth, discount, terminal]);

  const { data, isLoading, error } = useQuery({
    queryKey: ['dcf', code, debounced.growth, debounced.discount, debounced.terminal],
    queryFn: async () => {
      const qs = new URLSearchParams({
        growth: String(debounced.growth),
        discount: String(debounced.discount),
        terminal: String(debounced.terminal),
      });
      const resp = await fetch(`${API}/api/valuation/dcf/${code}?${qs}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json() as Promise<DCFResult>;
    },
  });

  const pct = (v: number) => `${(v * 100).toFixed(0)}%`;
  const upsideColor = (data?.upside_pct ?? 0) > 0 ? '#cf1322' : '#389e0d';

  return (
    <Card title="DCF 简易估值" size="small">
      <Space direction="vertical" style={{ width: '100%' }} size="middle">
        <div>
          <Text>5 年增速 (g): <Tag color="blue">{pct(growth)}</Tag></Text>
          <Slider
            min={0} max={0.30} step={0.01}
            value={growth}
            onChange={(v) => setGrowth(v as number)}
            tooltip={{ formatter: (v) => `${((v ?? 0) * 100).toFixed(0)}%` }}
          />
        </div>
        <div>
          <Text>折现率 (r): <Tag color="blue">{pct(discount)}</Tag></Text>
          <Slider
            min={0.05} max={0.20} step={0.005}
            value={discount}
            onChange={(v) => setDiscount(v as number)}
            tooltip={{ formatter: (v) => `${((v ?? 0) * 100).toFixed(1)}%` }}
          />
        </div>
        <div>
          <Text>永续增速 (g_t): <Tag color="blue">{pct(terminal)}</Tag></Text>
          <Slider
            min={0} max={0.05} step={0.005}
            value={terminal}
            onChange={(v) => setTerminal(v as number)}
            tooltip={{ formatter: (v) => `${((v ?? 0) * 100).toFixed(1)}%` }}
          />
        </div>

        {error ? (
          <Alert type="error" message={`DCF 计算失败: ${String(error)}`} />
        ) : isLoading ? (
          <Spin />
        ) : data?.error ? (
          <Alert type="warning" message={data.error} />
        ) : (
          <Row gutter={16}>
            <Col span={8}>
              <Statistic
                title="公允价值"
                value={data?.fair_value_per_share ?? 0}
                precision={2}
                suffix="元"
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="当前价"
                value={data?.current_price ?? 0}
                precision={2}
                suffix="元"
              />
            </Col>
            <Col span={8}>
              <Statistic
                title="上行空间"
                value={data?.upside_pct ?? 0}
                precision={2}
                suffix="%"
                valueStyle={{ color: upsideColor }}
              />
            </Col>
          </Row>
        )}

        <Paragraph type="secondary" style={{ fontSize: 11, marginBottom: 0 }}>
          假设: 5 年显式预测 + Gordon 永续. 仅适合成长股, 周期股请谨慎参考.
        </Paragraph>
      </Space>
    </Card>
  );
}