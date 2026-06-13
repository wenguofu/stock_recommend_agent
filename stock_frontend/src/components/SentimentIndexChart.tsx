import { useState } from 'react';
import { Card, Spin, Alert, Typography } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useApiUrl } from '../hooks/useApiUrl';

const { Text } = Typography;

interface IndexPoint {
  date: string;
  score: number;
  count: number;
}

interface Props {
  code: string;
}

/**
 * 舆情 tab 情绪指数曲线 (30 日)
 * score > 0 红, < 0 绿, 0 基准线
 */
export default function SentimentIndexChart({ code }: Props) {
  const API = useApiUrl();
  const [hoverIdx, setHoverIdx] = useState<number | null>(null);
  const { data, isLoading, error } = useQuery({
    queryKey: ['sentiment-index', code],
    queryFn: async () => {
      const resp = await fetch(`${API}/api/sentiment/analytics/${code}?days=30&top=20`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json() as Promise<{ index: IndexPoint[] }>;
    },
  });

  if (isLoading) {
    return (
      <Card title="30 日情绪指数" size="small">
        <div style={{ textAlign: 'center', padding: 32 }}><Spin /></div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card title="30 日情绪指数" size="small">
        <Alert type="error" message="加载情绪指数失败" />
      </Card>
    );
  }
  const index = data?.index || [];
  if (index.length < 3) {
    return (
      <Card title="30 日情绪指数" size="small">
        <Alert type="info" message="舆情数据不足, 无法绘制情绪曲线" />
      </Card>
    );
  }

  const W = 600, H = 180, PAD_L = 36, PAD_R = 16, PAD_T = 12, PAD_B = 32;
  const sorted = [...index].sort((a, b) => a.date.localeCompare(b.date));
  const xStep = (W - PAD_L - PAD_R) / Math.max(1, sorted.length - 1);
  const xOf = (i: number) => PAD_L + i * xStep;
  const yMid = H / 2;
  const yRange = (H - PAD_T - PAD_B) / 2;
  const yOf = (s: number) => yMid - s * yRange;

  // segments by sign (red if > 0, green if < 0)
  const segs: Array<{ from: number; to: number; color: string }> = [];
  for (let i = 0; i < sorted.length - 1; i++) {
    const s0 = sorted[i].score, s1 = sorted[i + 1].score;
    const color = s0 > 0 || s1 > 0 ? '#cf1322' : '#389e0d';
    if (s0 === 0 && s1 === 0) continue;
    segs.push({ from: i, to: i + 1, color });
  }

  return (
    <Card title="30 日情绪指数 (-1~1, 0 为基准)" size="small">
      <svg width={W} height={H} style={{ width: '100%', height: 'auto' }}>
        {/* 0 基准线 */}
        <line x1={PAD_L} y1={yMid} x2={W - PAD_R} y2={yMid} stroke="#999" strokeDasharray="4 2" />
        <text x={4} y={yMid + 4} fontSize={10} fill="#666">0</text>
        <text x={4} y={PAD_T + 8} fontSize={10} fill="#999">+1</text>
        <text x={4} y={H - PAD_B + 4} fontSize={10} fill="#999">-1</text>
        {/* 曲线 */}
        {segs.map((s, i) => {
          const x0 = xOf(s.from), x1 = xOf(s.to);
          const y0 = yOf(sorted[s.from].score), y1 = yOf(sorted[s.to].score);
          return <line key={i} x1={x0} y1={y0} x2={x1} y2={y1} stroke={s.color} strokeWidth={1.5} />;
        })}
        {/* 节点 */}
        {sorted.map((p, i) => (
          <circle
            key={i}
            cx={xOf(i)} cy={yOf(p.score)} r={2.5}
            fill={p.score > 0 ? '#cf1322' : p.score < 0 ? '#389e0d' : '#999'}
          />
        ))}
        {/* X 轴日期 (稀疏) */}
        {sorted.map((p, i) =>
          i % Math.ceil(sorted.length / 6) === 0 || i === sorted.length - 1 ? (
            <text key={i} x={xOf(i)} y={H - 8} fontSize={10} fill="#666" textAnchor="middle">
              {p.date.slice(5)}
            </text>
          ) : null
        )}
        {/* Hover */}
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
        {hoverIdx != null && (
          <line
            x1={xOf(hoverIdx)} y1={PAD_T}
            x2={xOf(hoverIdx)} y2={H - PAD_B}
            stroke="#999" strokeDasharray="3 3"
          />
        )}
      </svg>
      {hoverIdx != null && (
        <div style={{ marginTop: 8, padding: 8, background: '#fafafa', borderRadius: 4, fontSize: 12 }}>
          <b>{sorted[hoverIdx].date}</b>: score={sorted[hoverIdx].score.toFixed(3)}, news={sorted[hoverIdx].count}
        </div>
      )}
      <Text type="secondary" style={{ fontSize: 11, marginTop: 8, display: 'block' }}>
        score = (正面词数 - 负面词数) / 总词数. 仅基于新闻/帖子标题 NLP 估算, 不构成投资建议.
      </Text>
    </Card>
  );
}