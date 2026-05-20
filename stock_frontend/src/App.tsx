import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Home from './pages/Home';
import Watchlist from './pages/Watchlist';
import StockDetail from './pages/StockDetail';
import Tasks from './pages/Tasks';
import Strategy from './pages/Strategy';
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
import Layout from './components/Layout';
import './index.css';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30000, // 30秒
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Layout>
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/watchlist" element={<Watchlist />} />
            <Route path="/stock/:code" element={<StockDetail />} />
            <Route path="/tasks" element={<Tasks />} />
            <Route path="/strategy" element={<Strategy />} />
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
          </Routes>
        </Layout>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
