import { useEffect, useRef, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { stockAPI } from '../services/api';
import type { Agent } from '../services/api';
import { Button, Modal, Checkbox, Space, Typography, Radio, Alert, Card } from 'antd';
import { BulbOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

interface AIAnalyzeButtonProps {
  code: string;
  className?: string;
}

export default function AIAnalyzeButton({ code, className = '' }: AIAnalyzeButtonProps) {
  const [showModal, setShowModal] = useState(false);
  const [selectedAgentIds, setSelectedAgentIds] = useState<number[]>([]);
  const [mode, setMode] = useState<'fast' | 'balanced' | 'deep'>('fast');
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();
  const prevShowModalRef = useRef(false);

  const { data: agents, isLoading: agentsLoading } = useQuery({
    queryKey: ['agents', 'enabled'],
    queryFn: () => stockAPI.getAgents(true),
  });

  useEffect(() => {
    if (showModal && !prevShowModalRef.current && agents && agents.length > 0) {
      setSelectedAgentIds(agents.map((agent) => agent.id));
    }
    prevShowModalRef.current = showModal;
  }, [showModal, agents]);

  const toggleAgent = (agentId: number) => {
    setSelectedAgentIds((prev) =>
      prev.includes(agentId) ? prev.filter((id) => id !== agentId) : [...prev, agentId]
    );
  };

  const handleStartDebate = () => {
    if (selectedAgentIds.length < 2) {
      setError('至少选择2个Agent参与辩论');
      return;
    }

    setError(null);
    setShowModal(false);
    const modeConfig = {
      fast: { analysisRounds: 1, debateRounds: 1, label: '快速模式' },
      balanced: { analysisRounds: 2, debateRounds: 1, label: '均衡模式' },
      deep: { analysisRounds: 3, debateRounds: 2, label: '深入模式' },
    }[mode];
    navigate(`/ai-debate?code=${code}&ar=${modeConfig.analysisRounds}&dr=${modeConfig.debateRounds}`, {
      state: {
        code,
        agentIds: selectedAgentIds,
        analysisRounds: modeConfig.analysisRounds,
        debateRounds: modeConfig.debateRounds,
        modeLabel: modeConfig.label,
      },
    });
  };

  return (
    <>
      <Button
        type="primary"
        onClick={() => setShowModal(true)}
        icon={<BulbOutlined />}
        style={{ background: 'linear-gradient(135deg, #7b1fa2, #9c27b0)', border: 'none' }}
        className={className}
      >
        TradingAgents AI分析
      </Button>

      <Modal
        title="TradingAgents 多Agent辩论"
        open={showModal}
        onCancel={() => {
          setShowModal(false);
          setError(null);
        }}
        footer={null}
        width={600}
        destroyOnClose
      >
        <Space direction="vertical" size="middle" style={{ width: '100%' }}>
          {/* 模式选择 */}
          <div>
            <Text strong style={{ display: 'block', marginBottom: 8 }}>选择模式</Text>
            <Radio.Group
              value={mode}
              onChange={e => setMode(e.target.value)}
              style={{ width: '100%' }}
            >
              <Space direction="vertical" style={{ width: '100%' }}>
                <Radio.Button value="fast" style={{ width: '100%', height: 'auto', padding: '8px 12px' }}>
                  <div>快速模式</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>思考1 / 辩论1</Text>
                </Radio.Button>
                <Radio.Button value="balanced" style={{ width: '100%', height: 'auto', padding: '8px 12px' }}>
                  <div>均衡模式</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>思考2 / 辩论1</Text>
                </Radio.Button>
                <Radio.Button value="deep" style={{ width: '100%', height: 'auto', padding: '8px 12px' }}>
                  <div>深入模式</div>
                  <Text type="secondary" style={{ fontSize: 12 }}>思考3 / 辩论2</Text>
                </Radio.Button>
              </Space>
            </Radio.Group>
          </div>

          {/* Agent选择 */}
          <div>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
              <Text strong>选择参与辩论的Agent（至少2个）</Text>
              {agents && agents.length > 0 && (
                <Space size={4}>
                  <Button size="small" onClick={() => setSelectedAgentIds(agents.map((agent) => agent.id))}>
                    全选
                  </Button>
                  <Button size="small" onClick={() => setSelectedAgentIds([])}>
                    清空
                  </Button>
                </Space>
              )}
            </div>
            {agentsLoading ? (
              <Text type="secondary">加载中...</Text>
            ) : agents && agents.length > 0 ? (
              <Checkbox.Group
                value={selectedAgentIds}
                onChange={values => setSelectedAgentIds(values as number[])}
                style={{ width: '100%' }}
              >
                <Space direction="vertical" style={{ width: '100%' }}>
                  {agents.map((agent: Agent) => (
                    <Checkbox key={agent.id} value={agent.id}>
                      {agent.name} ({agent.type})
                    </Checkbox>
                  ))}
                </Space>
              </Checkbox.Group>
            ) : (
              <Text type="secondary">暂无启用的Agent，请先在配置页面添加</Text>
            )}
          </div>

          {/* 错误提示 */}
          {error && (
            <Alert message={error} type="error" showIcon closable onClose={() => setError(null)} />
          )}

          {/* 进入辩论 */}
          <Button
            type="primary"
            block
            onClick={handleStartDebate}
            disabled={selectedAgentIds.length < 2}
            style={{ background: 'linear-gradient(135deg, #7b1fa2, #9c27b0)', border: 'none' }}
          >
            进入辩论
          </Button>
        </Space>
      </Modal>
    </>
  );
}
