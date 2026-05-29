# llm_agents/agent_orchestrator.py
"""Orchestrate 4 specialist agents in parallel, then fusion agent for final decision."""

import concurrent.futures
import hashlib
import json
import logging
from datetime import datetime
from typing import Dict, List
from .agent_base import TradingAgent
from .agent_cache import get_cached, set_cache

logger = logging.getLogger(__name__)

# Singleton agents (created once)
_agents = {}

def _get_agent(name: str, prompt_file: str) -> TradingAgent:
    if name not in _agents:
        _agents[name] = TradingAgent(name, name.lower(), prompt_file)
    return _agents[name]

def _get_all_agents():
    return {
        'Macro': _get_agent('Macro', 'macro_agent.txt'),
        'Technical': _get_agent('Technical', 'technical_agent.txt'),
        'Fundamental': _get_agent('Fundamental', 'fundamental_agent.txt'),
        'Risk': _get_agent('Risk', 'risk_agent.txt'),
        'Fusion': _get_agent('Fusion', 'fusion_agent.txt'),
    }

def analyze_stock(stock_data: Dict, dl_predictions: Dict = None,
                  portfolio_context: Dict = None) -> Dict:
    """
    Full 4-agent concurrent analysis + fusion decision for one stock.
    Returns complete analysis with final trading decision.
    """
    agents = _get_all_agents()

    # Compute data hash for caching
    data_str = json.dumps({'code': stock_data.get('code', ''), 'price': stock_data.get('price', 0)})
    data_hash = hashlib.md5(data_str.encode()).hexdigest()
    cached = get_cached(stock_data.get('code', ''), data_hash)
    if cached:
        return cached

    # Inject portfolio context into stock data
    enriched_stock = dict(stock_data)
    if portfolio_context:
        enriched_stock['portfolio'] = portfolio_context

    # Run 4 specialist agents concurrently
    specialist_agents = {
        'Macro': agents['Macro'],
        'Technical': agents['Technical'],
        'Fundamental': agents['Fundamental'],
        'Risk': agents['Risk'],
    }

    specialist_results = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {
            executor.submit(agent.analyze, enriched_stock, dl_predictions): name
            for name, agent in specialist_agents.items()
        }
        for future in concurrent.futures.as_completed(futures):
            agent_name = futures[future]
            try:
                specialist_results[agent_name] = future.result(timeout=120)
            except Exception as e:
                logger.error(f"Agent {agent_name} failed: {e}")
                specialist_results[agent_name] = {'error': str(e), 'confidence': 0, '_agent': agent_name}

    # Fusion decision (sequential — needs all specialist results)
    fusion_context = _build_fusion_context(stock_data, specialist_results, dl_predictions)
    fusion_input = {'fusion_context': fusion_context, 'code': stock_data.get('code', ''),
                    'name': stock_data.get('name', ''), 'price': stock_data.get('price', 0)}
    try:
        fusion_result = agents['Fusion'].analyze(fusion_input, dl_predictions)
    except Exception as e:
        logger.error(f"Fusion agent failed: {e}")
        fusion_result = {'action': 'hold', 'confidence': 0, 'reasoning': f'Fusion error: {e}'}

    # Validate risk veto
    risk = specialist_results.get('Risk', {})
    if risk.get('veto') and fusion_result.get('action') == 'buy':
        fusion_result['action'] = 'hold'
        veto_reason = risk.get('veto_reason', 'No reason given')
        fusion_result['reasoning'] = f"RISK VETO: {veto_reason}. Original: {fusion_result.get('reasoning', '')}"

    result = {
        'code': stock_data.get('code'),
        'name': stock_data.get('name'),
        'price': stock_data.get('price'),
        'specialists': specialist_results,
        'decision': fusion_result,
        'timestamp': datetime.now().isoformat(),
    }

    set_cache(stock_data.get('code', ''), data_hash, result)
    return result

def _build_fusion_context(stock_data: Dict, specialist_results: Dict,
                           dl_predictions: Dict = None) -> str:
    """Build the fusion agent's input context from specialist outputs."""
    lines = [f"Stock: {stock_data.get('code')} {stock_data.get('name')} @ {stock_data.get('price')}"]

    if dl_predictions:
        st = dl_predictions.get('short_term', {})
        mt = dl_predictions.get('mid_term', {})
        lines.append("\nDL Predictions:")
        lines.append(f"  Short-term: {st.get('direction')} (up:{st.get('prob_up')} down:{st.get('prob_down')}), "
                     f"expected return: {st.get('expected_return')}")
        if mt:
            lines.append(f"  Mid-term: {mt.get('direction')} (up:{mt.get('prob_up')} down:{mt.get('prob_down')}), "
                         f"expected return: {mt.get('expected_return')}")

    for name, result in specialist_results.items():
        lines.append(f"\n{name} Agent:")
        lines.append(f"  Stance: {result.get('stance', 'N/A')}")
        lines.append(f"  Confidence: {result.get('confidence', 0)}")
        if result.get('error'):
            lines.append(f"  Error: {result['error']}")
        if result.get('veto') is not None:
            lines.append(f"  Veto: {result['veto']} ({result.get('veto_reason', '')})")
        if result.get('risk_grade'):
            lines.append(f"  Risk Grade: {result['risk_grade']}")

    return '\n'.join(lines)

def batch_analyze(stocks: List[Dict], dl_predictions_map: Dict[str, Dict] = None,
                  portfolio_context: Dict = None, max_concurrent: int = 5) -> List[Dict]:
    """
    Analyze a batch of stocks with concurrency control.
    max_concurrent limits simultaneous stock analyses to control API rate.
    """
    results = []
    semaphore = concurrent.futures.Semaphore(max_concurrent)

    def analyze_one(stock):
        with semaphore:
            code = stock.get('code')
            dl_pred = (dl_predictions_map or {}).get(code)
            return analyze_stock(stock, dl_pred, portfolio_context)

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrent) as executor:
        futures = [executor.submit(analyze_one, s) for s in stocks]
        for future in concurrent.futures.as_completed(futures):
            try:
                results.append(future.result(timeout=180))
            except Exception as e:
                logger.error(f"Batch analysis job failed: {e}")

    return results
