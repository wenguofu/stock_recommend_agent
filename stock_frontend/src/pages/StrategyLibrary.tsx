import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';
import type { StrategySummary, StrategyDetail } from '../services/api';
import { Link, useNavigate } from 'react-router-dom';
import {
  Card,
  Button,
  Space,
  Typography,
  Spin,
  Alert,
  Empty,
  Tag,
  Collapse,
  Result,
  Divider,
} from 'antd';
import {
  ReloadOutlined,
  ThunderboltOutlined,
  CaretRightOutlined,
  PlayCircleOutlined,
  BookOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
} from '@ant-design/icons';

const { Title, Paragraph, Text } = Typography;

const CATEGORIES = [
  { value: '', label: '全部策略', icon: '📚' },
  { value: 'youzi', label: '游资策略', icon: '🐉' },
  { value: 'jichang', label: '基础工具', icon: '🔧' },
  { value: 'lianghua', label: '量化策略', icon: '📊' },
  { value: 'zisuye', label: '紫苏叶', icon: '🍃' },
];

const CATEGORY_LABELS: Record<string, string> = {
  youzi: '游资策略',
  jichang: '基础工具',
  lianghua: '量化策略',
  zisuye: '紫苏叶',
};

const CATEGORY_COLORS: Record<string, string> = {
  youzi: 'red',
  jichang: 'blue',
  lianghua: 'green',
  zisuye: 'purple',
};

export default function StrategyLibrary() {
  const [selectedCategory, setSelectedCategory] = useState('');
  const [selectedStrategy, setSelectedStrategy] = useState<StrategyDetail | null>(null);
  const [applying, setApplying] = useState(false);
  const [applyResult, setApplyResult] = useState<{ message: string; count: number } | null>(null);
  const [expandedDoc, setExpandedDoc] = useState(false);
  const navigate = useNavigate();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ['strategies', selectedCategory],
    queryFn: () => stockAPI.getStrategies(selectedCategory || undefined),
  });

  const handleSelect = async (id: number) => {
    try {
      const detail = await stockAPI.getStrategyDetail(id);
      setSelectedStrategy(detail);
      setExpandedDoc(false);
      setApplyResult(null);
    } catch (e) {
      console.error('获取策略详情失败:', e);
    }
  };

  const handleApply = async () => {
    if (!selectedStrategy) return;
    setApplying(true);
    try {
      const result = await stockAPI.applyStrategy(selectedStrategy.id);
      setApplyResult({ message: result.message, count: result.count });
    } catch (e) {
      console.error('应用策略失败:', e);
      setApplyResult({ message: '应用失败', count: 0 });
    } finally {
      setApplying(false);
    }
  };

  // Render markdown doc
  const renderDoc = (docMd: string) => {
    return docMd.split('\n').map((line, i) => {
      if (line.startsWith('# ')) return <Title key={i} level={1} style={{ marginTop: 16, marginBottom: 8 }}>{line.slice(2)}</Title>;
      if (line.startsWith('## ')) return <Title key={i} level={2} style={{ marginTop: 16, marginBottom: 8 }}>{line.slice(3)}</Title>;
      if (line.startsWith('### ')) return <Title key={i} level={3} style={{ marginTop: 12, marginBottom: 4 }}>{line.slice(4)}</Title>;
      if (line.startsWith('| ')) return <div key={i} style={{ fontFamily: 'monospace', fontSize: 12, padding: '2px 0' }}>{line}</div>;
      if (line.startsWith('> ')) return (
        <blockquote key={i} style={{ borderLeft: '4px solid #1677ff', paddingLeft: 16, fontStyle: 'italic', margin: '8px 0' }}>
          {line.slice(2)}
        </blockquote>
      );
      if (line.startsWith('- ')) return <li key={i} style={{ marginLeft: 16, listStyle: 'disc', fontSize: 14 }}>{line.slice(2)}</li>;
      if (line.startsWith('---')) return <Divider key={i} style={{ margin: '16px 0' }} />;
      if (line.trim() === '') return <div key={i} style={{ height: 8 }} />;
      return <Paragraph key={i} style={{ fontSize: 14, lineHeight: 1.8, marginBottom: 4 }}>{line}</Paragraph>;
    });
  };

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Title level={2} style={{ margin: 0 }}>策略库</Title>
          <Paragraph type="secondary" style={{ marginTop: 4, marginBottom: 0 }}>
            浏览、选择并应用量化交易策略
          </Paragraph>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
      </div>

      {/* Category filter */}
      <Space wrap>
        {CATEGORIES.map((cat) => (
          <Button
            key={cat.value}
            type={selectedCategory === cat.value ? 'primary' : 'default'}
            shape="round"
            onClick={() => {
              setSelectedCategory(cat.value);
              setSelectedStrategy(null);
              setApplyResult(null);
            }}
          >
            <span style={{ marginRight: 4 }}>{cat.icon}</span>
            {cat.label}
          </Button>
        ))}
      </Space>

      {/* Content */}
      {isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
          <Paragraph type="secondary" style={{ marginTop: 16 }}>加载策略...</Paragraph>
        </div>
      ) : error ? (
        <Alert
          type="error"
          message="加载失败"
          action={
            <Button size="small" danger onClick={() => refetch()}>重试</Button>
          }
          style={{ marginTop: 16 }}
        />
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: 24 }}>
          {/* Strategy list */}
          <div>
            {!data?.strategies.length ? (
              <Empty description="暂无策略" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }} size="middle">
                {data.strategies.map((s) => (
                  <Card
                    key={s.id}
                    hoverable
                    size="small"
                    onClick={() => handleSelect(s.id)}
                    style={{
                      borderColor: selectedStrategy?.id === s.id ? '#1677ff' : undefined,
                      backgroundColor: selectedStrategy?.id === s.id ? '#e6f4ff' : undefined,
                    }}
                    title={
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                        <Text strong ellipsis style={{ maxWidth: 200 }}>{s.name}</Text>
                        <Space size={4}>
                          <Button
                            type="text"
                            size="small"
                            icon={<PlayCircleOutlined />}
                            style={{ color: '#52c41a' }}
                            onClick={(e) => { e.stopPropagation(); navigate(`/strategies/${s.id}/run`); }}
                            title="立即运行"
                          />
                          <Tag color="blue">{s.agent_count}个Agent</Tag>
                        </Space>
                      </div>
                    }
                  >
                    {s.category && (
                      <Tag color={CATEGORY_COLORS[s.category] || 'default'} style={{ marginBottom: 8 }}>
                        {CATEGORY_LABELS[s.category] || s.category}
                      </Tag>
                    )}
                    {s.description && (
                      <Paragraph
                        type="secondary"
                        ellipsis={{ rows: 2 }}
                        style={{ marginBottom: 0, fontSize: 13 }}
                      >
                        {s.description}
                      </Paragraph>
                    )}
                  </Card>
                ))}
              </Space>
            )}
          </div>

          {/* Strategy detail */}
          <div>
            {selectedStrategy ? (
              <Card
                title={
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 12 }}>
                    <div>
                      <Title level={4} style={{ margin: 0 }}>{selectedStrategy.name}</Title>
                      {selectedStrategy.description && (
                        <Paragraph type="secondary" style={{ marginTop: 8, marginBottom: 0 }}>
                          {selectedStrategy.description}
                        </Paragraph>
                      )}
                    </div>
                    <Space>
                      <Button
                        type="primary"
                        icon={applying ? undefined : <ThunderboltOutlined />}
                        loading={applying}
                        onClick={handleApply}
                      >
                        {applying ? '应用中...' : '应用配置'}
                      </Button>
                      <Button
                        icon={<PlayCircleOutlined />}
                        style={{ backgroundColor: '#52c41a', borderColor: '#52c41a', color: '#fff' }}
                        onClick={() => navigate(`/strategies/${selectedStrategy.id}/run`)}
                      >
                        立即运行
                      </Button>
                    </Space>
                  </div>
                }
              >
                {/* Apply result */}
                {applyResult && (
                  <Alert
                    type={applyResult.count > 0 ? 'success' : 'error'}
                    message={
                      applyResult.count > 0
                        ? `策略应用成功！已创建/更新 ${applyResult.count} 个Agent。可到"设置"页面查看。`
                        : '策略应用失败'
                    }
                    icon={applyResult.count > 0 ? <CheckCircleOutlined /> : <CloseCircleOutlined />}
                    style={{ marginBottom: 16 }}
                    showIcon
                  />
                )}

                {/* Agent configs */}
                <Title level={5} style={{ marginTop: 0, marginBottom: 16 }}>
                  包含的Agent ({selectedStrategy.agent_configs.length}个)
                </Title>
                <Collapse
                  expandIconPosition="end"
                  items={selectedStrategy.agent_configs.map((agent, idx) => ({
                    key: String(idx),
                    label: (
                      <Space>
                        <Tag color="blue" style={{ borderRadius: '50%', width: 28, height: 28, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', padding: 0 }}>
                          {idx + 1}
                        </Tag>
                        <Text strong>{agent.name}</Text>
                        <Tag>{agent.type}</Tag>
                      </Space>
                    ),
                    children: (
                      <pre style={{
                        whiteSpace: 'pre-wrap',
                        fontFamily: 'monospace',
                        fontSize: 13,
                        background: '#fafafa',
                        padding: 16,
                        borderRadius: 8,
                        maxHeight: 320,
                        overflowY: 'auto',
                        margin: 0,
                      }}>
                        {agent.prompt}
                      </pre>
                    ),
                  }))}
                />

                {/* Doc */}
                {selectedStrategy.doc_md && (
                  <>
                    <Divider style={{ margin: '24px 0 16px' }} />
                    <Button
                      type="text"
                      icon={<BookOutlined rotate={expandedDoc ? 90 : 0} />}
                      onClick={() => setExpandedDoc(!expandedDoc)}
                      style={{ padding: 0, fontSize: 16, fontWeight: 600, marginBottom: 12 }}
                    >
                      策略说明文档
                    </Button>
                    {expandedDoc && (
                      <div style={{
                        background: '#fafafa',
                        padding: 24,
                        borderRadius: 8,
                        fontSize: 14,
                      }}>
                        {renderDoc(selectedStrategy.doc_md)}
                      </div>
                    )}
                  </>
                )}
              </Card>
            ) : (
              <Card>
                <Empty
                  image={<BookOutlined style={{ fontSize: 64, color: '#d9d9d9' }} />}
                  description={
                    <>
                      <Title level={4}>选择一个策略</Title>
                      <Paragraph type="secondary">
                        从左侧选择一个策略，查看其包含的Agent配置和说明文档
                      </Paragraph>
                    </>
                  }
                >
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, maxWidth: 480, margin: '0 auto' }}>
                    <Card size="small" style={{ borderColor: '#ffa39e', background: '#fff2f0' }}>
                      <div style={{ fontSize: 24, marginBottom: 4 }}>🐉</div>
                      <Text strong style={{ fontSize: 13 }}>游资策略</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>短线追涨打板</Text>
                    </Card>
                    <Card size="small" style={{ borderColor: '#91caff', background: '#e6f4ff' }}>
                      <div style={{ fontSize: 24, marginBottom: 4 }}>🔧</div>
                      <Text strong style={{ fontSize: 13 }}>基础工具</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>盯盘监控分析</Text>
                    </Card>
                    <Card size="small" style={{ borderColor: '#b7eb8f', background: '#f6ffed' }}>
                      <div style={{ fontSize: 24, marginBottom: 4 }}>📊</div>
                      <Text strong style={{ fontSize: 13 }}>量化策略</Text>
                      <br />
                      <Text type="secondary" style={{ fontSize: 11 }}>多因子评分</Text>
                    </Card>
                  </div>
                </Empty>
              </Card>
            )}
          </div>
        </div>
      )}
    </Space>
  );
}
