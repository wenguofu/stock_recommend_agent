# llm_agents/agent_base.py
"""Base class for LLM trading agents with structured output and retry logic."""

import json
import time
import logging
from pathlib import Path
from typing import Dict, Optional
from ai_service import AIService
from ai_config import get_api_key

logger = logging.getLogger(__name__)

PROMPT_DIR = Path(__file__).parent / 'agent_prompts'


class TradingAgent:
    """Base agent for stock analysis and decision-making."""

    def __init__(self, name: str, role: str, prompt_file: str,
                 provider: str = 'deepseek', model: str = None):
        self.name = name
        self.role = role
        self.provider = provider
        self.model = model or 'deepseek-chat'
        prompt_path = PROMPT_DIR / prompt_file
        if not prompt_path.exists():
            raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
        with open(prompt_path, 'r', encoding='utf-8') as f:
            self.system_prompt = f.read()

    def build_context(self, stock_data: Dict, dl_predictions: Dict = None) -> str:
        """Build the user message with stock-specific context. Override in subclasses."""
        lines = []
        lines.append(f"Stock: {stock_data.get('code', 'N/A')} {stock_data.get('name', 'N/A')}")
        lines.append(f"Price: {stock_data.get('price', 'N/A')}")
        lines.append(f"Change: {stock_data.get('change_pct', 'N/A')}%")

        if dl_predictions:
            st = dl_predictions.get('short_term', {})
            if st:
                lines.append(f"\nDL Short-term Prediction:")
                lines.append(f"  Direction: {st.get('direction')} (up:{st.get('prob_up')} down:{st.get('prob_down')})")
                lines.append(f"  Expected Return: {st.get('expected_return')} ± {st.get('uncertainty')}")

            mt = dl_predictions.get('mid_term', {})
            if mt:
                lines.append(f"\nDL Mid-term Prediction:")
                lines.append(f"  Direction: {mt.get('direction')} (up:{mt.get('prob_up')} down:{mt.get('prob_down')})")
                lines.append(f"  Expected Return: {mt.get('expected_return')} ± {mt.get('uncertainty')}")

        # Include any additional context
        for key in ['sector', 'market_cap', 'turnover', 'pe_ttm', 'roe', 'portfolio']:
            if key in stock_data and stock_data[key] is not None:
                lines.append(f"\n{key}: {stock_data[key]}")

        return '\n'.join(lines)

    def analyze(self, stock_data: Dict, dl_predictions: Dict = None,
                max_retries: int = 2) -> Dict:
        """Run analysis. Returns structured dict with agent output."""
        api_key = get_api_key(self.provider)
        if not api_key:
            return {'error': f'No API key for {self.provider}', 'confidence': 0, '_agent': self.name}

        context = self.build_context(stock_data, dl_predictions)
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": context},
        ]

        for attempt in range(max_retries + 1):
            try:
                result = AIService.call_agent_structured(
                    self.provider, api_key, self.model, messages,
                )
                result['_agent'] = self.name
                result['_provider'] = self.provider
                return result
            except Exception as e:
                logger.warning(f"Agent {self.name} attempt {attempt+1} failed: {e}")
                if attempt < max_retries:
                    time.sleep(1 + attempt * 2)
                else:
                    return {'error': str(e), 'confidence': 0, '_agent': self.name}
