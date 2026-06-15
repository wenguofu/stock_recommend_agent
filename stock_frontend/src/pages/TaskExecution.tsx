import { useState } from 'react';
import { Card, Tabs, Button, Tag, Space, Typography, Empty, Spin, Alert } from 'antd';
import { ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { stockAPI } from '../services/api';

const { Title, Text } = Typography;

function formatDuration(ms: number | null | undefined): string {
  if (ms == null) return '';
  if (ms < 1000) return `${ms}ms`;
  const sec = Math.floor(ms / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  return `${min}m${s.toString().padStart(2, '0')}s`;
}

const STATUS_COLOR: Record<string, string> = {
  running: 'green',
  completed: 'blue',
  failed: 'red',
  pending: 'default',
};

const STATUS_LABEL: Record<string, string> = {
  running: '执行中',
  completed: '已完成',
  failed: '失败',
  pending: '待执行',
};

export default function TaskExecution() {
  const [tick, setTick] = useState(0);
  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['scheduler-status', tick],
    queryFn: () => stockAPI.schedulerStatus(),
  });
  const { data: userTasks, isLoading: tasksLoading } = useQuery({
    queryKey: ['user-tasks', tick],
    queryFn: () => stockAPI.listTasks(),
  });

  const handleRefresh = () => setTick((t) => t + 1);

  const tasks: any[] = (statusData?.tasks as any[]) || [];
  const running = tasks.filter((t) => t.status === 'running').length;
  const failed = tasks.filter((t) => t.status === 'failed').length;

  const schedulerTab = (
    <div data-testid="scheduler-tab">
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <Text>
            执行中: <Tag color="green">{running}</Tag>
          </Text>
          <Text>
            失败: <Tag color="red">{failed}</Tag>
          </Text>
          <Text>
            总数: <Tag color="blue">{tasks.length}</Tag>
          </Text>
        </Space>
      </Card>
      {statusLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin />
        </div>
      ) : tasks.length === 0 ? (
        <Empty description="暂无调度任务" />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {tasks.map((t) => (
            <Card key={t.id ?? t.task_name} size="small">
              <Space style={{ marginBottom: 8 }} wrap>
                {t.status === 'running' ? (
                  <Tag color="green" icon={<PlayCircleOutlined />}>
                    {STATUS_LABEL[t.status] || t.status}
                  </Tag>
                ) : t.status === 'failed' ? (
                  <Tag color="red" icon={<PauseCircleOutlined />}>
                    {STATUS_LABEL[t.status] || t.status}
                  </Tag>
                ) : (
                  <Tag color={STATUS_COLOR[t.status] || 'default'}>
                    {STATUS_LABEL[t.status] || t.status}
                  </Tag>
                )}
                <Text strong>{t.task_name}</Text>
                {t.task_type && <Tag color="blue">{t.task_type}</Tag>}
                {t.schedule && <Tag>{t.schedule}</Tag>}
                {t.duration_ms != null && <Tag color="cyan">{formatDuration(t.duration_ms)}</Tag>}
              </Space>
              {t.started_at && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    上次运行: {t.started_at}
                  </Text>
                </div>
              )}
              {t.output && (
                <div style={{ marginTop: 4, fontSize: 12, color: '#666' }}>{t.output}</div>
              )}
              {t.error && (
                <Alert
                  type="error"
                  message={t.error}
                  showIcon
                  style={{ marginTop: 8 }}
                />
              )}
            </Card>
          ))}
        </Space>
      )}
    </div>
  );

  const userTab = (
    <div data-testid="user-tasks-tab">
      {tasksLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}>
          <Spin />
        </div>
      ) : !userTasks || userTasks.length === 0 ? (
        <Empty description="暂无用户任务" />
      ) : (
        <Space direction="vertical" style={{ width: '100%' }} size={12}>
          {userTasks.map((t: any) => (
            <Card key={t.id} size="small">
              <Space>
                <Text strong>{t.name}</Text>
                <Tag color="blue">{t.task_type}</Tag>
                <Tag color={t.enabled ? 'green' : 'default'}>
                  {t.enabled ? '启用' : '停用'}
                </Tag>
              </Space>
              <div style={{ marginTop: 4 }}>
                <Text type="secondary" style={{ fontSize: 12 }}>
                  股票: {(t.codes || []).join(', ')} · 频率: {t.schedule}
                </Text>
              </div>
              {t.last_run && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    上次: {new Date(t.last_run).toLocaleString()}
                  </Text>
                </div>
              )}
            </Card>
          ))}
        </Space>
      )}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>
          ⏱ 任务执行
        </Title>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
          刷新
        </Button>
      </div>
      <Tabs
        items={[
          { key: 'sched', label: `内置调度器 (${tasks.length})`, children: schedulerTab },
          { key: 'user', label: `用户任务 (${userTasks?.length || 0})`, children: userTab },
        ]}
      />
    </div>
  );
}
