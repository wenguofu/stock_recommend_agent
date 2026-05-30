import { useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Tabs, Card, Descriptions, Spin, Space, Table, Tag, Statistic, Typography, Row, Col, Alert } from 'antd';
import { ArrowUpOutlined, ArrowDownOutlined } from '@ant-design/icons';
import { useState, useEffect } from 'react';
import { stockAPI } from '../services/api';
import CandlestickChart from '../components/charts/CandlestickChart';
import AIAnalyzeButton from '../components/AIAnalyzeButton';
import MoneyFlowPanel from '../components/MoneyFlowPanel';
import RiskPanel from '../components/RiskPanel';
import MLPredictPanel from '../components/MLPredictPanel';
import StockHeader from '../components/StockHeader';
import StockAnalysis from '../components/StockAnalysis';
import StockDebate from '../components/StockDebate';
import ValuationPanel from '../components/ValuationPanel';

const { Text } = Typography;

export default function StockDetail() {
  const { code } = useParams<{ code: string }>();
  const codeStr = code || '';

  const { data: realtimeData, isLoading: realtimeLoading } = useQuery({
    queryKey: ['realtime', codeStr],
    queryFn: () => stockAPI.getRealtime(codeStr),
    enabled: !!codeStr,
  });

  const { data: comprehensiveData, isLoading: comprehensiveLoading } = useQuery({
    queryKey: ['comprehensive', codeStr],
    queryFn: () => stockAPI.getComprehensive(codeStr),
    enabled: !!codeStr,
  });

  const { data: sentimentData, isLoading: sentimentLoading } = useQuery({
    queryKey: ['sentiment', codeStr],
    queryFn: () => stockAPI.getSentiment(codeStr, 7),
    enabled: !!codeStr,
  });

  const { data: dailyData, isLoading: dailyLoading } = useQuery({
    queryKey: ['daily', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const response = await fetch(`${apiUrl}/api/sina/daily/${codeStr}?count=240`);
      if (!response.ok) throw new Error('Failed to fetch daily data');
      return response.json();
    },
    enabled: !!codeStr,
  });

  const { data: watchlistData } = useQuery({
    queryKey: ['watchlist-stock', codeStr],
    queryFn: async () => {
      const items = await stockAPI.getWatchlist();
      return items.find((item: any) => item.code === codeStr) || null;
    },
    enabled: !!codeStr,
  });

  const positionCost = watchlistData?.cost_price;
  const positionShares = watchlistData?.shares;
  const hasPosition =
    positionCost != null && positionShares != null && positionShares > 0;
  const currentPrice =
    realtimeData?.current_price || comprehensiveData?.realtime?.current_price || 0;
  const positionValue = hasPosition ? currentPrice * positionShares : 0;
  const positionCostTotal = hasPosition ? positionCost * positionShares : 0;
  const positionPnl = positionValue - positionCostTotal;
  const positionPnlPercent =
    positionCost && positionCost > 0
      ? ((currentPrice - positionCost) / positionCost) * 100
      : 0;

  const { data: moneyFlowHistory, isLoading: moneyFlowHistoryLoading } = useQuery({
    queryKey: ['moneyFlowHistory', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const response = await fetch(`${apiUrl}/api/sina/money_flow/history/${codeStr}?days=60`);
      if (!response.ok) throw new Error('Failed to fetch money flow history');
      const result = await response.json();
      const data = result.data || [];
      return data.sort(
        (a: any, b: any) => new Date(b.date).getTime() - new Date(a.date).getTime()
      );
    },
    enabled: !!codeStr,
  });

  const { data: riskData } = useQuery({
    queryKey: ['risk', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const positionData = (window as any).__positionData;
      const body: any = { code: codeStr };
      if (positionData) body.position = positionData;
      const response = await fetch(`${apiUrl}/api/risk/report`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!response.ok) throw new Error('Failed to fetch risk data');
      const result = await response.json();
      return result.data || null;
    },
    enabled: !!codeStr,
    retry: 1,
  });

  const { data: mlData } = useQuery({
    queryKey: ['ml_predict', codeStr],
    queryFn: async () => {
      const apiUrl = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:35000';
      const response = await fetch(`${apiUrl}/api/ml/predict/${codeStr}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ horizon_days: 5 }),
      });
      if (!response.ok) throw new Error('Failed to fetch ML prediction');
      return response.json();
    },
    enabled: !!codeStr,
    retry: 1,
  });

  const displayData = comprehensiveData?.realtime || realtimeData;
  const isUp = (displayData?.change_percent ?? 0) >= 0;
  const upColor = '#cf1322';
  const downColor = '#3f8600';

  const moneyFlowHistoryColumns = [
    { title: '日期', dataIndex: 'date', key: 'date', width: 110 },
    {
      title: '主力净流入',
      dataIndex: 'main_net_inflow',
      key: 'main_net_inflow',
      align: 'right' as const,
      width: 120,
      render: (v: number) =>
        v != null ? (
          <Text style={{ color: v >= 0 ? upColor : downColor }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}万
          </Text>
        ) : '--',
    },
    {
      title: '超大单',
      dataIndex: 'super_large_net_inflow',
      key: 'super_large',
      align: 'right' as const,
      width: 110,
      render: (v: number) =>
        v != null ? (
          <Text style={{ color: v >= 0 ? upColor : downColor }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}万
          </Text>
        ) : '--',
    },
    {
      title: '大单',
      dataIndex: 'large_net_inflow',
      key: 'large',
      align: 'right' as const,
      width: 110,
      render: (v: number) =>
        v != null ? (
          <Text style={{ color: v >= 0 ? upColor : downColor }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}万
          </Text>
        ) : '--',
    },
    {
      title: '收盘价',
      dataIndex: 'close',
      key: 'close',
      align: 'right' as const,
      width: 90,
      render: (v: number) => (v != null ? v.toFixed(2) : '--'),
    },
    {
      title: '涨跌幅',
      dataIndex: 'change_percent',
      key: 'change_percent',
      align: 'right' as const,
      width: 90,
      render: (v: number) =>
        v != null ? (
          <Text style={{ color: v >= 0 ? upColor : downColor }}>
            {v >= 0 ? '+' : ''}{v.toFixed(2)}%
          </Text>
        ) : '--',
    },
  ];

  const tabItems = [
    {
      key: 'chart',
      label: 'K线图',
      children: (
        <Spin spinning={dailyLoading}>
          <CandlestickChart
            code={codeStr}
            indicatorsData={
              dailyData?.raw_data?.daily ||
              dailyData?.daily ||
              dailyData?.data ||
              comprehensiveData?.daily ||
              null
            }
          />
        </Spin>
      ),
    },
    {
      key: 'indicators',
      label: '技术指标',
      children: comprehensiveData?.indicators ? (
        <Card title="技术指标">
          <Descriptions column={{ xs: 2, sm: 3, md: 4 }} bordered size="small">
            {comprehensiveData.indicators.MA &&
              Object.entries(comprehensiveData.indicators.MA).map(
                ([key, value]: [string, any]) => (
                  <Descriptions.Item key={key} label={key}>
                    {typeof value === 'number' ? value.toFixed(2) : value}
                  </Descriptions.Item>
                )
              )}
            {comprehensiveData.indicators.RSI != null && (
              <Descriptions.Item label="RSI">
                {comprehensiveData.indicators.RSI.toFixed(2)}
              </Descriptions.Item>
            )}
            {comprehensiveData.indicators.MACD && (
              <>
                <Descriptions.Item label="MACD DIF">
                  {comprehensiveData.indicators.MACD.DIF?.toFixed(2)}
                </Descriptions.Item>
                <Descriptions.Item label="MACD DEA">
                  {comprehensiveData.indicators.MACD.DEA?.toFixed(2)}
                </Descriptions.Item>
              </>
            )}
            {comprehensiveData.indicators.KDJ && (
              <>
                <Descriptions.Item label="KDJ K">
                  {comprehensiveData.indicators.KDJ.K?.toFixed(2)}
                </Descriptions.Item>
                <Descriptions.Item label="KDJ D">
                  {comprehensiveData.indicators.KDJ.D?.toFixed(2)}
                </Descriptions.Item>
                <Descriptions.Item label="KDJ J">
                  {comprehensiveData.indicators.KDJ.J?.toFixed(2)}
                </Descriptions.Item>
              </>
            )}
          </Descriptions>
        </Card>
      ) : (
        <Alert type="info" message="暂无技术指标数据" showIcon />
      ),
    },
    {
      key: 'analysis',
      label: 'AI分析',
      children: <StockAnalysis code={codeStr} currentPrice={currentPrice} />,
    },
    {
      key: 'debate',
      label: 'AI辩论',
      children: <StockDebate code={codeStr} currentPrice={currentPrice} />,
    },
    {
      key: 'moneyflow',
      label: '资金流向',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {comprehensiveData?.money_flow && (
            <MoneyFlowPanel moneyFlow={comprehensiveData.money_flow} />
          )}
          {moneyFlowHistoryLoading ? (
            <Spin />
          ) : moneyFlowHistory && moneyFlowHistory.length > 0 ? (
            <Card title="历史资金流向（近60天）">
              <Table
                columns={moneyFlowHistoryColumns}
                dataSource={moneyFlowHistory.slice(0, 30).map((item: any, idx: number) => ({
                  ...item,
                  key: idx,
                }))}
                size="small"
                pagination={false}
                scroll={{ x: 600 }}
              />
            </Card>
          ) : null}
        </Space>
      ),
    },
    {
      key: 'risk',
      label: '风险',
      children: (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          <RiskPanel riskData={riskData} />
          <MLPredictPanel mlData={mlData} />
        </Space>
      ),
    },
    {
      key: 'fundamental',
      label: '基本面',
      children: comprehensiveData?.fundamental ? (
        <Card title="基本面数据">
          <Descriptions column={{ xs: 2, sm: 3, md: 4 }} bordered size="small">
            {comprehensiveData.fundamental.pe != null && (
              <Descriptions.Item label="市盈率(PE)">
                {comprehensiveData.fundamental.pe.toFixed(2)}
              </Descriptions.Item>
            )}
            {comprehensiveData.fundamental.pb != null && (
              <Descriptions.Item label="市净率(PB)">
                {comprehensiveData.fundamental.pb.toFixed(2)}
              </Descriptions.Item>
            )}
            {comprehensiveData.fundamental.roe != null && (
              <Descriptions.Item label="ROE">
                {comprehensiveData.fundamental.roe.toFixed(2)}%
              </Descriptions.Item>
            )}
            {comprehensiveData.fundamental.eps != null && (
              <Descriptions.Item label="EPS">
                {comprehensiveData.fundamental.eps.toFixed(2)}
              </Descriptions.Item>
            )}
          </Descriptions>
          {comprehensiveData?.industry_comparison && (
            <Card title="行业对比" size="small" style={{ marginTop: 16 }}>
              <Descriptions column={1} size="small">
                {comprehensiveData.industry_comparison.industry_name && (
                  <Descriptions.Item label="行业">
                    {comprehensiveData.industry_comparison.industry_name}
                  </Descriptions.Item>
                )}
                {comprehensiveData.industry_comparison.rank && (
                  <Descriptions.Item label="行业排名">
                    第 {comprehensiveData.industry_comparison.rank} 名
                  </Descriptions.Item>
                )}
                {comprehensiveData.industry_comparison.industry_avg_change != null && (
                  <Descriptions.Item label="行业平均涨跌幅">
                    <Text
                      style={{
                        color:
                          comprehensiveData.industry_comparison.industry_avg_change >= 0
                            ? upColor
                            : downColor,
                      }}
                    >
                      {comprehensiveData.industry_comparison.industry_avg_change >= 0
                        ? '+'
                        : ''}
                      {comprehensiveData.industry_comparison.industry_avg_change.toFixed(2)}%
                    </Text>
                  </Descriptions.Item>
                )}
              </Descriptions>
            </Card>
          )}
        </Card>
      ) : (
        <Alert type="info" message="暂无基本面数据" showIcon />
      ),
    },
    {
      key: 'sentiment',
      label: '舆情',
      children: sentimentLoading ? (
        <Spin />
      ) : sentimentData ? (
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {sentimentData.news?.list && sentimentData.news.list.length > 0 && (
            <Card title="相关新闻">
              {sentimentData.news.list.slice(0, 10).map((news: any, index: number) => (
                <div
                  key={index}
                  style={{
                    padding: '8px 0',
                    borderBottom: index < sentimentData.news.list.length - 1 ? '1px solid #f0f0f0' : 'none',
                  }}
                >
                  <a
                    href={news.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    style={{ fontWeight: 500 }}
                  >
                    {news.title}
                  </a>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {news.source} · {news.time}
                  </Text>
                </div>
              ))}
            </Card>
          )}
          {sentimentData.posts?.latest_posts && sentimentData.posts.latest_posts.length > 0 && (
            <Card title="最新帖子">
              {sentimentData.posts.latest_posts.slice(0, 10).map((post: any, index: number) => (
                <div
                  key={index}
                  style={{
                    padding: '8px 0',
                    borderBottom:
                      index < sentimentData.posts.latest_posts.length - 1
                        ? '1px solid #f0f0f0'
                        : 'none',
                  }}
                >
                  <Text strong>{post.title}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {post.author} · {post.time} · 阅读 {post.read_count}
                  </Text>
                </div>
              ))}
            </Card>
          )}
          {sentimentData.posts?.hot_posts && sentimentData.posts.hot_posts.length > 0 && (
            <Card title="热门帖子">
              {sentimentData.posts.hot_posts.slice(0, 10).map((post: any, index: number) => (
                <div
                  key={index}
                  style={{
                    padding: '8px 0',
                    borderBottom:
                      index < sentimentData.posts.hot_posts.length - 1
                        ? '1px solid #f0f0f0'
                        : 'none',
                  }}
                >
                  <Text strong>{post.title}</Text>
                  <br />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    {post.author} · {post.time} · 阅读 {post.read_count}
                  </Text>
                </div>
              ))}
            </Card>
          )}
        </Space>
      ) : null,
    },
    {
      key: 'valuation',
      label: '定量估值',
      children: <ValuationPanel stockCode={codeStr} />,
    },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <StockHeader
        name={displayData?.name}
        code={codeStr}
        currentPrice={displayData?.current_price}
        changePercent={displayData?.change_percent}
        high={displayData?.high}
        low={displayData?.low}
        open={displayData?.open}
        yesterdayClose={displayData?.yesterday_close}
        volume={displayData?.volume}
        amount={displayData?.amount}
      />

      {hasPosition && (
        <Card
          size="small"
          styles={{
            body: {
              borderLeft: '4px solid #1677ff',
              padding: 12,
            },
          }}
        >
          <Row justify="space-between" align="middle">
            <Col>
              <Space size="large">
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    持仓成本
                  </Text>
                  <br />
                  <Text strong>¥{positionCost!.toFixed(2)}</Text>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    持股数量
                  </Text>
                  <br />
                  <Text strong>{positionShares!.toLocaleString()}股</Text>
                </div>
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    持仓市值
                  </Text>
                  <br />
                  <Text strong>¥{positionValue.toFixed(2)}</Text>
                </div>
              </Space>
            </Col>
            <Col>
              <div style={{ textAlign: 'right' }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  持仓盈亏
                </Text>
                <br />
                <Statistic
                  value={positionPnl}
                  precision={2}
                  prefix={positionPnl >= 0 ? '+' : ''}
                  valueStyle={{
                    fontSize: 20,
                    fontWeight: 700,
                    color: positionPnl >= 0 ? upColor : downColor,
                  }}
                />
                <Text
                  strong
                  style={{
                    fontSize: 14,
                    color: positionPnlPercent >= 0 ? upColor : downColor,
                  }}
                >
                  {positionPnlPercent >= 0 ? '+' : ''}
                  {positionPnlPercent.toFixed(2)}%
                </Text>
              </div>
            </Col>
          </Row>
        </Card>
      )}

      <Card>
        <Tabs items={tabItems} />
      </Card>
    </Space>
  );
}
