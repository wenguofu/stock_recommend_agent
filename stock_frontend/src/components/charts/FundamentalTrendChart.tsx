import { useMemo, useState } from 'react';
import { Card, Spin, Alert, Empty, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useApiUrl } from '../../hooks/useApiUrl';

const { Text } = Typography;

interface FinancialRow {
  code: string;
  report_date: string;
  revenue?: number;
  net_profit?: number;
  roe?: number;
  gross_margin?: number;
}

interface Props {
  code: string;
}

/**
 * 基本面 tab 财务趋势图 — 自绘 SVG
 * 4 条归一化曲线: 营收 / 净利润 / ROE / 毛利率
 * Y 轴归一化到首期 = 100, 共享 X 轴 (报告期)
 */
export default function FundamentalTrendChart({ code }: Props) {
  const API = useApiUrl();
  const { data, isLoading, error } = useQuery({
    queryKey: ['fundamentals-history', code],
    queryFn: async () => {
      const resp = await fetch(`${API}/api/fundamentals/${code}/history?limit=8`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json() as Promise<{ code: string; history: FinancialRow[] }>;
    },
  });

  const [hoverIdx, setHoverIdx] = useState<number | null>(null);

  if (isLoading) {
    return (
      <Card title="近 5 年财务趋势" size="small">
        <div style={{ textAlign: 'center', padding: 32 }}><Spin /></div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card title="近 5 年财务趋势" size="small">
        <Alert type="error" message="加载历史财务数据失败" />
      </Card>
    );
  }
  const history = (data?.history || []).filter(
    (r) => r.revenue != null || r.net_profit != null || r.roe != null || r.gross_margin != null
  );
  if (history.length < 2) {
    return (
      <Card title="近 5 年财务趋势" size="small">
        <Alert type="info" message="历史数据不足, 无法绘制趋势" />
      </Card>
    );
  }

  // 按 report_date 升序
  const sorted = [...history].sort((a, b) =>
    String(a.report_date).localeCompare(String(b.report_date))
  );

  // 4 条曲线 (归一化到首期 = 100)
  const series = useMemo(() => {
    const fields = [
      { key: 'revenue', label: '营收', color: '#1677ff' },
      { key: 'net_profit', label: '净利润', color: '#52c41a' },
      { key: 'roe', label: 'ROE', color: '#faad14' },
      { key: 'gross_margin', label: '毛利率', color: '#722ed1' },
    ] as const;
    return fields.map((f) => {
      const base = sorted[0]?.[f.key as keyof FinancialRow] as number | undefined;
      if (!base || base === 0) return { ...f, points: [] as Array<{ idx: number; ratio: number | null }> };
      const points = sorted.map((r, i) => {
        const v = r[f.key as keyof FinancialRow] as number | undefined;
        const ratio = v != null ? (v / base) * 100 : null;
        return { idx: i, ratio };
      });
      return { ...f, points };
    });
  }, [sorted]);

  const W = 600, H = 220, PAD_L = 40, PAD_R = 16, PAD_T = 16, PAD_B = 36;
  const xStep = (W - PAD_L - PAD_R) / Math.max(1, sorted.length - 1);
  const yMin = 0, yMax = 200; // 归一化 0~200%

  const xOf = (i: number) => PAD_L + i * xStep;
  const yOf = (v: number) => H - PAD_B - ((v - yMin) / (yMax - yMin)) * (H - PAD_T - PAD_B);

  const path = (pts: Array<{ idx: number; ratio: number | null }>) =>
    pts
      .filter((p) => p.ratio != null)
      .map((p, i) => `${i === 0 ? 'M' : 'L'} ${xOf(p.idx).toFixed(1)} ${yOf(p.ratio as number).toFixed(1)}`)
      .join(' ');

  return (
    <Card title="近 5 年财务趋势 (归一化, 首期=100)" size="small">
      <div style={{ position: 'relative' }}>
        <svg width={W} height={H} style={{ width: '100%', height: 'auto' }}>
          {/* 网格 */}
          {[0, 50, 100, 150, 200].map((g) => (
            <g key={g}>
              <line x1={PAD_L} y1={yOf(g)} x2={W - PAD_R} y2={yOf(g)} stroke="#f0f0f0" />
              <text x={4} y={yOf(g) + 4} fontSize={10} fill="#999">{g}</text>
            </g>
          ))}
          {/* 曲线 */}
          {series.map((s) => (
            <g key={s.key}>
              <path d={path(s.points)} fill="none" stroke={s.color} strokeWidth={1.5} />
              {s.points.filter((p) => p.ratio != null).map((p) => (
                <circle
                  key={p.idx}
                  cx={xOf(p.idx)} cy={yOf(p.ratio as number)} r={3}
                  fill={s.color}
                />
              ))}
            </g>
          ))}
          {/* X 轴 */}
          {sorted.map((r, i) => (
            <text key={i} x={xOf(i)} y={H - PAD_B + 16} fontSize={10} fill="#666" textAnchor="middle">
              {String(r.report_date).slice(0, 7)}
            </text>
          ))}
          {/* Hover 提示线 */}
          {hoverIdx != null && (
            <line
              x1={xOf(hoverIdx)} y1={PAD_T}
              x2={xOf(hoverIdx)} y2={H - PAD_B}
              stroke="#999" strokeDasharray="3 3"
            />
          )}
          {/* Hover 透明覆盖层 */}
          {sorted.map((_, i) => (
            <rect
              key={i}
              x={xOf(i) - xStep / 2} y={PAD_T}
              width={xStep} height={H - PAD_T - PAD_B}
              fill="transparent"
              onMouseEnter={() => setHoverIdx(i)}
              onMouseLeave={() => setHoverIdx(null)}
            />
          ))}
        </svg>
        {/* Legend */}
        <div style={{ display: 'flex', gap: 12, marginTop: 8, flexWrap: 'wrap' }}>
          {series.map((s) => (
            <Text key={s.key} style={{ fontSize: 12 }}>
              <span style={{ display: 'inline-block', width: 10, height: 10, background: s.color, marginRight: 4 }} />
              {s.label}
            </Text>
          ))}
        </div>
        {/* Hover tooltip */}
        {hoverIdx != null && (
          <div style={{ marginTop: 8, padding: 8, background: '#fafafa', borderRadius: 4, fontSize: 12 }}>
            <b>{String(sorted[hoverIdx].report_date).slice(0, 10)}</b>
            {series.map((s) => {
              const raw = sorted[hoverIdx][s.key as keyof FinancialRow];
              return (
                <div key={s.key} style={{ color: s.color }}>
                  {s.label}: {raw != null ? String(raw) : '-'}
                </div>
              );
            })}
          </div>
        )}
      </div>
      <Text type="secondary" style={{ fontSize: 11, marginTop: 8, display: 'block' }}>
        注: 数据归一化到首期 = 100, 用于观察相对增长趋势, 数值大小不代表绝对水平.
      </Text>
    </Card>
  );
}