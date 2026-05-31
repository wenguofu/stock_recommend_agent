# tests/test_layer1_screen.py
import pytest
import sys
sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')

def test_layer1_basic():
    """Test Layer 1 screening returns results"""
    from screening.layer1_tech_screen import screen_layer1
    result = screen_layer1(recommendation_type='short')
    assert result is not None
    assert 'candidates' in result


def test_market_safety_check():
    """Test market safety check returns correct structure"""
    from screening.layer1_tech_screen import is_market_safe_for_screening
    is_safe, details = is_market_safe_for_screening()
    assert isinstance(is_safe, bool)
    assert 'strong_count' in details
    assert 'limit_down_count' in details
    assert 'reason' in details


def test_layer1_short_screening():
    """Test Layer 1 short-term screening"""
    from screening.layer1_tech_screen import screen_layer1
    result = screen_layer1(recommendation_type='short')
    assert 'candidates' in result
    assert 'market_check' in result
    assert 'filter_applied' in result


def test_layer1_mid_screening():
    """Test Layer 1 mid-term screening"""
    from screening.layer1_tech_screen import screen_layer1
    result = screen_layer1(recommendation_type='mid')
    assert result['recommendation_type'] == 'mid'


def test_recommendation_engine():
    """Test end-to-end recommendation engine"""
    from screening.recommendation_engine import get_recommendations
    result = get_recommendations(recommendation_type='short')
    assert 'recommendations' in result
    assert 'pipeline_status' in result


def test_daily_monitor():
    """Test daily monitor"""
    from monitoring.daily_monitor import DailyMonitor
    monitor = DailyMonitor()
    status = monitor.get_daily_status()
    assert 'positions' in status
    assert 'recommendations' in status