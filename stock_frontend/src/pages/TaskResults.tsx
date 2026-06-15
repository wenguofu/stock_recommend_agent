import { useState } from 'react';
import { Card, Tabs, DatePicker, Table, Tag, Typography, Empty, Spin, Drawer, Descriptions, Space } from 'antd';
import { useQuery } from '@tanstack/react-query';
import dayjs, { Dayjs } from 'dayjs';
import { stockAPI, SchedulerRun, TaskLogEntry } from '../services/api';

const { Title, Text } = Typography;

const STATUS_COLORS: Record<string, string> = {
  success: 'green',
  failed: 'red',
  running: 'blue',
  skipped: 'default',
};

function disabledDate(current: Dayjs) {
  // 禁用未来日期 + 7 天前之前
  const today = dayjs().endOf('day');
  const minDate = dayjs().subtract(7, 'day').startOf('day');
  return current && (current > today || current < minDate);
}

export default function TaskResults() {
  const [date, setDate] = useState<Dayjs>(dayjs());
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

  const [drawerRow, setDrawerRow] = useState<SchedulerRun | (TaskLogEntry & { task_name: string }) | null>(null);

  const runs: SchedulerRun[] = runsData?.data || [];
  const userLogs: (TaskLogEntry & { task_name: string })[] = taskLogQueries.data || [];

  const schedulerColumns = [
    { title: '任务', dataIndex: 'task_name', key: 'task_name' },
    {
      title: '触发时间',
      dataIndex: 'started_at',
      key: 'started_at',
      render: (v: string | null) => v ? new Date(v).toLocaleString() : '-',
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
      render: (v: string) => v ? new Date(v).toLocaleString() : '-',
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

  const schedulerTab = (
    <Card>
      {runsLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
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
  );

  const userTab = (
    <Card>
      {!userTasks || userTasks.length === 0 ? (
        <Empty description="暂无用户任务" />
      ) : taskLogQueries.isLoading ? (
        <div style={{ textAlign: 'center', padding: 48 }}><Spin /></div>
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
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <Title level={2} style={{ margin: 0 }}>📊 任务执行结果</Title>
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
      <Tabs
        items={[
          { key: 'sched', label: `内置调度器 (${runs.length})`, children: schedulerTab },
          { key: 'user', label: `用户任务 (${userLogs.length})`, children: userTab },
        ]}
      />
      <Drawer
        open={!!drawerRow}
        onClose={() => setDrawerRow(null)}
        title={(drawerRow as any)?.task_name || '详情'}
        width={600}
      >
        {drawerRow && (
          <Descriptions column={1} bordered size="small">
            <Descriptions.Item label="状态">
              <Tag color={STATUS_COLORS[(drawerRow as any).status] || 'default'}>{(drawerRow as any).status}</Tag>
            </Descriptions.Item>
            <Descriptions.Item label="开始时间">
              {(drawerRow as any).started_at ? new Date((drawerRow as any).started_at).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="结束时间">
              {(drawerRow as any).finished_at ? new Date((drawerRow as any).finished_at).toLocaleString() : '-'}
            </Descriptions.Item>
            {(drawerRow as any).duration_ms != null && (
              <Descriptions.Item label="耗时">{((drawerRow as any).duration_ms / 1000).toFixed(2)}s</Descriptions.Item>
            )}
            {(drawerRow as any).trigger_source && (
              <Descriptions.Item label="触发来源">{(drawerRow as any).trigger_source}</Descriptions.Item>
            )}
            {(drawerRow as any).output && (
              <Descriptions.Item label="输出">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{(drawerRow as any).output}</pre>
              </Descriptions.Item>
            )}
            {(drawerRow as any).error && (
              <Descriptions.Item label="错误">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0, color: '#cf1322' }}>{(drawerRow as any).error}</pre>
              </Descriptions.Item>
            )}
            {(drawerRow as any).result && (
              <Descriptions.Item label="结果">
                <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{JSON.stringify((drawerRow as any).result, null, 2)}</pre>
              </Descriptions.Item>
            )}
          </Descriptions>
        )}
      </Drawer>
    </div>
  );
}
