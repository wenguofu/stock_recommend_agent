import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ConfigProvider, App as AntApp, theme } from 'antd';
import zhCN from 'antd/locale/zh_CN';
import Home from './pages/Home';
import Watchlist from './pages/Watchlist';
import StockDetail from './pages/StockDetail';
import Tasks from './pages/Tasks';
import StrategyRecommend from './pages/StrategyRecommend';
import StrategyLibrary from './pages/StrategyLibrary';
import StrategyRun from './pages/StrategyRun';
import Settings from './pages/Settings';
import AIDebate from './pages/AIDebate';
import PaperAccounts from './pages/PaperAccounts';
import PaperDetail from './pages/PaperDetail';
import PaperRankings from './pages/PaperRankings';
import PaperBreakdown from './pages/PaperBreakdown';
import Recommendations from './pages/Recommendations';
import BacktestPage from './pages/BacktestPage';
import SectorPrediction from './pages/SectorPrediction';
import Midline from './pages/Midline';
import Layout from './components/Layout';
import ErrorBoundary from './components/ErrorBoundary';
import NotFound from './pages/NotFound';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000,
    },
  },
});

function App() {
  return (
    <ConfigProvider
      theme={{
        cssVar: { prefix: 'ant' },
        token: { colorPrimary: '#1677ff', borderRadius: 6 },
      }}
      locale={zhCN}
    >
      <AntApp>
        <QueryClientProvider client={queryClient}>
          <BrowserRouter>
            <Layout>
              <ErrorBoundary>
                <Routes>
                  <Route path="/" element={<Home />} />
                  <Route path="/watchlist" element={<Watchlist />} />
                  <Route path="/stock/:code" element={<StockDetail />} />
                  <Route path="/tasks" element={<Tasks />} />
                  <Route path="/strategy" element={<StrategyRecommend />} />
                  <Route path="/strategies" element={<StrategyLibrary />} />
                  <Route path="/strategies/:id/run" element={<StrategyRun />} />
                  <Route path="/ai-debate" element={<AIDebate />} />
                  <Route path="/settings" element={<Settings />} />
                  <Route path="/paper" element={<PaperAccounts />} />
                  <Route path="/paper/:id" element={<PaperDetail />} />
                  <Route path="/paper/rankings" element={<PaperRankings />} />
                  <Route path="/paper/breakdown/:id" element={<PaperBreakdown />} />
                  <Route path="/recommendations" element={<Recommendations />} />
                  <Route path="/backtest" element={<BacktestPage />} />
                  <Route path="/sector-prediction" element={<SectorPrediction />} />
                  <Route path="/midline" element={<Midline />} />
                  <Route path="*" element={<NotFound />} />
                </Routes>
              </ErrorBoundary>
            </Layout>
          </BrowserRouter>
        </QueryClientProvider>
      </AntApp>
    </ConfigProvider>
  );
}

export default App;
