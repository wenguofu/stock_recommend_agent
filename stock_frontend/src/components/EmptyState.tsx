import { Empty } from 'antd';

interface EmptyStateProps {
  description?: string;
  action?: React.ReactNode;
}

export default function EmptyState({ description = '暂无数据', action }: EmptyStateProps) {
  return (
    <Empty
      description={description}
      style={{ padding: '48px 0' }}
    >
      {action}
    </Empty>
  );
}
