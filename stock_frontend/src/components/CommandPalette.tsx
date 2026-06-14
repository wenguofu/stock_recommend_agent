/**
 * Sprint5: Command+K 命令面板
 *
 * 用法: 在 Layout 中 <CommandPalette /> 即可, 全局监听 ⌘K / Ctrl+K
 * 支持:
 *  - 跳转到任意页面
 *  - 跳转到任意股票详情
 *  - 触发任意 GET API
 */
import { useState, useEffect, useMemo, useCallback } from 'react';
import { Modal, Input, List, Tag, Empty } from 'antd';
import { useNavigate } from 'react-router-dom';
import {
  HomeOutlined, StarOutlined, ExperimentOutlined, BarChartOutlined,
  SettingOutlined, ScheduleOutlined, LineChartOutlined, AimOutlined,
  BulbOutlined, SafetyOutlined, MonitorOutlined, ThunderboltOutlined,
  OrderedListOutlined, TrophyOutlined, SearchOutlined, AlertOutlined,
  FundOutlined,
} from '@ant-design/icons';
import React from 'react';

interface Command {
  id: string;
  title: string;
  subtitle?: string;
  icon?: React.ReactNode;
  group: '页面' | '股票' | 'API';
  action: () => void;
  keywords?: string[];
}

const ICON_MAP: Record<string, React.ReactNode> = {
  HomeOutlined: <HomeOutlined />,
  StarOutlined: <StarOutlined />,
  ExperimentOutlined: <ExperimentOutlined />,
  BarChartOutlined: <BarChartOutlined />,
  SettingOutlined: <SettingOutlined />,
  ScheduleOutlined: <ScheduleOutlined />,
  LineChartOutlined: <LineChartOutlined />,
  AimOutlined: <AimOutlined />,
  BulbOutlined: <BulbOutlined />,
  SafetyOutlined: <SafetyOutlined />,
  MonitorOutlined: <MonitorOutlined />,
  ThunderboltOutlined: <ThunderboltOutlined />,
  OrderedListOutlined: <OrderedListOutlined />,
  TrophyOutlined: <TrophyOutlined />,
  FundOutlined: <FundOutlined />,
  AlertOutlined: <AlertOutlined />,
};

const PAGE_COMMANDS: Array<Omit<Command, 'id' | 'group' | 'action'>> = [
  { title: '首页', icon: <HomeOutlined />, keywords: ['home', 'index'] },
  { title: '自选股', icon: <StarOutlined />, keywords: ['watchlist', 'star'] },
  { title: '模拟盘', icon: <ExperimentOutlined />, keywords: ['paper'] },
  { title: '收益排名', icon: <TrophyOutlined />, keywords: ['ranking', 'rank'] },
  { title: '股票推荐', icon: <BulbOutlined />, keywords: ['recommend'] },
  { title: '高胜率推荐', icon: <SafetyOutlined />, keywords: ['high win'] },
  { title: '任务', icon: <ScheduleOutlined />, keywords: ['task', 'scheduler'] },
  { title: '策略库', icon: <OrderedListOutlined />, keywords: ['strategy library'] },
  { title: '策略推荐', icon: <ThunderboltOutlined />, keywords: ['strategy recommend'] },
  { title: '回测', icon: <BarChartOutlined />, keywords: ['backtest'] },
  { title: '组合优化', icon: <FundOutlined />, keywords: ['portfolio'] },
  { title: 'ML 监控', icon: <MonitorOutlined />, keywords: ['ml', 'monitor', 'drift'] },
  { title: '主线预判', icon: <AimOutlined />, keywords: ['sector', 'prediction'] },
  { title: '自选池健康度', icon: <LineChartOutlined />, keywords: ['midline'] },
  { title: '告警中心', icon: <AlertOutlined />, keywords: ['alert'] },
  { title: '配置', icon: <SettingOutlined />, keywords: ['settings', 'config'] },
];

const PAGE_ROUTES: Record<string, string> = {
  '首页': '/',
  '自选股': '/watchlist',
  '模拟盘': '/paper',
  '收益排名': '/paper/rankings',
  '股票推荐': '/recommendations',
  '高胜率推荐': '/high-win-recommend',
  '任务': '/tasks',
  '策略库': '/strategies',
  '策略推荐': '/strategy',
  '回测': '/backtest',
  '组合优化': '/portfolio',
  'ML 监控': '/monitoring',
  '主线预判': '/sector-prediction',
  '自选池健康度': '/midline',
  '告警中心': '/alerts',
  '配置': '/settings',
};

interface Props {
  // 监听 ⌘K, 默认开启
  enabled?: boolean;
  // 外部控制开闭
  externalOpen?: boolean;
  onClose?: () => void;
}

export default function CommandPalette({ enabled = true, externalOpen, onClose }: Props) {
  const navigate = useNavigate();
  const [internalOpen, setInternalOpen] = useState(false);
  const open = externalOpen !== undefined ? externalOpen : internalOpen;
  const setOpen = (v: boolean | ((o: boolean) => boolean)) => {
    const next = typeof v === 'function' ? v(open) : v;
    if (externalOpen !== undefined) {
      if (!next) onClose?.();
    } else {
      setInternalOpen(next);
    }
  };
  const [query, setQuery] = useState('');
  const [selectedIdx, setSelectedIdx] = useState(0);

  // 全局快捷键
  useEffect(() => {
    if (!enabled) return;
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setOpen(o => !o);
      } else if (e.key === 'Escape' && open) {
        setOpen(false);
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [enabled, open]);

  // 构建命令列表
  const commands: Command[] = useMemo(() => {
    const cmds: Command[] = [];
    PAGE_COMMANDS.forEach((p) => {
      cmds.push({
        id: 'page-' + p.title,
        title: p.title,
        subtitle: PAGE_ROUTES[p.title],
        icon: p.icon,
        group: '页面',
        action: () => navigate(PAGE_ROUTES[p.title]),
        keywords: p.keywords,
      });
    });

    // 股票代码模式: 输入 6 位数字 → 跳转 stock/CODE
    const m = query.match(/^\d{6}$/);
    if (m) {
      cmds.push({
        id: 'stock-' + m[0],
        title: `查看 ${m[0]}`,
        subtitle: `/stock/${m[0]}`,
        icon: <StarOutlined />,
        group: '股票',
        action: () => navigate(`/stock/${m[0]}`),
      });
    }
    return cmds;
  }, [navigate, query]);

  // 过滤
  const filtered = useMemo(() => {
    if (!query.trim()) return commands;
    const q = query.toLowerCase();
    return commands.filter(c =>
      c.title.toLowerCase().includes(q) ||
      c.subtitle?.toLowerCase().includes(q) ||
      c.keywords?.some(k => k.toLowerCase().includes(q))
    );
  }, [commands, query]);

  // 键盘上下选择
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setSelectedIdx(i => Math.min(i + 1, filtered.length - 1));
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setSelectedIdx(i => Math.max(i - 1, 0));
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const cmd = filtered[selectedIdx];
        if (cmd) {
          cmd.action();
          setOpen(false);
          setQuery('');
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, filtered, selectedIdx]);

  // query 变化时重置
  useEffect(() => {
    setSelectedIdx(0);
  }, [query]);

  const grouped = useMemo(() => {
    const groups: Record<string, Command[]> = {};
    filtered.forEach((c) => {
      if (!groups[c.group]) groups[c.group] = [];
      groups[c.group].push(c);
    });
    return groups;
  }, [filtered]);

  return (
    <Modal
      open={open}
      onCancel={() => { setOpen(false); setQuery(''); }}
      footer={null}
      width={600}
      destroyOnClose
      closable={false}
      styles={{ body: { padding: 0 } }}
    >
      <div style={{ padding: '12px 16px', borderBottom: '1px solid #f0f0f0' }}>
        <Input
          autoFocus
          size="large"
          prefix={<SearchOutlined />}
          placeholder="搜索页面、输入股票代码、回车跳转..."
          value={query}
          onChange={e => setQuery(e.target.value)}
          allowClear
        />
        <div style={{ fontSize: 12, color: '#999', marginTop: 4 }}>
          ↑↓ 选择 / ↵ 跳转 / Esc 关闭 (⌘K)
        </div>
      </div>
      <div style={{ maxHeight: 400, overflowY: 'auto' }}>
        {filtered.length === 0 && (
          <Empty description="无匹配项" style={{ padding: 32 }} />
        )}
        {Object.entries(grouped).map(([group, items]) => (
          <div key={group}>
            <div style={{
              padding: '6px 16px',
              fontSize: 12,
              fontWeight: 600,
              color: '#999',
              background: '#fafafa',
            }}>{group}</div>
            <List
              dataSource={items}
              renderItem={(item, idx) => {
                const flatIdx = filtered.indexOf(item);
                return (
                  <List.Item
                    style={{
                      padding: '10px 16px',
                      cursor: 'pointer',
                      background: flatIdx === selectedIdx ? '#e6f4ff' : 'transparent',
                    }}
                    onClick={() => {
                      item.action();
                      setOpen(false);
                      setQuery('');
                    }}
                    onMouseEnter={() => setSelectedIdx(flatIdx)}
                  >
                    <List.Item.Meta
                      avatar={item.icon}
                      title={item.title}
                      description={item.subtitle}
                    />
                  </List.Item>
                );
              }}
            />
          </div>
        ))}
      </div>
    </Modal>
  );
}
