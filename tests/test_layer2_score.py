# tests/test_layer2_score.py
import sys
sys.path.insert(0, '/Users/wgfu/work/a-stock-trading')

def test_layer2_scoring():
    """Test Layer 2 multi-signal scoring"""
    from screening.layer2_signal_score import score_layer2

    # 模拟Layer 1输出
    layer1_result = {
        'candidates': [
            {'code': '300750', 'name': '宁德时代'}
        ],
        'recommendation_type': 'short'
    }

    result = score_layer2(layer1_result)
    assert 'scored_candidates' in result
    assert 'top_candidates' in result