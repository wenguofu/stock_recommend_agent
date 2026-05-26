import { useState, useEffect } from 'react';
import { Button, Card, Modal, Form, Select, Input, Space, Tag, Typography, Spin, Empty, Alert } from 'antd';
import { PlusOutlined, CaretRightOutlined, PauseOutlined, EditOutlined, DeleteOutlined, FileTextOutlined, BellOutlined } from '@ant-design/icons';
import { stockAPI } from '../services/api';

const { Title, Text } = Typography;

const SCHEDULE_OPTIONS = [
  { value: 'every_5m', label: '每5分钟' },
  { value: 'every_15m', label: '每15分钟' },
  { value: 'every_30m', label: '每30分钟' },
  { value: 'every_1h', label: '每小时' },
  { value: 'every_4h', label: '每4小时' },
];

const TASK_TYPE_OPTIONS = [
  { value: 'price_alert', label: '📊 价格提醒', desc: '监控股票涨跌幅，超过阈值时触发提醒' },
  { value: 'ai_analysis', label: '🤖 AI分析', desc: '定时运行AI多Agent分析，生成研究报告' },
];

export default function Tasks() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [alerts, setAlerts] = useState<any[]>([]);
  const [showAlerts, setShowAlerts] = useState(false);
  const [showForm, setShowForm] = useState(false);
  const [editId, setEditId] = useState<number | null>(null);
  const [logs, setLogs] = useState<Record<number, any[]>>({});
  const [expandedLog, setExpandedLog] = useState<number | null>(null);

  // 表单
  const [formName, setFormName] = useState('');
  const [formType, setFormType] = useState('price_alert');
  const [formCodes, setFormCodes] = useState('');
  const [formSchedule, setFormSchedule] = useState('every_15m');
  const [formPriceUp, setFormPriceUp] = useState('');
  const [formPriceDown, setFormPriceDown] = useState('');

  const fetchTasks = async () => {
    setLoading(true);
    try {
      const data = await stockAPI.listTasks();
      setTasks(data);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchTasks(); }, []);

  const fetchAlerts = async () => {
    const data = await stockAPI.getAlerts();
    setAlerts(data);
  };

  useEffect(() => {
    fetchAlerts();
    const interval = setInterval(fetchAlerts, 10000);
    return () => clearInterval(interval);
  }, []);

  const openCreate = () => {
    setEditId(null);
    setFormName(''); setFormType('price_alert'); setFormCodes('');
    setFormSchedule('every_15m'); setFormPriceUp(''); setFormPriceDown('');
    setShowForm(true);
  };

  const openEdit = (t: any) => {
    setEditId(t.id);
    setFormName(t.name);
    setFormType(t.task_type);
    setFormCodes((t.codes || []).join(','));
    setFormSchedule(t.schedule);
    setFormPriceUp(t.config?.price_up || '');
    setFormPriceDown(t.config?.price_down || '');
    setShowForm(true);
  };

  const handleSave = async () => {
    const codes = formCodes.split(',').map((c) => c.trim()).filter(Boolean);
    const config: any = {};
    if (formPriceUp) config.price_up = parseFloat(formPriceUp);
    if (formPriceDown) config.price_down = parseFloat(formPriceDown);

    const task = {
      name: formName || '未命名任务',
      task_type: formType,
      codes,
      schedule: formSchedule,
      config,
    };

    if (editId) {
      await stockAPI.updateTask(editId, task);
    } else {
      await stockAPI.createTask(task);
    }
    setShowForm(false);
    fetchTasks();
  };

  const handleDelete = async (id: number) => {
    if (!confirm('确认删除此任务？')) return;
    await stockAPI.deleteTask(id);
    fetchTasks();
  };

  const handleTrigger = async (id: number) => {
    await stockAPI.triggerTask(id);
    fetchTasks();
  };

  const toggleLogs = async (taskId: number) => {
    if (expandedLog === taskId) {
      setExpandedLog(null);
      return;
    }
    setExpandedLog(taskId);
    const data = await stockAPI.listTaskLogs(taskId);
    setLogs((prev) => ({ ...prev, [taskId]: data }));
  };

  const getScheduleLabel = (v: string) => SCHEDULE_OPTIONS.find((o) => o.value === v)?.label || v;
  const getTypeLabel = (v: string) => TASK_TYPE_OPTIONS.find((o) => o.value === v)?.label || v;

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 24 }}>
      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>📋 盯盘任务</Title>
        <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>
          新建任务
        </Button>
      </div>

      {/* 实时提醒面板 */}
      {alerts.length > 0 && (
        <Card
          style={{ borderColor: '#fadb14' }}
          title={
            <Space>
              <BellOutlined />
              <span>实时盯盘提醒</span>
              <Tag color="gold">{alerts.length}条</Tag>
            </Space>
          }
          extra={<a onClick={() => setShowAlerts(!showAlerts)}>{showAlerts ? '收起' : '展开'}</a>}
        >
          {showAlerts && (
            <div>
              {alerts.map((a, i) => (
                <div key={i} style={{ display: 'flex', padding: '8px 0', borderBottom: i < alerts.length - 1 ? '1px solid #f0f0f0' : 'none' }}>
                  <span style={{ fontSize: 20, marginRight: 8, color: a.type === 'price_up' ? '#ff4d4f' : '#52c41a' }}>
                    {a.type === 'price_up' ? '📈' : '📉'}
                  </span>
                  <div style={{ flex: 1 }}>
                    <div style={{ fontWeight: 500 }}>{a.message}</div>
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(a.timestamp).toLocaleString()} · 任务: {a.task_name}
                    </Text>
                  </div>
                  <Tag color={a.type === 'price_up' ? 'red' : 'green'}>
                    {a.type === 'price_up' ? '+' : ''}{a.value?.toFixed(2)}%
                  </Tag>
                </div>
              ))}
            </div>
          )}
        </Card>
      )}

      {/* 任务列表 */}
      {loading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin size="large" />
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">加载中...</Text>
          </div>
        </div>
      ) : tasks.length === 0 ? (
        <Card>
          <Empty description="暂无盯盘任务">
            <Button type="primary" onClick={openCreate}>创建第一个任务</Button>
          </Empty>
        </Card>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {tasks.map((t) => (
            <Card key={t.id} styles={{ body: { padding: 16 } }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div style={{ flex: 1 }}>
                  <div style={{ marginBottom: 4 }}>
                    <Space>
                      <Text strong>{t.name}</Text>
                      <Tag color="blue">{getTypeLabel(t.task_type)}</Tag>
                      <Tag color={t.enabled ? 'green' : 'default'}>{t.enabled ? '启用' : '停用'}</Tag>
                    </Space>
                  </div>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      📈 {(t.codes || []).join(', ')}
                    </Text>
                    <Text type="secondary" style={{ fontSize: 13 }}>
                      ⏱ {getScheduleLabel(t.schedule)}
                    </Text>
                    {t.last_run && (
                      <Text type="secondary" style={{ fontSize: 13 }}>
                        🕐 上次: {new Date(t.last_run).toLocaleString()}
                      </Text>
                    )}
                  </div>
                </div>
                <Space>
                  <Button size="small" type="primary" danger={false} style={{ background: '#52c41a', borderColor: '#52c41a' }} icon={<CaretRightOutlined />} onClick={() => handleTrigger(t.id)}>执行</Button>
                  <Button size="small" onClick={() => stockAPI.updateTask(t.id, { enabled: !t.enabled }).then(() => fetchTasks())}>
                    {t.enabled ? '暂停' : '启用'}
                  </Button>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(t)}>编辑</Button>
                  <Button size="small" danger icon={<DeleteOutlined />} onClick={() => handleDelete(t.id)}>删除</Button>
                  <Button size="small" icon={<FileTextOutlined />} onClick={() => toggleLogs(t.id)}>
                    {expandedLog === t.id ? '收起日志' : '日志'}
                  </Button>
                </Space>
              </div>
              {/* 日志展开 */}
              {expandedLog === t.id && (
                <div style={{ marginTop: 16, padding: 16, background: '#fafafa', borderRadius: 6 }}>
                  {(!logs[t.id] || logs[t.id].length === 0) ? (
                    <Text type="secondary" style={{ fontSize: 13 }}>暂无执行记录</Text>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 8, maxHeight: 240, overflow: 'auto' }}>
                      {logs[t.id].map((log: any) => (
                        <div key={log.id} style={{ display: 'flex', justifyContent: 'space-between', padding: 8, background: '#fff', borderRadius: 6, border: '1px solid #f0f0f0', fontSize: 13 }}>
                          <Tag color={log.status === 'completed' ? 'green' : 'red'}>{log.status}</Tag>
                          <Text type="secondary">{new Date(log.started_at).toLocaleString()}</Text>
                          <Text>{log.triggered_count > 0 ? `⚠ ${log.triggered_count}条提醒` : '无触发'}</Text>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </Card>
          ))}
        </div>
      )}

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editId ? '编辑任务' : '新建盯盘任务'}
        open={showForm}
        onCancel={() => setShowForm(false)}
        onOk={handleSave}
        okText={editId ? '保存修改' : '创建任务'}
        cancelText="取消"
        width={480}
      >
        <Form layout="vertical">
          <Form.Item label="任务名称">
            <Input value={formName} onChange={(e) => setFormName(e.target.value)} placeholder="如：蓝思科技盯盘" />
          </Form.Item>

          <Form.Item label="任务类型" help={TASK_TYPE_OPTIONS.find((o) => o.value === formType)?.desc}>
            <Select value={formType} onChange={setFormType} options={TASK_TYPE_OPTIONS} />
          </Form.Item>

          <Form.Item label="股票代码（多个用逗号分隔）">
            <Input value={formCodes} onChange={(e) => setFormCodes(e.target.value)} placeholder="如：300433, AAPL, SE" />
          </Form.Item>

          <Form.Item label="执行频率">
            <Select value={formSchedule} onChange={setFormSchedule} options={SCHEDULE_OPTIONS} />
          </Form.Item>

          {formType === 'price_alert' && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <Form.Item label="涨幅提醒（%）">
                <Input type="number" value={formPriceUp} onChange={(e) => setFormPriceUp(e.target.value)} placeholder="如：5" />
              </Form.Item>
              <Form.Item label="跌幅提醒（%）">
                <Input type="number" value={formPriceDown} onChange={(e) => setFormPriceDown(e.target.value)} placeholder="如：3" />
              </Form.Item>
            </div>
          )}
        </Form>
      </Modal>
    </div>
  );
}
