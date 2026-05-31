# tests/test_layer3_verify.py
import sys
sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')

def test_layer3_verification():
    """Test Layer 3 historical win rate verification"""
    from screening.layer3_backtest_verify import verify_layer3

    layer2_result = {
        'top_candidates': [
            {'code': '300750', 'name': '宁德时代', 'composite_score': 75.5}
        ],
        'recommendation_type': 'short'
    }

    result = verify_layer3(layer2_result)
    assert 'verified_candidates' in result
    assert 'top_recommendations' in result