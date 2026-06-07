"""
所有 25 个页面的 E2E 测试定义
"""
from .home import HomeTest
from .watchlist import WatchlistTest
from .stock_detail import StockDetailTest
from .tasks import TasksTest
from .strategy import StrategyTest
from .strategy_library import StrategyLibraryTest
from .strategy_run import StrategyRunTest
from .strategy_recommend import StrategyRecommendTest
from .strategy_config import StrategyConfigTest
from .ai_debate import AIDebateTest
from .paper_accounts import PaperAccountsTest
from .paper_detail import PaperDetailTest
from .paper_rankings import PaperRankingsTest
from .paper_breakdown import PaperBreakdownTest
from .recommendations import RecommendationsTest
from .high_win_recommend import HighWinRecommendTest
from .backtest import BacktestTest
from .sector_prediction import SectorPredictionTest
from .sensitivity_scan import SensitivityScanTest
from .portfolio import PortfolioTest
from .ml_monitoring import MLMonitoringTest
from .alert_center import AlertCenterTest
from .settings import SettingsTest
from .midline import MidlineTest
from .not_found import NotFoundTest


ALL_TESTS = [
    HomeTest,
    WatchlistTest,
    StockDetailTest,
    TasksTest,
    StrategyTest,
    StrategyLibraryTest,
    StrategyRunTest,
    StrategyRecommendTest,
    StrategyConfigTest,
    AIDebateTest,
    PaperAccountsTest,
    PaperDetailTest,
    PaperRankingsTest,
    PaperBreakdownTest,
    RecommendationsTest,
    HighWinRecommendTest,
    BacktestTest,
    SectorPredictionTest,
    SensitivityScanTest,
    PortfolioTest,
    MLMonitoringTest,
    AlertCenterTest,
    SettingsTest,
    MidlineTest,
    NotFoundTest,
]

# 按 path 索引
BY_PATH = {t.path: t for t in ALL_TESTS}
