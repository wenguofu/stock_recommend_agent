import { useEffect, useState } from 'react';
import {
  Card, Tabs, Button, Tag, Space, Typography, Empty, Spin, Alert,
  DatePicker, Table, Drawer, Descriptions,
} from 'antd';
import { ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import dayjs, { Dayjs } from 'dayjs';
import { stockAPI, SchedulerStatusTask, SchedulerRun, TaskLogEntry } from '../services/api';

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  skipped: 'default',
  completed: 'green',
  failed_user: 'red',
};

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

function disabledDate(current: Dayjs) {
  const today = dayjs().endOf('day');
  const minDate = dayjs().subtract(7, 'day').startOf('day');
  return current && (current > today || current < minDate);
}

export default function TaskCenter() {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>
          ⏱ 任务中心
        </Title>
      </div>
      <Tabs
        items={[
          { key: 'status', label: '执行状态', children: <StatusTab /> },
          { key: 'results', label: '执行结果', children: <ResultsTab /> },
        ]}
      />
    </div>
  );
}

// ─── Status Tab (current execution) ────────────────────────────────────────

function StatusTab() {
  const [tick, setTick] = useState(0);
  const [, setNow] = useState<number>(Date.now());

  const { data: statusData, isLoading: statusLoading } = useQuery({
    queryKey: ['scheduler-status', tick],
    queryFn: () => stockAPI.schedulerStatus(),
  });
  const { data: userTasks, isLoading: tasksLoading } = useQuery({
    queryKey: ['user-tasks', tick],
    queryFn: () => stockAPI.listTasks(),
  });

  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, []);

  const handleRefresh = () => setTick((t) => t + 1);

  const tasks: SchedulerStatusTask[] = (statusData?.tasks as SchedulerStatusTask[]) || [];
  const running = tasks.filter((t) => t.in_flight === true).length;
  const idle = tasks.filter((t) => t.in_flight === false).length;
  const totalRuns = tasks.reduce((sum, t) => sum + (t.run_count || 0), 0);

  return (
    <div data-testid="status-tab">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <Button icon={<ReloadOutlined />} onClick={handleRefresh}>
          刷新
        </Button>
      </div>
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
      {tasksLoading ? (
        <div style={{ textAlign: 'center', padding: 24 }}>
          <Spin />
        </div>
      ) : userTasks && userTasks.length > 0 ? (
        <Card title="用户任务" style={{ marginTop: 16 }}>
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
        </Card>
      ) : null}
    </div>
  );
}

// ─── Results Tab (historical by date) ───────────────────────────────────────

type DrawerRow = SchedulerRun | (TaskLogEntry & { task_name: string });

function ResultsTab() {
  const [date, setDate] = useState<Dayjs>(dayjs());
  const [drawerRow, setDrawerRow] = useState<DrawerRow | null>(null);
  const dateStr = date.format('YYYY-MM-DD');

  const { data: runsData, isLoading: runsLoading } = useQuery({
    queryKey: ['scheduler-runs', dateStr],
    queryFn: () => stockAPI.schedulerRuns(dateStr),
  });

  const { data: userTasks } = useQuery({
    queryKey: ['user-tasks-results'],
    queryFn: () => stockAPI.listTasks(),
  });

  const taskIds: number[] = (userTasks || []).map((t: any) => t.id);
  const taskLogQueries = useQuery({
    queryKey: ['user-task-logs', dateStr, taskIds.join(',')],
    queryFn: async () => {
      const lists = await Promise.all(
        taskIds.map((id) => stockAPI.taskLogsByDate(id, dateStr)),
      );
      return lists.flatMap((r, i) =>
        (r.data || []).map((log) => ({
          ...log,
          task_name: (userTasks || [])[i]?.name || `任务${i + 1}`,
        })),
      );
    },
    enabled: taskIds.length > 0,
  });

  const runs: SchedulerRun[] = runsData?.data || [];
  const userLogs: (TaskLogEntry & { task_name: string })[] = taskLogQueries.data || [];

  const schedulerColumns = [
    { title: '任务', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '触发时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string | null) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: '耗时',
      dataIndex: 'duration_ms',
      key: 'duration_ms',
      render: (v: number | null) => (v == null ? '-' : `${(v / 1000).toFixed(1)}s`),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '来源',
      dataIndex: 'trigger_source',
      key: 'trigger_source',
      render: (v: string | null) => <Tag>{v || '-'}</Tag>,
    },
  ];

  const userColumns = [
    { title: '任务', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '触发时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string) => (v ? new Date(v).toLocaleString() : '-'),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (v: string) => <Tag color={STATUS_COLORS[v] || 'default'}>{v}</Tag>,
    },
    {
      title: '触发条数',
      dataIndex: 'triggered_count',
      key: 'triggered_count',
      render: (v: number) => v || 0,
    },
  ];

  return (
    <div data-testid="results-tab">
      <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 12 }}>
        <Space>
          <Text type="secondary">日期:</Text>
          <DatePicker
            value={date}
            onChange={(d) => d && setDate(d)}
            disabledDate={disabledDate}
            allowClear={false}
          />
        </Space>
      </div>
      <Card title="内置调度器" style={{ marginBottom: 16 }}>
        {runsLoading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : runs.length === 0 ? (
          <Empty description={`${dateStr} 暂无调度器执行记录`} />
        ) : (
          <Table
            rowKey="id"
            dataSource={runs}
            columns={schedulerColumns}
            pagination={{ pageSize: 20 }}
            onRow={(record) => ({ onClick: () => setDrawerRow(record) })}
          />
        )}
      </Card>
      <Card title="用户任务">
        {!userTasks || userTasks.length === 0 ? (
          <Empty description="暂无用户任务" />
        ) : taskLogQueries.isLoading ? (
          <div style={{ textAlign: 'center', padding: 48 }}>
            <Spin />
          </div>
        ) : userLogs.length === 0 ? (
          <Empty description={`${dateStr} 暂无用户任务执行记录`} />
        ) : (
          <Table
            rowKey="id"
            dataSource={userLogs}
            columns={userColumns}
            pagination={{ pageSize: 20 }}
            onRow={(record) => ({ onClick: () => setDrawerRow(record) })}
          />
        )}
      </Card>
      <Drawer
        open={!!drawerRow}
        onClose={() => setDrawerRow(null)}
        title={(drawerRow as any)?.task_name || '详情'}
        width={600}
      >
        {drawerRow && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="状态">
              <Tag color={STATUS_COLORS[(drawerRow as any).status] || 'default'}>
                {(drawerRow as any).status}
              </Tag>
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {(drawerRow as any).started_at
                ? new Date((drawerRow as any).started_at).toLocaleString()
                : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {(drawerRow as any).finished_at
                ? new Date((drawerRow as any).finished_at).toLocaleString()
                : '-'}
            </Descriptions.Item>
            {(drawerRow as any).duration_ms != null && (
              <Descriptions.Item label="耗时">
                {((drawerRow as any).duration_ms / 1000).toFixed(2)}s
              </Descriptions.Item>
            )}
            {(drawerRow as any).trigger_source && (
              <Descriptions.Item label="触发来源">
                {(drawerRow as any).trigger_source}
              </Descriptions.Item>
            )}
            {(drawerRow as any).output && (
              <Descriptions.Item label="输出">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                  {(drawerRow as any).output}
                </pre>
              </Descriptions.Item>
            )}
            {(drawerRow as any).error && (
              <Descriptions.Item label="错误">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: '#cf1322' }}>
                  {(drawerRow as any).error}
                </pre>
              </Descriptions.Item>
            )}
            {(drawerRow as any).result && (
              <Descriptions.Item label="结果">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>
                  {JSON.stringify((drawerRow as any).result, null, 2)}
                </pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}