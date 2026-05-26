import { Card, Table, Tag, Typography, Alert, Space, Row, Col, Descriptions } from 'antd';
import { useState, useEffect } from 'react';
import { stockAPI } from '../services/api';

const { Text } = Typography;

interface StockDebateProps {
  code: string;
  currentPrice?: number;
}

export default function StockDebate({ code, currentPrice }: StockDebateProps) {
  const [latestReport, setLatestReport] = useState<string | null>(null);
  const [reportPositions, setReportPositions] = useState<{ long: string; short: string } | null>(null);

  useEffect(() => {
    if (!code) return;
    stockAPI
      .listDebateJobs('completed', 10)
      .then((jobs) => {
        const thisStockJobs = jobs.filter(
          (j: any) => j.code === code || (j.code && j.code.includes(code))
        );
        if (thisStockJobs.length > 0) {
          const latest = thisStockJobs.sort(
            (a: any, b: any) =>
              new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
          )[0];
          if (latest.report_md) {
            setLatestReport(latest.report_md);
            const longMatch = latest.report_md.match(/(?:看多|多方|乐观).*?(?:\n|$)/);
            const shortMatch = latest.report_md.match(/(?:看空|空方|悲观|建议).*?(?:\n|$)/);
            setReportPositions({
              long: longMatch
                ? latest.report_md.substring(
                    Math.max(0, longMatch.index! - 20),
                    longMatch.index! + 80
                  ).trim()
                : '',
              short: shortMatch
                ? latest.report_md.substring(
                    Math.max(0, shortMatch.index! - 20),
                    shortMatch.index! + 80
                  ).trim()
                : '',
            });
          }
        }
      })
      .catch(() => {});
  }, [code]);

  if (!latestReport) {
    return (
      <Card title="AI辩论结果">
        <Alert
          type="info"
          message="暂无AI辩论报告"
          description="当AI辩论任务完成后，您将在这里看到多空双方的分析结果和操作建议。"
          showIcon
        />
      </Card>
    );
  }

  const currentPx = currentPrice || 0;

  const extractPrice = (pattern: RegExp): number | null => {
    const m = latestReport.match(pattern);
    return m ? parseFloat(m[1]) : null;
  };

  const support1 = extractPrice(/(?:第一观察位|第一支撑|支撑位1|观察位1).*?([\d.]+)/);
  const support2 = extractPrice(/(?:第二观察位|第二支撑|支撑位2|观察位2).*?([\d.]+)/);
  const resistance1 = extractPrice(/(?:第一压力|压力位1|目标位1|目标价1|上方目标).*?([\d.]+)/);
  const resistance2 = extractPrice(/(?:第二压力|压力位2|目标位2).*?([\d.]+)/);
  const stopLossPrice = extractPrice(
    /(?:止损|止损位|止损价|跌破).*?(?:设[于在置]|为|看至|看).*?([\d.]+)/
  );
  const takeProfit1 = extractPrice(
    /(?:止盈|目标价|目标位|减仓|卖出).*?(?:设[于在置]|为|看至|看|在).*?([\d.]+)/
  );

  const isBearish =
    latestReport.includes('强烈看空') ||
    latestReport.includes('建议规避') ||
    latestReport.includes('不建议追') ||
    latestReport.includes('清仓');
  const isBullish =
    latestReport.includes('强烈看多') ||
    latestReport.includes('建议买入') ||
    latestReport.includes('推荐买入') ||
    latestReport.includes('加仓');
  const verdict = isBearish ? 'bearish' : isBullish ? 'bullish' : 'neutral';

  const calcPrice = (base: number | null, pct: number): number | null => {
    return base ? Math.round(base * (1 + pct) * 100) / 100 : null;
  };

  interface ActionItem {
    type: string;
    price: string;
    desc: string;
    color: string;
  }

  const actionList: ActionItem[] = [];

  if (verdict === 'bearish') {
    const suggestStopLoss = stopLossPrice || calcPrice(currentPx, -0.05);
    const suggestSupport1 = support1 || calcPrice(currentPx, -0.08);
    const suggestSupport2 = support2 || calcPrice(currentPx, -0.15);
    actionList.push(
      {
        type: '⚠️ 止损',
        price: suggestStopLoss ? `≤ ¥${suggestStopLoss.toFixed(2)}` : '--',
        desc: '跌破止损位应果断离场',
        color: '#cf1322',
      },
      {
        type: '📉 减仓①',
        price: suggestSupport1 ? `¥${suggestSupport1.toFixed(2)}` : '--',
        desc: '第一观察位，分批减仓',
        color: '#fa8c16',
      },
      {
        type: '📉 减仓②',
        price: suggestSupport2 ? `¥${suggestSupport2.toFixed(2)}` : '--',
        desc: '第二观察位，剩余仓位出清',
        color: '#fa8c16',
      },
      {
        type: '⏸️ 观望',
        price: currentPx ? `¥${currentPx.toFixed(2)}` : '--',
        desc: '当前不宜追高，等待回调',
        color: '#8c8c8c',
      }
    );
  } else if (verdict === 'bullish') {
    const suggestTP1 = takeProfit1 || resistance1 || calcPrice(currentPx, 0.1);
    const suggestTP2 = resistance2 || calcPrice(currentPx, 0.2);
    const suggestAdd = support1 || calcPrice(currentPx, -0.03);
    actionList.push(
      {
        type: '📈 加仓',
        price: suggestAdd ? `¥${suggestAdd.toFixed(2)}` : '--',
        desc: '回调至支撑位可加仓',
        color: '#cf1322',
      },
      {
        type: '🎯 止盈①',
        price: suggestTP1 ? `¥${suggestTP1.toFixed(2)}` : '--',
        desc: '第一目标位，减仓锁定利润',
        color: '#3f8600',
      },
      {
        type: '🎯 止盈②',
        price: suggestTP2 ? `¥${suggestTP2.toFixed(2)}` : '--',
        desc: '第二目标位，继续持有观察',
        color: '#3f8600',
      }
    );
  } else {
    const suggestTP = takeProfit1 || resistance1 || calcPrice(currentPx, 0.08);
    const suggestSL = stopLossPrice || calcPrice(currentPx, -0.05);
    actionList.push(
      {
        type: '🎯 上方',
        price: suggestTP ? `¥${suggestTP.toFixed(2)}` : '--',
        desc: '突破可看高一线',
        color: '#3f8600',
      },
      {
        type: '🛡️ 下方',
        price: suggestSL ? `¥${suggestSL.toFixed(2)}` : '--',
        desc: '跌破注意风险',
        color: '#cf1322',
      },
      {
        type: '⏸️ 观望',
        price: currentPx ? `¥${currentPx.toFixed(2)}` : '--',
        desc: '当前方向不明，建议观望',
        color: '#8c8c8c',
      }
    );
  }

  const verdictLabels: Record<string, string> = {
    bearish: '📉 偏空 / 建议减仓规避',
    bullish: '📈 偏多 / 可持股观察',
    neutral: '⚖️ 中性 / 暂时观望',
  };

  const verdictColors: Record<string, string> = {
    bearish: 'green',
    bullish: 'red',
    neutral: 'gold',
  };

  // Parse timeline table
  const timelineMatch = latestReport.match(/## 目标价与操作时间线[\s\S]*?(?=\n## |$)/);
  const timelineRows: { node: string; price: string; action: string; logic: string }[] = [];

  if (timelineMatch) {
    const tableLines = timelineMatch[0].split('\n');
    let inTable = false;
    for (const line of tableLines) {
      if (line.includes('|') && line.includes('时间节点') && line.includes('目标价'))
        inTable = true;
      else if (inTable && line.trim().startsWith('|') && !line.includes('---')) {
        const cols = line.split('|').map((c) => c.trim()).filter(Boolean);
        if (cols.length >= 4 && cols[0] !== '时间节点') {
          timelineRows.push({
            node: cols[0],
            price: cols[1],
            action: cols[2],
            logic: cols[3],
          });
        }
      }
    }
  }

  const actionTableColumns = [
    { title: '操作', dataIndex: 'type', key: 'type', width: 120, render: (_: any, r: ActionItem) => <Text strong style={{ color: r.color }}>{r.type}</Text> },
    { title: '参考价格', dataIndex: 'price', key: 'price', align: 'right' as const, width: 150, render: (_: any, r: ActionItem) => <Text strong code style={{ color: r.color }}>{r.price}</Text> },
    { title: '说明', dataIndex: 'desc', key: 'desc' },
  ];

  const timelineColumns = [
    { title: '时间', dataIndex: 'node', key: 'node', width: 100 },
    { title: '目标价', dataIndex: 'price', key: 'price', align: 'right' as const, width: 100 },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      align: 'center' as const,
      width: 100,
      render: (action: string) => {
        const act = action.replace(/[\/\s].*$/, '');
        const bgColor: Record<string, string> = {
          加仓: '#cf1322', 持仓: '#1677ff', 减仓: '#fa8c16',
          止盈: '#3f8600', 止损: '#cf1322',
        };
        return (
          <Tag color={bgColor[act] || 'default'}>{action}</Tag>
        );
      },
    },
    { title: '逻辑', dataIndex: 'logic', key: 'logic', render: (s: string) => <Text style={{ fontSize: 12 }}>{s}</Text> },
  ];

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Card
        title={
          <Space>
            <span>📋</span>
            <span>建议操作</span>
          </Space>
        }
        extra={<Text type="secondary" style={{ fontSize: 12 }}>基于最新AI分析报告</Text>}
      >
        <Tag color={verdictColors[verdict]} style={{ marginBottom: 16, padding: '4px 12px', fontSize: 14 }}>
          {verdictLabels[verdict]}
        </Tag>

        <Table
          columns={actionTableColumns}
          dataSource={actionList.map((a, i) => ({ ...a, key: i }))}
          size="small"
          pagination={false}
          style={{ marginBottom: timelineRows.length > 0 ? 16 : 0 }}
        />

        {timelineRows.length > 0 && (
          <>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>
              🎯 目标价与操作时间线
            </Text>
            <Table
              columns={timelineColumns}
              dataSource={timelineRows.map((r, i) => ({ ...r, key: i }))}
              size="small"
              pagination={false}
            />
          </>
        )}

        <Row gutter={12} style={{ marginTop: 16 }}>
          <Col xs={24} md={12}>
            <Card
              size="small"
              styles={{
                body: { background: '#fff2f0', border: '1px solid #ffccc7', borderRadius: 8 },
              }}
            >
              <Text strong style={{ color: '#cf1322', display: 'block', marginBottom: 4 }}>
                📈 多方观点
              </Text>
              <Text style={{ fontSize: 12, color: '#595959' }}>
                {reportPositions?.long
                  ? reportPositions.long.length > 80
                    ? reportPositions.long.slice(0, 80) + '...'
                    : reportPositions.long
                  : '未提取到明确看多观点'}
              </Text>
            </Card>
          </Col>
          <Col xs={24} md={12}>
            <Card
              size="small"
              styles={{
                body: { background: '#f6ffed', border: '1px solid #b7eb8f', borderRadius: 8 },
              }}
            >
              <Text strong style={{ color: '#3f8600', display: 'block', marginBottom: 4 }}>
                📉 空方观点
              </Text>
              <Text style={{ fontSize: 12, color: '#595959' }}>
                {reportPositions?.short
                  ? reportPositions.short.length > 80
                    ? reportPositions.short.slice(0, 80) + '...'
                    : reportPositions.short
                  : '未提取到明确看空观点'}
              </Text>
            </Card>
          </Col>
        </Row>

        <Alert
          type="warning"
          message={`⚠️ 价格建议由AI分析报告自动解析生成 + 基于当前价 ¥${currentPx.toFixed(2)} 计算，仅供参考，不构成投资建议`}
          banner
          style={{ marginTop: 12 }}
        />
      </Card>
    </Space>
  );
}
