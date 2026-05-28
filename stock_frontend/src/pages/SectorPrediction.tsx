import { useState, useMemo } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Card, Table, Button, Tag, Typography, Space, Spin, Row, Col, Empty, Collapse } from "antd";
import { ReloadOutlined, HistoryOutlined, CalendarOutlined } from "@ant-design/icons";
import { stockAPI } from "../services/api";

const { Title, Text } = Typography;

// 从 markdown 报告中解析出结构化数据
interface SectorPredictionItem {
  rank: number;
  name: string;
  total: number;
  scores: {
    supply_demand: number;
    cycle_position: number;
    tech_breakthrough: number;
    policy_catalyst: number;
    capital_flow: number;
    valuation_elasticity: number;
  };
  rating: string;
  gates_passed: number;
  stocks: string;
  details?: Record<string, string>;
  gate_msgs?: string[];
}

function parseMarkdownReport(report: string): { date: string; sectors: SectorPredictionItem[] } | null {
  if (!report) return null;

  // Extract date
  const dateMatch = report.match(/日期:[\s]*(\d{4}-\d{2}-\d{2})/);
  const date = dateMatch ? dateMatch[1] : "";

  const sectors: SectorPredictionItem[] = [];

  // Parse table rows: | rank | name | total | sd | cp | tb | pc | cf | ve | rating |
  const tableRegex = /\|\s*(\d+)\s*\|\s*\*\*([^*]+)\*\*\s*\|\s*\*\*(\d+)\*\*\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|/g;
  let match;
  while ((match = tableRegex.exec(report)) !== null) {
    sectors.push({
      rank: parseInt(match[1]),
      name: match[2].trim(),
      total: parseInt(match[3]),
      scores: {
        supply_demand: parseInt(match[4]),
        cycle_position: parseInt(match[5]),
        tech_breakthrough: parseInt(match[6]),
        policy_catalyst: parseInt(match[7]),
        capital_flow: parseInt(match[8]),
        valuation_elasticity: parseInt(match[9]),
      },
      rating: match[10].trim(),
      gates_passed: 0,
      stocks: "",
    });
  }

  // Parse details for each sector
  for (const sec of sectors) {
    const sectionRegex = new RegExp(
      `###\\s*[^#]*—\\s*${sec.name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}[^#]*?(?=###|##\\s*🏆|---|$)`,
      "s"
    );
    const sectionMatch = report.match(sectionRegex);
    if (sectionMatch) {
      const section = sectionMatch[0];

      // Extract scores details
      sec.details = {};
      const scoreDetailRegex = /\|\s*(供需失衡度|周期位置|技术突破|政策催化|资金信号|估值弹性)\s*\|\s*(\d+)\/10\s*\|\s*([^|]*)\s*\|/g;
      let dm;
      while ((dm = scoreDetailRegex.exec(section)) !== null) {
        const keyMap: Record<string, string> = {
          "供需失衡度": "supply_demand",
          "周期位置": "cycle_position",
          "技术突破": "tech_breakthrough",
          "政策催化": "policy_catalyst",
          "资金信号": "capital_flow",
          "估值弹性": "valuation_elasticity",
        };
        sec.details![keyMap[dm[1]]] = dm[3].trim();
      }

      // Extract gate messages
      sec.gate_msgs = [];
      const gateRegex = /-\s*(✅|❌)\s*(Gate\d\s*[^-\n]*)/g;
      let gm;
      while ((gm = gateRegex.exec(section)) !== null) {
        sec.gate_msgs.push(gm[0]);
        if (gm[1] === "✅") sec.gates_passed++;
      }

      // Extract stocks
      const stocksMatch = section.match(/\*\*领涨标的:\*\*\s*(.+)/);
      if (stocksMatch) {
        sec.stocks = stocksMatch[1].trim();
      }

      // Extract rating
      const ratingMatch = section.match(/\*\*评级:\s*(.+?)\*\*/);
      if (ratingMatch) {
        sec.rating = ratingMatch[1].trim();
      }
    }
  }

  return { date, sectors };
}

// 评分颜色
function scoreColor(s: number): string {
  if (s >= 8) return "green";
  if (s >= 6) return "gold";
  return "red";
}

function ratingColor(rating: string): string {
  if (rating.includes("S级")) return "red";
  if (rating.includes("A级")) return "orange";
  if (rating.includes("B级")) return "gold";
  return "default";
}

const FACTOR_LABELS: Record<string, string> = {
  supply_demand: "供需",
  cycle_position: "周期",
  tech_breakthrough: "技术",
  policy_catalyst: "政策",
  capital_flow: "资金",
  valuation_elasticity: "估值",
};

export default function SectorPrediction() {
  const queryClient = useQueryClient();
  const [selectedDate, setSelectedDate] = useState<string>("");
  const [selectedSector, setSelectedSector] = useState<string>("");
  const [showAll, setShowAll] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["sector-prediction", showAll ? "all" : "latest"],
    queryFn: () => stockAPI.getSectorPrediction(undefined, showAll),
    refetchInterval: 300000,
  });

  const predictionData = useMemo(() => {
    if (!data?.data) return null;
    if (showAll && Array.isArray(data.data)) {
      return data.data.map((d: any) => parseMarkdownReport(d.report)).filter(Boolean);
    }
    return [parseMarkdownReport(data.data.report)].filter(Boolean);
  }, [data, showAll]);

  const currentData = useMemo(() => {
    if (!predictionData) return null;
    if (selectedDate && Array.isArray(predictionData)) {
      return predictionData.find((d: any) => d.date === selectedDate) || predictionData[0];
    }
    return predictionData[0];
  }, [predictionData, selectedDate]);

  const selectedDetail = useMemo(() => {
    if (!currentData || !selectedSector) return null;
    return currentData.sectors.find((s: SectorPredictionItem) => s.name === selectedSector);
  }, [currentData, selectedSector]);

  if (isLoading) {
    return (
      <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}>
        <Spin size="large" />
      </div>
    );
  }

  if (isError || !currentData) {
    return (
      <div style={{ textAlign: "center", padding: "80px 0" }}>
        <Empty description="暂无主线预判数据">
          <Text type="secondary">请先导入九大板块数据后运行预判引擎</Text>
        </Empty>
      </div>
    );
  }

  // Build table columns
  const factorColumns = Object.keys(FACTOR_LABELS).map((key) => ({
    title: FACTOR_LABELS[key],
    dataIndex: ["scores", key],
    key: key,
    width: 60,
    align: "center" as const,
    render: (val: number) => (
      <Text strong style={{ color: scoreColor(val) === "green" ? "#52c41a" : scoreColor(val) === "gold" ? "#faad14" : "#ff4d4f" }}>
        {val}
      </Text>
    ),
  }));

  const columns = [
    {
      title: "#",
      dataIndex: "rank",
      key: "rank",
      width: 50,
      render: (val: number) => <Text type="secondary">{val}</Text>,
    },
    {
      title: "板块",
      dataIndex: "name",
      key: "name",
      render: (val: string) => <Text strong>{val}</Text>,
    },
    {
      title: "总分",
      dataIndex: "total",
      key: "total",
      width: 80,
      align: "right" as const,
      render: (val: number) => (
        <Text strong code style={{ color: val >= 65 ? "#52c41a" : val >= 50 ? "#faad14" : undefined }}>
          {val}
        </Text>
      ),
    },
    ...factorColumns,
    {
      title: "关卡",
      dataIndex: "gates_passed",
      key: "gates_passed",
      width: 70,
      align: "center" as const,
      render: (val: number) => (
        <Text style={{ color: val >= 3 ? "#52c41a" : val >= 2 ? "#faad14" : undefined }}>
          {val}/4
        </Text>
      ),
    },
    {
      title: "评级",
      dataIndex: "rating",
      key: "rating",
      width: 80,
      render: (val: string) => (
        <Tag color={ratingColor(val)}>{val.slice(0, 2)}</Tag>
      ),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: "100%" }}>
      {/* 头部 */}
      <Row justify="space-between" align="middle">
        <Col>
          <Title level={2} style={{ margin: 0 }}>🔮 主线预判</Title>
          <Text type="secondary">基于六因子+四关卡模型，预判下一个主线板块</Text>
        </Col>
        <Col>
          <Space>
            <Button
              type={showAll ? "primary" : "default"}
              icon={<HistoryOutlined />}
              onClick={() => setShowAll(!showAll)}
            >
              {showAll ? "收起" : "查看历史"}
            </Button>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => queryClient.invalidateQueries({ queryKey: ["sector-prediction"] })}
            >
              刷新
            </Button>
          </Space>
        </Col>
      </Row>

      {/* 历史日期选择 */}
      {showAll && Array.isArray(predictionData) && predictionData.length > 1 && (
        <Space wrap>
          {predictionData.map((d: any) => (
            <Button
              key={d.date}
              size="small"
              type={(selectedDate || predictionData[0].date) === d.date ? "primary" : "default"}
              icon={<CalendarOutlined />}
              onClick={() => setSelectedDate(d.date)}
            >
              {d.date.slice(5)}
            </Button>
          ))}
        </Space>
      )}

      {/* 当前日期 */}
      <Text type="secondary">
        📅 {currentData.date} · {currentData.sectors.length} 个板块
      </Text>

      {/* 评分汇总表 */}
      <Card bodyStyle={{ padding: 0 }}>
        <Table
          columns={columns}
          dataSource={currentData.sectors}
          rowKey="name"
          pagination={false}
          size="small"
          scroll={{ x: 700 }}
          onRow={(record) => ({
            onClick: () => setSelectedSector(record.name),
            style: {
              cursor: "pointer",
              background: selectedSector === record.name ? "#e6f7ff" : undefined,
            },
          })}
        />
      </Card>

      {/* 详情面板 */}
      {selectedDetail && (
        <Card
          title={
            <Space>
              <Text strong style={{ fontSize: 16 }}>{selectedDetail.name}</Text>
              <Text type="secondary">· 综合评分 {selectedDetail.total}</Text>
            </Space>
          }
          extra={
            <Tag color={ratingColor(selectedDetail.rating)}>{selectedDetail.rating}</Tag>
          }
        >
          {/* 六因子详情 */}
          <Row gutter={[12, 12]} style={{ marginBottom: 16 }}>
            {Object.entries(FACTOR_LABELS).map(([key, label]) => (
              <Col xs={12} md={8} key={key}>
                <Card size="small">
                  <Row justify="space-between" align="middle" style={{ marginBottom: 4 }}>
                    <Text type="secondary" style={{ fontSize: 12 }}>{label}</Text>
                    <Text strong style={{ fontSize: 18, color: scoreColor((selectedDetail.scores as any)[key]) === "green" ? "#52c41a" : scoreColor((selectedDetail.scores as any)[key]) === "gold" ? "#faad14" : "#ff4d4f" }}>
                      {(selectedDetail.scores as any)[key]}
                      <Text type="secondary" style={{ fontSize: 12 }}>/10</Text>
                    </Text>
                  </Row>
                  {selectedDetail.details?.[key] && (
                    <Text type="secondary" style={{ fontSize: 12 }}>{selectedDetail.details[key]}</Text>
                  )}
                </Card>
              </Col>
            ))}
          </Row>

          {/* 验证关卡 */}
          {selectedDetail.gate_msgs && selectedDetail.gate_msgs.length > 0 && (
            <div style={{ marginBottom: 12 }}>
              <Text strong style={{ fontSize: 13, display: "block", marginBottom: 8 }}>
                验证关卡 (通过 {selectedDetail.gates_passed}/4)
              </Text>
              <Space direction="vertical" size={4} style={{ width: "100%" }}>
                {selectedDetail.gate_msgs.map((gm: string, i: number) => (
                  <Tag
                    key={i}
                    color={gm.includes("✅") ? "success" : "error"}
                    style={{ padding: "4px 12px", fontSize: 12 }}
                  >
                    {gm}
                  </Tag>
                ))}
              </Space>
            </div>
          )}

          {/* 领涨标的 */}
          {selectedDetail.stocks && (
            <Text type="secondary" style={{ fontSize: 13 }}>
              <Text strong>领涨标的:</Text> {selectedDetail.stocks}
            </Text>
          )}
        </Card>
      )}
    </Space>
  );
}
