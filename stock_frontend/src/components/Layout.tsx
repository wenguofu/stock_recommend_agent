import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ReactNode, useState, useEffect } from 'react';

interface LayoutProps {
  children: ReactNode;
}

/** 短线量化导航 */
const QUANT_NAV = [
  { path: '/', label: '首页' },
  { path: '/watchlist', label: '自选' },
  { path: '/paper', label: '模拟盘' },
  { path: '/paper/rankings', label: '收益排名' },
  { path: '/recommendations', label: '股票推荐' },
  { path: '/tasks', label: '任务' },
  { path: '/strategies', label: '策略库' },
  { path: '/strategy', label: '策略推荐' },
  { path: '/backtest', label: '回测' },
  { path: '/sector-prediction', label: '🔮主线预判' },
  { path: '/settings', label: '配置' },
];

/** 中长线交易导航 */
const MIDLINE_NAV = [
  { path: '/midline', label: '🏠中长线看板' },
  { path: '/watchlist', label: '自选池' },
  { path: '/midline/journal', label: '交易日志' },
  { path: '/settings', label: '配置' },
];

export default function Layout({ children }: LayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();

  // 根据路径判断当前策略模式
  const isMidline = location.pathname.startsWith('/midline');
  const [strategy, setStrategy] = useState<'quant' | 'midline'>(isMidline ? 'midline' : 'quant');

  useEffect(() => {
    setStrategy(isMidline ? 'midline' : 'quant');
  }, [isMidline]);

  const navItems = strategy === 'midline' ? MIDLINE_NAV : QUANT_NAV;

  const switchStrategy = (s: 'quant' | 'midline') => {
    setStrategy(s);
    navigate(s === 'midline' ? '/midline' : '/');
  };

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-gray-900">
      <nav className="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          {/* 策略切换栏 */}
          <div className="flex items-center justify-between py-2 border-b border-gray-100 dark:border-gray-700">
            <Link to="/" className="text-lg font-bold text-gray-900 dark:text-white">
              📈 股票交易系统
            </Link>
            <div className="flex bg-gray-100 dark:bg-gray-700 rounded-lg p-0.5">
              <button
                onClick={() => switchStrategy('quant')}
                className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
                  strategy === 'quant'
                    ? 'bg-white dark:bg-gray-600 text-blue-600 dark:text-blue-400 shadow font-medium'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
                }`}
              >
                ⚡ 短线量化
              </button>
              <button
                onClick={() => switchStrategy('midline')}
                className={`px-4 py-1.5 text-sm rounded-md transition-colors ${
                  strategy === 'midline'
                    ? 'bg-white dark:bg-gray-600 text-green-600 dark:text-green-400 shadow font-medium'
                    : 'text-gray-500 dark:text-gray-400 hover:text-gray-700'
                }`}
              >
                📊 中长线交易
              </button>
            </div>
          </div>
          {/* 子导航 */}
          <div className="flex space-x-6 h-10 overflow-x-auto">
            {navItems.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`inline-flex items-center px-1 border-b-2 text-sm font-medium whitespace-nowrap ${
                  location.pathname === item.path
                    ? 'border-blue-500 text-gray-900 dark:text-white'
                    : 'border-transparent text-gray-500 hover:border-gray-300 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                {item.label}
              </Link>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        {children}
      </main>
    </div>
  );
}
