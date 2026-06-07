#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
AI辩论 + 分析路由模块
从 api_routes.py 提取，包含：
  - AI模型列表/测试
  - 多Agent辩论任务（单股 + 多选一）
  - 单Agent分析
"""
import json
import logging
import re
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

from flask import jsonify, request

logger = logging.getLogger(__name__)

from ai_service import AIService, DEFAULT_MODEL_MAP
from ai_config import get_api_key
from data_fetchers import get_realtime_data, get_news_from_stock, get_guba_posts
from data_formatters import format_for_ai
from technical_indicators import get_comprehensive_data_with_indicators
from models import SessionLocal, get_db
from db import (
    get_config, get_agent,
    get_cached_analysis, save_analysis_cache,
    create_debate_job, get_debate_job, update_debate_job,
    list_debate_jobs, cancel_debate_job, delete_debate_job,
)
from utils import is_valid_stock_code


# ═══════════════════════════════════════════
# 辩论辅助函数
# ═══════════════════════════════════════════

def _parse_decision_json(report_md: str) -> dict:
    """从报告中提取 <decision> JSON 块"""
    import re
    if not report_md:
        return {}
    match = re.search(r'<decision>\s*(\{.*?\})\s*</decision>', report_md, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    return {}


def _serialize_job(job):
    agent_info = {}
    try:
        agent_info = json.loads(job.agent_ids) if job.agent_ids else {}
    except Exception:
        agent_info = {}
    steps = []
    try:
        steps = json.loads(job.steps) if job.steps else []
    except Exception:
        steps = []
    decision = _parse_decision_json(job.report_md or '')
    return {
        'job_id': job.job_id,
        'code': job.code,
        'name': job.name,
        'agent_ids': agent_info.get('agent_ids', []),
        'analysis_rounds': agent_info.get('analysis_rounds', 3),
        'debate_rounds': agent_info.get('debate_rounds', 3),
        'meta': agent_info.get('meta', {}),
        'status': job.status,
        'progress': job.progress,
        'steps': steps,
        'report_md': job.report_md or '',
        'decision': decision,
        'error': job.error,
        'created_at': job.created_at.isoformat() if job.created_at else None,
        'updated_at': job.updated_at.isoformat() if job.updated_at else None,
    }


def _update_debate_job(db, job_id, **kwargs):
    if 'steps' in kwargs and isinstance(kwargs['steps'], list):
        kwargs['steps'] = json.dumps(kwargs['steps'], ensure_ascii=False)
    if 'progress_detail' in kwargs and isinstance(kwargs['progress_detail'], list):
        kwargs['progress_detail'] = json.dumps(kwargs['progress_detail'], ensure_ascii=False)
    update_debate_job(db, job_id, **kwargs)

    # WebSocket 实时推送
    try:
        from websocket_routes import emit_debate_progress, emit_debate_complete
        status = kwargs.get('status', 'running')
        progress = kwargs.get('progress', 0)
        if status == 'completed':
            emit_debate_complete(job_id, kwargs.get('report_md', ''))
        else:
            # 从 progress_detail 获取最新信息
            detail_list = kwargs.get('progress_detail', [])
            last_detail = detail_list[-1] if isinstance(detail_list, list) and detail_list else ''
            emit_debate_progress(job_id, progress, status, detail=str(last_detail))
    except Exception:
        pass  # WebSocket 不可用时静默降级


def _is_job_canceled(db, job_id):
    job = get_debate_job(db, job_id)
    return bool(job and job.canceled)


def _truncate_steps_for_db(steps, max_content_len=200):
    truncated = []
    for s in steps:
        entry = dict(s)
        if isinstance(entry.get('content'), str) and len(entry['content']) > max_content_len:
            entry['content'] = entry['content'][:max_content_len] + '...'
        truncated.append(entry)
    return truncated


def _update_progress_detail(progress_detail_list, phase, round_num, agent_name, current=0, total=0):
    if phase == 'analysis':
        detail = f"第{round_num}轮分析：{agent_name} 正在分析（{current}/{total}）"
    elif phase == 'debate':
        detail = f"第{round_num}轮辩论：{agent_name} 正在辩论（{current}/{total}）"
    elif phase == 'operator':
        detail = "报告生成中..."
    elif phase == 'complete':
        detail = "分析完成！"
    elif phase == 'pending':
        detail = "准备中..."
    else:
        detail = phase
    progress_detail_list.append(detail)


def _resolve_agent_config(db, agent):
    provider = agent.ai_provider or get_config(db, 'default_ai_provider', 'openai')
    api_key = get_config(db, f'{provider}_api_key')
    if not api_key:
        raise ValueError(f'未配置{provider} API Key')
    model = agent.model or get_config(db, f'{provider}_model', DEFAULT_MODEL_MAP.get(provider, 'gpt-3.5-turbo'))
    return provider, api_key, model


def _build_sector_context():
    try:
        from sector_utils import get_latest_sector, format_for_debate, get_holdings_sector_context
        sd = get_latest_sector(n=1)
        if sd and sd.get("sectors"):
            holdings_ctx = get_holdings_sector_context()
            return format_for_debate(sd, holdings_ctx)
    except Exception as e:
        print(f"[Debate] 板块数据加载失败: {e}")
    return ""


def _build_sector_context_simple():
    try:
        from sector_utils import get_latest_sector, format_for_debate
        sd = get_latest_sector(n=1)
        if sd and sd.get("sectors"):
            return format_for_debate(sd)
    except Exception as e:
        print(f"[Debate] 板块数据加载失败: {e}")
    return ""


# ═══════════════════════════════════════════
# 通用辩论轮次执行
# ═══════════════════════════════════════════

def _execute_round(db, job_id, agents, round_idx, num_rounds, phase, build_prompt_fn,
                   analysis_memory=None, debate_history=None, steps=None, progress_detail=None,
                   progress_base=20, progress_range=70):
    """通用辩论轮次执行 — 并行调用所有Agent, 处理结果和进度更新"""

    current_time = datetime.now()
    current_time_info = f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {current_time.strftime('%A')})"

    prompts = []
    for agent in agents:
        prompts.append((
            agent,
            build_prompt_fn(agent, current_time_info, analysis_memory, debate_history),
        ))

    with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
        futures = {
            executor.submit(
                AIService.call_agent,
                *_resolve_agent_config(db, agent),
                prompt
            ): agent
            for agent, prompt in prompts
        }
        for idx, future in enumerate(as_completed(futures)):
            agent = futures[future]
            try:
                result = future.result(timeout=150)
            except Exception as e:
                result = f"[ERROR] {agent.name} {phase} failed: {str(e)}"

            if analysis_memory is not None and agent.id is not None:
                analysis_memory.setdefault(agent.id, []).append(result)

            item = {
                'phase': phase, 'round': round_idx,
                'agent_id': agent.id, 'agent_name': agent.name,
                'content': result, 'timestamp': datetime.now().isoformat()
            }
            (steps or []).append(item)
            if debate_history is not None:
                debate_history.append(item)

            progress = progress_base + (round_idx - 1) * (progress_range // max(num_rounds, 1)) + \
                       (idx * (progress_range // max(num_rounds, 1)) // max(len(prompts), 1))
            _update_progress_detail(progress_detail, phase, round_idx, agent.name, idx + 1, len(prompts))
            _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)


# ═══════════════════════════════════════════
# 单股辩论执行
# ═══════════════════════════════════════════

def _run_debate_job(job_id, code_str, agent_ids, analysis_rounds, debate_rounds, position=None):
    db = SessionLocal()
    try:
        progress_detail = []
        _update_progress_detail(progress_detail, 'pending', 0, '', 0, len(agent_ids))
        _update_debate_job(db, job_id, status='running', progress=5, progress_detail=progress_detail)

        agents = []
        for agent_id in agent_ids:
            agent = get_agent(db, agent_id)
            if not agent or not agent.enabled:
                raise ValueError(f'Agent不存在或未启用: {agent_id}')
            agents.append(agent)

        position_context = ""
        if position:
            shares = position.get('shares', 0)
            cost = position.get('cost', 0)
            position_context = (
                f"\n\n## User Position Info (IMPORTANT - consider this in your analysis)\n"
                f"The user HOLDS this stock with the following position:\n"
                f"- Shares: {shares} 股\n"
                f"- Cost basis: {cost} 元/股\n"
                f"- Total cost: {cost * shares:,.2f} 元\n"
                f"- Current P&L is calculable from current_price vs cost_basis\n"
                f"\n"
                f"Your analysis and recommendations MUST account for this real position.\n"
                f"Include specific advice on whether to hold, add, or reduce based on your expertise.\n"
            )

        sector_context = _build_sector_context()

        print(f"[Debate] 获取股票数据: {code_str}")
        stock_data = get_comprehensive_data_with_indicators(code_str)
        formatted_data = format_for_ai(stock_data)

        # 注入基本面数据
        try:
            from fundamental_data import get_fundamental_data_for_ai
            fund_text = get_fundamental_data_for_ai(code_str, db=db)
            formatted_data = fund_text + "\n" + formatted_data
        except Exception:
            pass

        # 注入因子评分
        try:
            from factor_engine import get_rating_text
            factor_text = get_rating_text(code_str)
            formatted_data = formatted_data + "\n" + factor_text
        except Exception:
            pass

        # 舆情数据
        try:
            news_list = get_news_from_stock(code_str, days=7)[:5]
            posts_list = get_guba_posts(code_str, latest_count=5, hot_count=5)
            sentiment_text = (
                "News:\n" + "\n".join([f"- {n.get('title','')}" for n in news_list]) +
                "\n\nPosts:\n" + "\n".join([f"- {p.get('title','')}" for p in posts_list[:10]])
            )
        except Exception as e:
            sentiment_text = f"Sentiment data unavailable: {str(e)}"

        steps = []
        analysis_memory = {agent.id: [] for agent in agents}

        # ── 多轮分析 ──
        for round_idx in range(1, analysis_rounds + 1):
            if _is_job_canceled(db, job_id):
                _update_debate_job(db, job_id, status='canceled')
                return
            current_time = datetime.now()
            current_time_info = f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {current_time.strftime('%A')})"

            prompts = []
            for agent in agents:
                prev_analysis = "\n\n".join(analysis_memory[agent.id][-2:]) if analysis_memory[agent.id] else "None"
                prompts.append((
                    agent,
                    f"{agent.prompt}\n\n"
                    f"{current_time_info}\n\n"
                    f"{sector_context}\n\n"
                    f"Stock Data:\n{formatted_data}\n\n"
                    f"Sentiment Data:\n{sentiment_text}\n\n"
                    f"{position_context}\n\n"
                    f"Round {round_idx} Analysis:\n"
                    f"Build on your previous analysis and provide new insights without repetition.\n\n"
                    f"Previous Analysis (if any):\n{prev_analysis}\n\n"
                    f"Please provide your analysis in Chinese."
                ))

            with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                futures = {
                    executor.submit(
                        AIService.call_agent,
                        *_resolve_agent_config(db, agent),
                        prompt
                    ): agent
                    for agent, prompt in prompts
                }
                for idx, future in enumerate(as_completed(futures)):
                    agent = futures[future]
                    try:
                        result = future.result(timeout=150)
                    except Exception as e:
                        result = f"[ERROR] {agent.name} analysis failed: {str(e)}"
                    analysis_memory[agent.id].append(result)
                    steps.append({
                        'phase': 'analysis', 'round': round_idx,
                        'agent_id': agent.id, 'agent_name': agent.name,
                        'content': result, 'timestamp': datetime.now().isoformat()
                    })
                    progress = 20 + (round_idx - 1) * (70 // max(analysis_rounds, 1))
                    _update_progress_detail(progress_detail, 'analysis', round_idx, agent.name, idx + 1, len(prompts))
                    _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

        # ── 多轮辩论 ──
        debate_history = []
        for round_idx in range(1, debate_rounds + 1):
            if _is_job_canceled(db, job_id):
                _update_debate_job(db, job_id, status='canceled')
                return
            current_time = datetime.now()
            current_time_info = f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {current_time.strftime('%A')})"

            prompts = []
            other_latest = "\n\n".join([
                f"{a.name}:\n{analysis_memory[a.id][-1]}"
                for a in agents if analysis_memory[a.id]
            ])
            recent_debate = "\n\n".join([
                f"Round {item['round']} - {item['agent_name']}:\n{item['content']}"
                for item in debate_history[-min(len(debate_history), len(agents) * 2):]
            ]) if debate_history else "None"

            for agent in agents:
                prompts.append((
                    agent,
                    f"{agent.prompt}\n\n"
                    f"{current_time_info}\n\n"
                    f"{sector_context}\n\n"
                    "You are participating in a multi-agent debate.\n\n"
                    f"Debate Round {round_idx}:\n"
                    "Respond with counterarguments, supporting evidence, and actionable insights.\n"
                    "Focus on your unique perspective and address opposing viewpoints.\n\n"
                    f"Other agents' latest analyses:\n{other_latest}\n\n"
                    f"Recent Debate History:\n{recent_debate}\n\n"
                    f"{position_context}\n\n"
                    "Please provide your debate response in Chinese."
                ))

            with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                futures = {
                    executor.submit(
                        AIService.call_agent,
                        *_resolve_agent_config(db, agent),
                        prompt
                    ): agent
                    for agent, prompt in prompts
                }
                for idx, future in enumerate(as_completed(futures)):
                    agent = futures[future]
                    try:
                        result = future.result(timeout=150)
                    except Exception as e:
                        result = f"[ERROR] {agent.name} debate failed: {str(e)}"
                    item = {
                        'phase': 'debate', 'round': round_idx,
                        'agent_id': agent.id, 'agent_name': agent.name,
                        'content': result, 'timestamp': datetime.now().isoformat()
                    }
                    debate_history.append(item)
                    steps.append(item)
                    progress = 60 + (round_idx - 1) * (30 // max(debate_rounds, 1))
                    _update_progress_detail(progress_detail, 'debate', round_idx, agent.name, idx + 1, len(prompts))
                    _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

        # ── Operator最终报告 ──
        operator_provider = get_config(db, 'default_ai_provider', 'openai')
        operator_api_key = get_config(db, f'{operator_provider}_api_key')
        if not operator_api_key:
            raise ValueError(f'未配置{operator_provider} API Key')
        operator_model = get_config(db, f'{operator_provider}_model', DEFAULT_MODEL_MAP.get(operator_provider, 'gpt-3.5-turbo'))

        transcript = "\n\n".join([
            f"[{item['phase']} R{item['round']}] {item['agent_name']}:\n{item['content']}"
            for item in steps
        ])

        operator_prompt = (
            "You are a senior trading operator and debate recorder.\n"
            "Based on the multi-agent analysis and debate transcript, produce a final research report in Markdown.\n\n"
            "## REQUIRED OUTPUT STRUCTURE:\n\n"
            "### TL;DR Decision Summary (MUST be first section):\n"
            "A one-paragraph executive summary followed by a structured decision table:\n"
            "| 维度 | 判断 | 置信度 |\n"
            "|------|------|--------|\n"
            "| 方向 | 看多/看空/中性 | 高/中/低 |\n"
            "| 短期(1周) | 买入/持有/卖出 | 高/中/低 |\n"
            "| 中期(1月) | 买入/持有/卖出 | 高/中/低 |\n"
            "| 推荐仓位 | X% | — |\n\n"
            "Then the full report with sections: Basic Info, Overview, Key Points by Agent (ALL agents in table), "
            "Debate Summary, Risks, Final Recommendation.\n\n"
            f"## Sector Context\n{sector_context}\n\n"
            "CRITICAL - Sentiment & Sentient Trading Considerations:\n"
            "1. The analysis includes a 游资情绪Agent. Take this agent's perspective SERIOUSLY.\n"
            "2. If 游资情绪Agent identifies phase (b) Skepticism or (c) Gradual Conviction, lean BULLISH.\n"
            "3. If 游资情绪Agent identifies phase (d) FOMO, advocate for 'hold with trailing stop'.\n"
            "4. Only if phase (e) Exhaustion AND technical danger signals → recommend 'full exit'.\n"
            "5. Your final recommendation should be GRADUAL with clear price targets and stop levels.\n\n"
            "IMPORTANT: Include '## 目标价与操作时间线' with this exact table:\n"
            "| 时间节点 | 目标价 | 操作建议 | 逻辑 |\n"
            "|---------|--------|---------|------|\n"
            "| 1周内 | xx.xx | 操作 | 理由 |\n"
            "| 1个月 | xx.xx | 操作 | 理由 |\n"
            "| 3个月 | xx.xx | 操作 | 理由 |\n"
            "| 6个月 | xx.xx | 操作 | 理由 |\n"
            "| 1年 | xx.xx | 操作 | 理由 |\n\n"
            "IMPORTANT: Include '## 安全买入区间' with this exact table:\n"
            "| 买入场景 | 价格区间 | 条件 | 仓位建议 |\n"
            "|---------|---------|------|---------|\n"
            "| 激进买点 | xx.xx - xx.xx | 条件 | 仓位 |\n"
            "| 稳健买点 | xx.xx - xx.xx | 条件 | 仓位 |\n"
            "| 左侧买点 | xx.xx - xx.xx | 条件 | 仓位 |\n"
            "If no safe buy zone exists, state \"当前价格过高，暂无安全买入区间，建议观望等待回调\".\n"
            f"{position_context}\n"
            f"Stock Data (key fields):\n{formatted_data}\n\n"
            f"Sentiment Summary:\n{sentiment_text}\n\n"
            f"Transcript:\n{transcript}\n\n"
            "Please output the report in Chinese.\n\n"
            "## CRITICAL: Structured Decision Block\n"
            "At the very END of your report, include a machine-readable JSON decision block "
            "wrapped in <decision> and </decision> tags. This is the single most important "
            "part of your output — it will be parsed by the system to track recommendation accuracy.\n\n"
            "Format EXACTLY:\n"
            "<decision>\n"
            "{\n"
            '  "direction": "bullish|bearish|neutral",\n'
            '  "confidence": "high|medium|low",\n'
            '  "action": "buy|sell|hold|reduce",\n'
            '  "position_pct": 30,\n'
            '  "target_price_1w": 15.50,\n'
            '  "target_price_1m": 16.80,\n'
            '  "stop_loss": 13.50,\n'
            '  "key_reason": "一句话核心理由"\n'
            "}\n"
            "</decision>\n"
        )

        try:
            _update_progress_detail(progress_detail, 'operator', 0, '')
            _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress_detail=progress_detail)
            report_md = AIService.call_agent(operator_provider, operator_api_key, operator_model, operator_prompt)
            _update_progress_detail(progress_detail, 'complete', 0, '')
            _update_debate_job(db, job_id, status='completed', progress=100, report_md=report_md,
                              steps=steps, progress_detail=progress_detail, error=None)

            # 自动创建推荐跟踪记录
            try:
                from recommendation_tracker import create_track
                current_price = None
                try:
                    stock_data = get_comprehensive_data_with_indicators(code_str)
                    current_price = stock_data.get('realtime', {}).get('price')
                except Exception:
                    pass
                # 尝试从报告提取方向
                direction = 'buy'  # default
                if '看空' in (report_md or '')[:500]:
                    direction = 'sell'
                create_track(
                    code=code_str, direction=direction,
                    source='debate', source_id=job_id,
                    entry_price=float(current_price) if current_price else None,
                    confidence='medium', horizon_days=7,
                    note=(report_md or '')[:200],
                )
            except Exception:
                pass  # 跟踪记录不是关键路径
        except Exception as e:
            fallback_report = (
                "## 报告生成失败（已提供原始记录）\n\n"
                f"- Error: {str(e)}\n\n"
                "### 原始辩论记录（节选）\n\n"
                f"{transcript[:8000]}\n\n"
                "请稍后重试生成报告。"
            )
            _update_progress_detail(progress_detail, 'complete', 0, '')
            _update_debate_job(db, job_id, status='completed', progress=100, report_md=fallback_report,
                              steps=steps, progress_detail=progress_detail, error=None)
    except Exception as e:
        error_msg = str(e)
        print(f"[Debate] 辩论分析失败: {error_msg}")
        _update_debate_job(db, job_id, status='failed', error=error_msg)
    finally:
        db.close()


def _run_multi_select_job(job_id, codes, agent_ids, analysis_rounds, debate_rounds):
    db = SessionLocal()
    try:
        progress_detail = []
        _update_progress_detail(progress_detail, 'pending', 0, '', 0, len(agent_ids))
        _update_debate_job(db, job_id, status='running', progress=5, progress_detail=progress_detail)

        agents = []
        for agent_id in agent_ids:
            agent = get_agent(db, agent_id)
            if not agent or not agent.enabled:
                raise ValueError(f'Agent不存在或未启用: {agent_id}')
            agents.append(agent)

        operator_provider = get_config(db, 'default_ai_provider', 'openai')
        operator_api_key = get_config(db, f'{operator_provider}_api_key')
        if not operator_api_key:
            raise ValueError(f'未配置{operator_provider} API Key')
        operator_model = get_config(db, f'{operator_provider}_model', DEFAULT_MODEL_MAP.get(operator_provider, 'gpt-3.5-turbo'))

        stock_blocks = []
        for code_str in codes:
            try:
                stock_data = get_comprehensive_data_with_indicators(code_str)
                formatted = format_for_ai(stock_data)
                stock_name = ''
                try:
                    stock_name = stock_data.get('realtime', {}).get('name', '')
                except Exception:
                    stock_name = ''
                stock_blocks.append(f"Stock {code_str} {stock_name}:\n{formatted}")
            except Exception as e:
                stock_blocks.append(f"Stock {code_str}:\nData unavailable: {str(e)}")

        combined_data = "\n\n".join(stock_blocks)
        sector_context = _build_sector_context_simple()

        multi_instruction = (
            "You must choose exactly ONE stock to invest in from the list below. "
            "A capital MUST be allocated to one of these stocks. "
            "Provide your preferred choice and reasoning from your unique perspective."
        )

        steps = []
        analysis_memory = {agent.id: [] for agent in agents}

        # 多轮分析
        for round_idx in range(1, analysis_rounds + 1):
            if _is_job_canceled(db, job_id):
                _update_debate_job(db, job_id, status='canceled')
                return
            current_time = datetime.now()
            current_time_info = f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {current_time.strftime('%A')})"

            prompts = []
            for agent in agents:
                prev_analysis = "\n\n".join(analysis_memory[agent.id][-2:]) if analysis_memory[agent.id] else "None"
                prompts.append((
                    agent,
                    f"{agent.prompt}\n\n{current_time_info}\n\n{sector_context}\n\n"
                    f"Multi-Stock Selection Task:\n{combined_data}\n\n"
                    f"{multi_instruction}\n\n"
                    f"Round {round_idx} Analysis:\n"
                    "Provide new insights and clearly state your preferred stock.\n\n"
                    f"Previous Analysis (if any):\n{prev_analysis}\n\n"
                    "Please provide your analysis in Chinese."
                ))

            with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                futures = {
                    executor.submit(AIService.call_agent, *_resolve_agent_config(db, agent), prompt): agent
                    for agent, prompt in prompts
                }
                for idx, future in enumerate(as_completed(futures)):
                    agent = futures[future]
                    try:
                        result = future.result(timeout=150)
                    except Exception as e:
                        result = f"[ERROR] {agent.name} analysis failed: {str(e)}"
                    analysis_memory[agent.id].append(result)
                    steps.append({
                        'phase': 'analysis', 'round': round_idx,
                        'agent_id': agent.id, 'agent_name': agent.name,
                        'content': result, 'timestamp': datetime.now().isoformat()
                    })
                    progress = 20 + (round_idx - 1) * (70 // max(analysis_rounds, 1))
                    _update_progress_detail(progress_detail, 'analysis', round_idx, agent.name, idx + 1, len(prompts))
                    _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

        # 多轮辩论
        debate_history = []
        for round_idx in range(1, debate_rounds + 1):
            if _is_job_canceled(db, job_id):
                _update_debate_job(db, job_id, status='canceled')
                return
            current_time = datetime.now()
            current_time_info = f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {current_time.strftime('%A')})"

            prompts = []
            other_latest = "\n\n".join([
                f"{a.name}:\n{analysis_memory[a.id][-1]}"
                for a in agents if analysis_memory[a.id]
            ])
            recent_debate = "\n\n".join([
                f"Round {item['round']} - {item['agent_name']}:\n{item['content']}"
                for item in debate_history[-min(len(debate_history), len(agents) * 2):]
            ]) if debate_history else "None"

            for agent in agents:
                prompts.append((
                    agent,
                    f"{agent.prompt}\n\n{current_time_info}\n\n"
                    "You are participating in a multi-agent debate for a multi-stock selection task.\n"
                    f"{multi_instruction}\n\n"
                    f"Debate Round {round_idx}:\n"
                    "Respond with counterarguments and emphasize your preferred stock.\n\n"
                    f"Other agents' latest analyses:\n{other_latest}\n\n"
                    f"Recent Debate History:\n{recent_debate}\n\n"
                    "Please provide your debate response in Chinese."
                ))

            with ThreadPoolExecutor(max_workers=min(6, len(prompts))) as executor:
                futures = {
                    executor.submit(AIService.call_agent, *_resolve_agent_config(db, agent), prompt): agent
                    for agent, prompt in prompts
                }
                for idx, future in enumerate(as_completed(futures)):
                    agent = futures[future]
                    try:
                        result = future.result(timeout=150)
                    except Exception as e:
                        result = f"[ERROR] {agent.name} debate failed: {str(e)}"
                    item = {
                        'phase': 'debate', 'round': round_idx,
                        'agent_id': agent.id, 'agent_name': agent.name,
                        'content': result, 'timestamp': datetime.now().isoformat()
                    }
                    debate_history.append(item)
                    steps.append(item)
                    progress = 60 + (round_idx - 1) * (30 // max(debate_rounds, 1))
                    _update_progress_detail(progress_detail, 'debate', round_idx, agent.name, idx + 1, len(prompts))
                    _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress=progress, progress_detail=progress_detail)

        # 决策结论
        transcript = "\n\n".join([
            f"[{item['phase']} R{item['round']}] {item['agent_name']}:\n{item['content']}"
            for item in steps
        ])

        decision_prompt = (
            "You are a decisive, ruthless senior trader and final decision maker.\n"
            "You must choose exactly ONE stock to buy from the candidates.\n"
            "Be bold, concise, and action-oriented. No hedging.\n\n"
            f"Candidates:\n{combined_data}\n\n"
            f"Debate Transcript:\n{transcript}\n\n"
            "Output a Markdown report with sections: Final Choice, Rationale, Entry Plan, Risk Control.\n"
            "Please output in Chinese."
        )

        try:
            _update_progress_detail(progress_detail, 'operator', 0, '')
            _update_debate_job(db, job_id, steps=_truncate_steps_for_db(steps), progress_detail=progress_detail)
            report_md = AIService.call_agent(operator_provider, operator_api_key, operator_model, decision_prompt)
            steps.append({
                'phase': 'debate', 'round': debate_rounds + 1,
                'agent_id': 0, 'agent_name': "裁判（决策）",
                'content': report_md, 'timestamp': datetime.now().isoformat()
            })
            _update_progress_detail(progress_detail, 'complete', 0, '')
            _update_debate_job(db, job_id, status='completed', progress=100, report_md=report_md,
                              steps=steps, progress_detail=progress_detail, error=None)
        except Exception as e:
            fallback_report = (
                "## 决策生成失败（已提供原始记录）\n\n"
                f"- Error: {str(e)}\n\n"
                "### 原始辩论记录（节选）\n\n"
                f"{transcript[:8000]}\n\n"
                "请稍后重试生成决策报告。"
            )
            steps.append({
                'phase': 'debate', 'round': debate_rounds + 1,
                'agent_id': 0, 'agent_name': "裁判（决策）",
                'content': fallback_report, 'timestamp': datetime.now().isoformat()
            })
            _update_progress_detail(progress_detail, 'complete', 0, '')
            _update_debate_job(db, job_id, status='completed', progress=100, report_md=fallback_report,
                              steps=steps, progress_detail=progress_detail, error=None)

    except Exception as e:
        error_msg = str(e)
        print(f"[Debate] 多选一辩论失败: {error_msg}")
        _update_debate_job(db, job_id, status='failed', error=error_msg)
    finally:
        db.close()


def _parse_intraday_t_prices(text: str):
    """从文本中解析买入卖出价格"""
    try:
        buy_match = re.search(r'买入[价格]?[：:]\s*(\d+\.?\d*)', text)
        sell_match = re.search(r'卖出[价格]?[：:]\s*(\d+\.?\d*)', text)
        buy_price = float(buy_match.group(1)) if buy_match else None
        sell_price = float(sell_match.group(1)) if sell_match else None
        return buy_price, sell_price
    except Exception:
        return None, None


# ═══════════════════════════════════════════
# 路由注册
# ═══════════════════════════════════════════

def register_debate_routes(app):
    # 修复 ARCH-07: 在 LLM 端点挂载 rate_limit 装饰器,防止 LLM 暴力刷
    from rate_limiter import rate_limit

    @app.route('/api/ai/models', methods=['GET'])
    @rate_limit('default')
    def get_ai_models():
        """获取指定AI提供商的可用模型列表"""
        try:
            provider = request.args.get('provider')
            api_key = request.args.get('api_key')

            if not provider:
                return jsonify({'success': False, 'error': '缺少provider参数'}), 400

            if not api_key:
                db = next(get_db())
                try:
                    api_key_key = f'{provider}_api_key'
                    api_key = get_config(db, api_key_key)
                finally:
                    db.close()

            if not api_key:
                return jsonify({'success': False, 'error': '未配置API Key'}), 400

            models = AIService.get_models(provider, api_key)
            return jsonify({'success': True, 'data': models})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取模型列表失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/test', methods=['POST'])
    @rate_limit('ai_analyze')
    def test_ai_connection():
        """测试AI服务连接"""
        try:
            data = request.json
            provider = data.get('provider')
            api_key = data.get('api_key')
            model = data.get('model')

            if not provider or not api_key:
                return jsonify({'success': False, 'error': '缺少provider或api_key参数'}), 400

            result = AIService.test_connection(provider, api_key, model)
            return jsonify(result)
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 测试连接失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/start/<code>', methods=['POST'])
    @rate_limit('debate_start')
    def start_debate_job_api(code):
        """启动多Agent辩论任务（后台执行）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            data = request.json or {}
            agent_ids = data.get('agent_ids', [])
            analysis_rounds = int(data.get('analysis_rounds', 3))
            debate_rounds = int(data.get('debate_rounds', 3))
            position = data.get('position', None)

            if not isinstance(agent_ids, list) or len(agent_ids) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2个Agent参与辩论'}), 400

            job_id = str(uuid.uuid4())
            try:
                realtime = get_realtime_data(code_str)
                stock_name = realtime.get('name') if isinstance(realtime, dict) else None
            except Exception:
                stock_name = None
            job_name = f"{stock_name or code_str} {datetime.now().strftime('%Y-%m-%d')}"

            db = next(get_db())
            try:
                meta = data.get('meta', {})
                if position:
                    meta['position'] = position
                create_debate_job(db, job_id, code_str, job_name, agent_ids, analysis_rounds, debate_rounds, meta=meta)
            finally:
                db.close()

            thread = threading.Thread(
                target=_run_debate_job,
                args=(job_id, code_str, agent_ids, analysis_rounds, debate_rounds, position),
                daemon=True
            )
            thread.start()

            return jsonify({'success': True, 'data': {'job_id': job_id, 'name': job_name}})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 启动辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/start_multi', methods=['POST'])
    @rate_limit('debate_start')
    def start_multi_debate_job_api():
        """启动多选一辩论任务（后台执行）"""
        try:
            data = request.json or {}
            codes = data.get('codes', [])
            agent_ids = data.get('agent_ids', [])
            analysis_rounds = int(data.get('analysis_rounds', 2))
            debate_rounds = int(data.get('debate_rounds', 1))

            if not isinstance(codes, list) or len(codes) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2只股票'}), 400
            if not isinstance(agent_ids, list) or len(agent_ids) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2个Agent参与辩论'}), 400
            codes = [str(c).strip() for c in codes if str(c).strip()]
            if not all(code.isdigit() and len(code) == 6 for code in codes):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            job_id = str(uuid.uuid4())
            job_name = f"多选一: {'/'.join(codes)} {datetime.now().strftime('%Y-%m-%d')}"
            job_code = ",".join(codes)

            db = next(get_db())
            try:
                create_debate_job(
                    db, job_id, job_code, job_name, agent_ids, analysis_rounds, debate_rounds,
                    meta={'mode': 'multi_select', 'codes': codes}
                )
            finally:
                db.close()

            thread = threading.Thread(
                target=_run_multi_select_job,
                args=(job_id, codes, agent_ids, analysis_rounds, debate_rounds),
                daemon=True
            )
            thread.start()

            return jsonify({'success': True, 'data': {'job_id': job_id, 'name': job_name}})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 启动多选一辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/status/<job_id>', methods=['GET'])
    def get_debate_job_status(job_id):
        """查询辩论任务状态"""
        db = next(get_db())
        try:
            job = get_debate_job(db, job_id)
        finally:
            db.close()
        if not job:
            return jsonify({'success': False, 'error': '任务不存在'}), 404
        return jsonify({'success': True, 'data': _serialize_job(job)})

    @app.route('/api/ai/debate/jobs', methods=['GET'])
    def list_debate_jobs_api():
        """获取辩论任务列表"""
        try:
            status = request.args.get('status')
            limit = int(request.args.get('limit', 50))
            db = next(get_db())
            try:
                jobs = list_debate_jobs(db, status=status, limit=limit)
                data = [_serialize_job(job) for job in jobs]
            finally:
                db.close()
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 获取辩论任务列表失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    @app.route('/api/ai/debate/stop/<job_id>', methods=['POST'])
    def stop_debate_job_api(job_id):
        """终止辩论任务"""
        db = next(get_db())
        try:
            job = get_debate_job(db, job_id)
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            if job.status in ['completed', 'failed', 'canceled']:
                return jsonify({'success': False, 'error': '任务已结束，无法终止'}), 400
            cancel_debate_job(db, job_id)
            return jsonify({'success': True})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 终止辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()

    @app.route('/api/ai/debate/delete/<job_id>', methods=['DELETE'])
    def delete_debate_job_api(job_id):
        """删除辩论任务"""
        db = next(get_db())
        try:
            job = get_debate_job(db, job_id)
            if not job:
                return jsonify({'success': False, 'error': '任务不存在'}), 404
            if job.status in ['queued', 'running']:
                return jsonify({'success': False, 'error': '任务进行中，无法删除，请先终止'}), 400
            success = delete_debate_job(db, job_id)
            return jsonify({'success': success})
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 删除辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()

    @app.route('/api/ai/debate/<code>', methods=['POST'])
    def debate_stock_api(code):
        """多Agent分析+辩论（异步——后台执行，立即返回job_id）"""
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            data = request.json or {}
            agent_ids = data.get('agent_ids', [])
            analysis_rounds = int(data.get('analysis_rounds', 3))
            debate_rounds = int(data.get('debate_rounds', 3))
            position = data.get('position', None)

            if not isinstance(agent_ids, list) or len(agent_ids) < 2:
                return jsonify({'success': False, 'error': '至少需要选择2个Agent参与辩论'}), 400

            job_id = str(uuid.uuid4())
            try:
                realtime = get_realtime_data(code_str)
                stock_name = realtime.get('name') if isinstance(realtime, dict) else None
            except Exception:
                stock_name = None
            job_name = f"{stock_name or code_str} {datetime.now().strftime('%Y-%m-%d')}"

            db = next(get_db())
            try:
                meta = data.get('meta', {})
                if position:
                    meta['position'] = position
                create_debate_job(db, job_id, code_str, job_name, agent_ids, analysis_rounds, debate_rounds, meta=meta)
            finally:
                db.close()

            thread = threading.Thread(
                target=_run_debate_job,
                args=(job_id, code_str, agent_ids, analysis_rounds, debate_rounds, position),
                daemon=True
            )
            thread.start()

            return jsonify({
                'success': True,
                'data': {
                    'job_id': job_id, 'name': job_name,
                    'message': '辩论任务已后台提交，轮询 /api/ai/debate/status/<job_id> 获取结果'
                }
            })
        except Exception as e:
            error_msg = str(e)
            print(f"[API] 提交辩论任务失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500

    # ── 单Agent分析 ──

    @app.route('/api/ai/analyze/<code>', methods=['POST'])
    def analyze_stock_api(code):
        """使用Agent分析股票"""
        db = next(get_db())
        try:
            code_str = str(code).strip()
            if not is_valid_stock_code(code_str):
                return jsonify({'success': False, 'error': '股票代码格式错误'}), 400

            data = request.json
            agent_id = data.get('agent_id')
            use_cache = data.get('use_cache', True)

            agent = get_agent(db, agent_id)
            if not agent or not agent.enabled:
                return jsonify({'success': False, 'error': 'Agent不存在或未启用'}), 400

            if use_cache:
                cached = get_cached_analysis(db, code_str, agent.type, max_age_minutes=30)
                if cached:
                    return jsonify({'success': True, 'data': cached, 'cached': True})

            ai_provider = agent.ai_provider or get_config(db, 'default_ai_provider', 'openai')
            api_key_key = f'{ai_provider}_api_key'
            api_key = get_api_key(ai_provider, get_config(db, api_key_key))
            if not api_key:
                return jsonify({'success': False, 'error': f'未配置{ai_provider} API Key'}), 400

            model = agent.model or get_config(db, f'{ai_provider}_model', 'gpt-3.5-turbo')

            print(f"[API] 获取股票数据: {code_str}")
            stock_data = get_comprehensive_data_with_indicators(code_str)
            formatted_data = format_for_ai(stock_data)

            current_time = datetime.now()
            current_time_info = f"Current Time: {current_time.strftime('%Y-%m-%d %H:%M:%S')} (Weekday: {current_time.strftime('%A')})"

            full_prompt = f"{agent.prompt}\n\n{current_time_info}\n\nStock Data:\n{formatted_data}\n\nPlease provide your analysis in Chinese."

            try:
                print(f"[API] 调用AI分析: {agent.name} ({ai_provider})")
                result = AIService.call_agent(ai_provider, api_key, model, full_prompt)

                analysis_result = {
                    'analysis': result,
                    'agent_name': agent.name,
                    'agent_type': agent.type,
                    'timestamp': datetime.now().isoformat()
                }

                if agent.type == 'intraday_t':
                    buy_price, sell_price = _parse_intraday_t_prices(result)
                    if buy_price and sell_price:
                        analysis_result['recommendation'] = {
                            'buy_price': buy_price,
                            'sell_price': sell_price
                        }

                if use_cache:
                    save_analysis_cache(db, code_str, agent.type, analysis_result)

                return jsonify({'success': True, 'data': analysis_result, 'cached': False})
            except Exception as e:
                error_msg = str(e)
                print(f"[API] AI分析失败: {error_msg}")
                return jsonify({'success': False, 'error': f'AI分析失败: {error_msg}'}), 500

        except Exception as e:
            error_msg = str(e)
            print(f"[API] 分析股票失败: {error_msg}")
            return jsonify({'success': False, 'error': error_msg}), 500
        finally:
            db.close()
