import { useState, useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Form, Input, Select, Button, Typography, Space, Spin, message, Alert, Modal, Tag } from 'antd';
import { SettingOutlined, ApiOutlined, RobotOutlined, KeyOutlined, PlayCircleOutlined, SaveOutlined, EditOutlined, ReloadOutlined } from '@ant-design/icons';
import { stockAPI } from '../services/api';
import type { Agent } from '../services/api';

const { Title, Text } = Typography;

const AI_PROVIDERS = [
  { value: 'openai', label: 'OpenAI' },
  { value: 'deepseek', label: 'DeepSeek' },
  { value: 'qwen', label: '通义千问' },
  { value: 'gemini', label: 'Google Gemini' },
  { value: 'siliconflow', label: '硅基流动' },
  { value: 'grok', label: 'xAI Grok' },
];

export default function Settings() {
  const [apiBaseURL, setApiBaseURL] = useState('http://127.0.0.1:35000');
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const [apiKey, setApiKey] = useState('');
  const [selectedModel, setSelectedModel] = useState('');
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);

  // 加载配置
  useEffect(() => {
    loadConfig();
  }, []);

  const loadConfig = async () => {
    try {
      const url = await stockAPI.getConfig('api_base_url');
      if (url) setApiBaseURL(url);

      const provider = await stockAPI.getConfig('default_ai_provider');
      if (provider) {
        setSelectedProvider(provider);
        const key = await stockAPI.getConfig(`${provider}_api_key`);
        if (key) setApiKey(key);
        const model = await stockAPI.getConfig(`${provider}_model`);
        if (model) setSelectedModel(model);
      }
    } catch (error) {
      console.error('加载配置失败:', error);
    }
  };

  // 当provider改变时，加载对应的key和模型
  useEffect(() => {
    const loadProviderConfig = async () => {
      try {
        const key = await stockAPI.getConfig(`${selectedProvider}_api_key`);
        setApiKey(key || '');
        const model = await stockAPI.getConfig(`${selectedProvider}_model`);
        setSelectedModel(model || '');
      } catch (error) {
        console.error('加载provider配置失败:', error);
      }
    };
    loadProviderConfig();
  }, [selectedProvider]);

  // 获取模型列表
  const { data: models, isLoading: modelsLoading, refetch: refetchModels } = useQuery({
    queryKey: ['ai-models', selectedProvider, apiKey],
    queryFn: () => stockAPI.getAIModels(selectedProvider, apiKey || undefined),
    enabled: !!selectedProvider && !!apiKey,
  });

  const handleSave = async () => {
    setSaving(true);
    try {
      await stockAPI.setConfig('api_base_url', apiBaseURL);
      stockAPI.setBaseURL(apiBaseURL);
      await stockAPI.setConfig('default_ai_provider', selectedProvider);
      await stockAPI.setConfig(`${selectedProvider}_api_key`, apiKey);
      if (selectedModel) {
        await stockAPI.setConfig(`${selectedProvider}_model`, selectedModel);
      }
      message.success('配置保存成功！');
    } catch (error) {
      message.error(`保存失败: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  const handleTest = async () => {
    if (!apiKey) {
      setTestResult({ success: false, message: '请先输入API Key' });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const result = await stockAPI.testAIConnection(
        selectedProvider,
        apiKey,
        selectedModel || undefined
      );
      setTestResult(result);
      if (result.success) {
        refetchModels();
      }
    } catch (error) {
      setTestResult({
        success: false,
        message: `测试失败: ${(error as Error).message}`,
      });
    } finally {
      setTesting(false);
    }
  };

  const providerLabel = AI_PROVIDERS.find(p => p.value === selectedProvider)?.label || selectedProvider;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Title level={2}>系统配置</Title>

      {/* 后端地址配置 */}
      <Card title={<><ApiOutlined /> 后端地址</>}>
        <Form layout="vertical">
          <Form.Item label="API基础地址">
            <Input
              value={apiBaseURL}
              onChange={(e) => setApiBaseURL(e.target.value)}
              placeholder="http://127.0.0.1:35000"
            />
          </Form.Item>
        </Form>
      </Card>

      {/* AI服务配置 */}
      <Card title={<><RobotOutlined /> AI服务配置</>}>
        <Form layout="vertical">
          <Form.Item label="AI服务商">
            <Select
              value={selectedProvider}
              onChange={(value) => {
                setSelectedProvider(value);
                setApiKey('');
                setSelectedModel('');
              }}
              options={AI_PROVIDERS}
            />
          </Form.Item>

          <Form.Item label="API Key">
            <Space.Compact style={{ width: '100%' }}>
              <Input.Password
                value={apiKey}
                onChange={(e) => {
                  setApiKey(e.target.value);
                  setSelectedModel('');
                }}
                placeholder={`输入${providerLabel}的API Key`}
                style={{ flex: 1 }}
              />
              <Button
                type="primary"
                style={{ background: '#52c41a', borderColor: '#52c41a' }}
                icon={<PlayCircleOutlined />}
                onClick={handleTest}
                loading={testing}
                disabled={!apiKey}
              >
                测试连接
              </Button>
              <Button
                icon={<SaveOutlined />}
                onClick={handleSave}
                loading={saving}
                disabled={!apiKey}
              >
                保存AI配置
              </Button>
            </Space.Compact>
            {testResult && (
              <Alert
                style={{ marginTop: 8 }}
                type={testResult.success ? 'success' : 'error'}
                message={testResult.message}
                showIcon
              />
            )}
          </Form.Item>

          <Form.Item label="模型选择">
            {modelsLoading ? (
              <Spin tip="加载模型中..." />
            ) : models && models.length > 0 ? (
              <Space.Compact style={{ width: '100%' }}>
                <Select
                  value={selectedModel || undefined}
                  onChange={(value) => setSelectedModel(value)}
                  placeholder="请选择模型"
                  options={models.map((m: string) => ({ value: m, label: m }))}
                  style={{ flex: 1 }}
                  allowClear
                />
                <Button
                  icon={<ReloadOutlined />}
                  onClick={() => refetchModels()}
                  disabled={!apiKey}
                >
                  刷新模型
                </Button>
              </Space.Compact>
            ) : (
              <Text type="secondary">请先输入API Key并测试连接以加载模型列表</Text>
            )}
          </Form.Item>
        </Form>
      </Card>

      {/* Agent配置 */}
      <AgentConfigSection />

      {/* 底部保存按钮 */}
      <div style={{ textAlign: 'right' }}>
        <Button
          type="primary"
          size="large"
          icon={<SaveOutlined />}
          onClick={handleSave}
          loading={saving}
        >
          保存配置
        </Button>
      </div>
    </Space>
  );
}

// Agent配置组件
function AgentConfigSection() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingAgent, setEditingAgent] = useState<Agent | null>(null);
  const [prompt, setPrompt] = useState('');

  useEffect(() => {
    loadAgents();
  }, []);

  const loadAgents = async () => {
    try {
      setLoading(true);
      const data = await stockAPI.getAgents(false);
      setAgents(data);
    } catch (error) {
      console.error('加载Agents失败:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (agent: Agent) => {
    setEditingAgent(agent);
    setPrompt(agent.prompt);
  };

  const handleSavePrompt = async () => {
    if (!editingAgent) return;
    try {
      await stockAPI.updateAgent(editingAgent.id, { prompt });
      setEditingAgent(null);
      setPrompt('');
      loadAgents();
      message.success('提示词保存成功');
    } catch (error) {
      message.error(`保存失败: ${(error as Error).message}`);
    }
  };

  if (loading) {
    return (
      <Card title="Agent配置">
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <Spin />
        </div>
      </Card>
    );
  }

  return (
    <Card title="Agent配置">
      <Space direction="vertical" size="middle" style={{ width: '100%' }}>
        {agents.map((agent) => (
          <Card
            key={agent.id}
            size="small"
            type="inner"
            title={
              <Space>
                <Text strong>{agent.name}</Text>
                <Tag>{agent.type}</Tag>
                {agent.enabled ? <Tag color="green">启用</Tag> : <Tag color="default">禁用</Tag>}
              </Space>
            }
            extra={
              <Button
                size="small"
                type="primary"
                icon={<EditOutlined />}
                onClick={() => handleEdit(agent)}
              >
                编辑提示词
              </Button>
            }
          >
            {editingAgent?.id === agent.id ? (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Input.TextArea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  rows={8}
                  placeholder="输入Agent提示词..."
                  style={{ fontFamily: 'monospace' }}
                />
                <Space>
                  <Button
                    type="primary"
                    style={{ background: '#52c41a', borderColor: '#52c41a' }}
                    onClick={handleSavePrompt}
                  >
                    保存
                  </Button>
                  <Button
                    onClick={() => {
                      setEditingAgent(null);
                      setPrompt('');
                    }}
                  >
                    取消
                  </Button>
                </Space>
              </Space>
            ) : (
              <Text
                type="secondary"
                style={{
                  whiteSpace: 'pre-wrap',
                  fontFamily: 'monospace',
                  display: 'block',
                  background: 'rgba(0,0,0,0.02)',
                  padding: 12,
                  borderRadius: 4,
                }}
              >
                {agent.prompt.substring(0, 200)}
                {agent.prompt.length > 200 && '...'}
              </Text>
            )}
          </Card>
        ))}
      </Space>
    </Card>
  );
}
