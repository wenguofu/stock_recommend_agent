import { useEffect, useState } from 'react';
import { Card, Tabs, Button, Tag, Space, Typography, Empty, Spin, Alert } from 'antd';
import { ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { stockAPI, SchedulerStatusTask } from '../services/api';

const { Title, Text } = Typography;

function formatElapsed(startedAt: string | null): string {
  if (!startedAt) return '';
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const sec = Math.floor((now - start) / 1000);
  if (sec < 60) return `${sec}s`;
  const min = Math.floor(sec / 60);
  const s = sec % 60;
  return `${min}m${s.toString().padStart(2, '0')}s`;
}

export default function TaskExecution() {
  const [tick, setTick] = useState(0);
  const [now, setNow] = useState<number>(Date.now());
  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['scheduler-status', tick],
    queryFn: () => stockAPI.schedulerStatus(),
  });
  const { data: userTasks, isLoading: tasksLoading } = useQuery({
    queryKey: ['user-tasks', tick],
    queryFn: () => stockAPI.listTasks(),
  });

  // Re-render once per second so formatElapsed() updates without refetching
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = () => setTick((t) => t + 1);

  const tasks: SchedulerStatusTask[] = (statusData?.tasks as SchedulerStatusTask[]) || [];
  const running = tasks.filter((t) => t.in_flight === true).length;
  const idle = tasks.filter((t) => t.in_flight === false).length;
  const totalRuns = tasks.reduce((sum, t) => sum + (t.run_count || 0), 0);
  // Reference `now` so it participates in the render lifecycle
  void now;

  const schedulerTab = (
    <div data-testid="scheduler-tab">
      <Card style={{ marginBottom: 16 }}>
        <Space size="large">
          <Text>
            执行中: <Tag color="green">{running}</Tag>
          </Text>
          <Text>
            空闲: <Tag color="default">{idle}</Tag>
          </Text>
          <Text>
            累计运行: <Tag color="blue">{totalRuns}</Tag>
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
            <Card key={t.name} size="small">
              <Space style={{ marginBottom: 8 }} wrap>
                {t.in_flight ? (
                  <Tag color="green" icon={<PlayCircleOutlined />}>
                    🟢执行中 {formatElapsed(t.current_started_at)}
                  </Tag>
                ) : (
                  <Tag color="default" icon={<PauseCircleOutlined />}>
                    ⏸空闲
                  </Tag>
                )}
                <Text strong>{t.name}</Text>
                {t.type && <Tag color="blue">{t.type}</Tag>}
                {t.schedule && <Tag>{t.schedule}</Tag>}
                <Tag color="cyan">累计 {t.run_count} 次</Tag>
              </Space>
              {t.last_run && (
                <div>
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    上次运行: {t.last_run}
                  </Text>
                </div>
              )}
              {t.last_output && (
                <div style={{ marginTop: 4, fontSize: 12, color: '#666' }}>{t.last_output}</div>
              )}
              {t.last_error && (
                <Alert
                  type="error"
                  message={t.last_error}
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
