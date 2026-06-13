import { useState } from 'react';
import { Card, Spin, Alert, Typography, Tooltip } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { useApiUrl } from '../hooks/useApiUrl';

const { Text } = Typography;

interface Keyword {
  word: string;
  count: number;
}

interface Props {
  code: string;
}

/**
 * 舆情 tab 关键词云 — CSS 字号权重 (12-32px)
 * 不引第三方 wordcloud 库
 */
export default function KeywordCloud({ code }: Props) {
  const API = useApiUrl();
  const { data, isLoading, error } = useQuery({
    queryKey: ['sentiment-keywords', code],
    queryFn: async () => {
      const resp = await fetch(`${API}/api/sentiment/analytics/${code}?days=30&top=20`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      return resp.json() as Promise<{ keywords: Keyword[] }>;
    },
  });

  if (isLoading) {
    return (
      <Card title="热门关键词 (30 日)" size="small">
        <div style={{ textAlign: 'center', padding: 32 }}><Spin /></div>
      </Card>
    );
  }
  if (error) {
    return (
      <Card title="热门关键词 (30 日)" size="small">
        <Alert type="error" message="加载关键词失败" />
      </Card>
    );
  }
  const kws = data?.keywords || [];
  if (kws.length === 0) {
    return (
      <Card title="热门关键词 (30 日)" size="small">
        <Alert type="info" message="暂无关键词数据" />
      </Card>
    );
  }

  const maxCount = Math.max(...kws.map((k) => k.count), 1);
  const minCount = Math.min(...kws.map((k) => k.count), 1);
  const fontSize = (count: number) => {
    if (maxCount === minCount) return 18;
    return 12 + (count - minCount) / (maxCount - minCount) * 20;
  };
  const hue = (word: string) => {
    // 稳定 hash → HSL
    let h = 0;
    for (let i = 0; i < word.length; i++) h = (h * 31 + word.charCodeAt(i)) >>> 0;
    return h % 360;
  };

  return (
    <Card title={`热门关键词 (30 日, top ${kws.length})`} size="small">
      <div
        style={{
          display: 'flex',
          flexWrap: 'wrap',
          gap: '6px 12px',
          padding: 8,
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: 100,
        }}
      >
        {kws.map((k) => (
          <Tooltip key={k.word} title={`出现 ${k.count} 次`}>
            <span
              style={{
                fontSize: `${fontSize(k.count).toFixed(0)}px`,
                color: `hsl(${hue(k.word)}, 65%, 45%)`,
                cursor: 'default',
                fontWeight: k.count > maxCount * 0.7 ? 600 : 400,
                userSelect: 'none',
              }}
            >
              {k.word}
            </span>
          </Tooltip>
        ))}
      </div>
      <Text type="secondary" style={{ fontSize: 11, marginTop: 8, display: 'block' }}>
        字号越大 = 出现次数越多. 来源: 新闻标题 + 帖子标题 NLP 切词.
      </Text>
    </Card>
  );
}