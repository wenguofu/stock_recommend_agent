import { ReactNode, useState, useEffect } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { Layout as AntLayout, Menu, Segmented, Typography, theme } from 'antd';
import {
  HomeOutlined, StarOutlined, ExperimentOutlined, ThunderboltOutlined,
  BarChartOutlined, SettingOutlined, OrderedListOutlined, TrophyOutlined,
  ScheduleOutlined, LineChartOutlined, AimOutlined, BulbOutlined,
  SafetyOutlined,
} from '@ant-design/icons';

const { Sider, Content } = AntLayout;
const { Text } = Typography;

interface LayoutProps {
  children: ReactNode;
}

const QUANT_NAV = [
  { path: '/', label: '首页', icon: <HomeOutlined /> },
  { path: '/watchlist', label: '自选', icon: <StarOutlined /> },
  { path: '/paper', label: '模拟盘', icon: <ExperimentOutlined /> },
  { path: '/paper/rankings', label: '收益排名', icon: <TrophyOutlined /> },
  { path: '/recommendations', label: '股票推荐', icon: <BulbOutlined /> },
  { path: '/high-win-recommend', label: '高胜率推荐', icon: <SafetyOutlined /> },
  { path: '/tasks', label: '任务', icon: <ScheduleOutlined /> },
  { path: '/strategies', label: '策略库', icon: <OrderedListOutlined /> },
  { path: '/strategy', label: '策略推荐', icon: <ThunderboltOutlined /> },
  { path: '/backtest', label: '回测', icon: <BarChartOutlined /> },
  { path: '/sector-prediction', label: '主线预判', icon: <AimOutlined /> },
  { path: '/settings', label: '配置', icon: <SettingOutlined /> },
];

const MIDLINE_NAV = [
  { path: '/midline', label: '自选池健康度', icon: <LineChartOutlined /> },
  { path: '/settings', label: '配置', icon: <SettingOutlined /> },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const { token } = theme.useToken();
  const isMidline = location.pathname.startsWith('/midline');
  const [strategy, setStrategy] = useState<'quant' | 'midline'>(isMidline ? 'midline' : 'quant');
  const [collapsed, setCollapsed] = useState(false);

  useEffect(() => {
    setStrategy(isMidline ? 'midline' : 'quant');
  }, [isMidline]);

  const navItems = strategy === 'midline' ? MIDLINE_NAV : QUANT_NAV;

  // 匹配当前路径到导航项
  const resolvedKey = (() => {
    const exact = navItems.find(i => i.path === location.pathname);
    if (exact) return exact.path;
    const prefix = navItems.find(i => location.pathname.startsWith(i.path + '/'));
    if (prefix) return prefix.path;
    return '/';
  })();

  const switchStrategy = (val: string | number) => {
    const s = val as 'quant' | 'midline';
    setStrategy(s);
    navigate(s === 'midline' ? '/midline' : '/');
  };

  return (
    <AntLayout style={{ minHeight: '100vh' }}>
      <Sider
        collapsible
        collapsed={collapsed}
        onCollapse={setCollapsed}
        breakpoint="lg"
        style={{ background: token.colorBgContainer }}
      >
        <div style={{
          height: 64,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          borderBottom: `1px solid ${token.colorBorderSecondary}`,
        }}>
          <Text strong style={{ fontSize: collapsed ? 14 : 16, whiteSpace: 'nowrap' }}>
            📈 {collapsed ? '' : '股票交易系统'}
          </Text>
        </div>

        <div style={{ padding: '12px 16px' }}>
          <Segmented
            block
            size="small"
            value={strategy}
            onChange={switchStrategy}
            options={[
              { label: '⚡ 短线', value: 'quant' },
              { label: '📊 中长线', value: 'midline' },
            ]}
          />
        </div>

        <Menu
          mode="inline"
          selectedKeys={[resolvedKey]}
          items={navItems.map(item => ({
            key: item.path,
            icon: item.icon,
            label: <Link to={item.path}>{item.label}</Link>,
          }))}
          style={{ borderInlineEnd: 'none' }}
        />
      </Sider>

      <AntLayout>
        <Content style={{ padding: 24, background: token.colorBgLayout, minHeight: '100vh' }}>
          {children}
        </Content>
      </AntLayout>
    </AntLayout>
  );
}
