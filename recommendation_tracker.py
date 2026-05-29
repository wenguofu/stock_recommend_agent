#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
推荐结果跟踪系统
追踪 AI 推荐并对比实际走势，形成反馈闭环

数据库模型：RecommendationTrack — 记录每次推荐的详情和回测结果
API：查看推荐准确率、胜率、平均收益
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict

from models import Base, SessionLocal
from sqlalchemy import (
    Column, Integer, String, Float, Boolean, Text, DateTime,
    create_engine,
)
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════
# 数据库模型
# ═══════════════════════════════════════════

class RecommendationTrack(Base):
    """AI推荐跟踪表"""
    __tablename__ = 'recommendation_tracks'

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(10), nullable=False, index=True)
    name = Column(String(50))
    direction = Column(String(10), nullable=False)  # 'buy' / 'sell' / 'hold'
    source = Column(String(50))  # 来源: 'debate', 'single_agent', 'ml_predict', 'strategy'
    source_id = Column(String(100))  # 关联的job_id或agent_id
    target_price = Column(Float)  # 目标价
    stop_loss = Column(Float)  # 止损价
    entry_price = Column(Float)  # 推荐时的当前价
    confidence = Column(String(10))  # 'high'/'medium'/'low'
    horizon_days = Column(Integer, default=5)  # 预测周期
    note = Column(Text)  # 推荐理由摘要
    status = Column(String(20), default='pending')  # pending/tracked/expired/hit/missed
    # 回测结果
    result_price = Column(Float)  # horizon_days后的实际价格
    result_return_pct = Column(Float)  # 实际收益率
    result_hit = Column(Boolean, default=None)  # 是否命中预测方向
    result_checked_at = Column(DateTime)  # 回测检查时间
    created_at = Column(DateTime, default=datetime.now)


# ═══════════════════════════════════════════
# CRUD
# ═══════════════════════════════════════════

def create_track(
    code: str,
    direction: str,
    source: str = 'debate',
    source_id: str = None,
    name: str = None,
    target_price: float = None,
    stop_loss: float = None,
    entry_price: float = None,
    confidence: str = 'medium',
    horizon_days: int = 5,
    note: str = None,
) -> RecommendationTrack:
    """创建推荐跟踪记录"""
    db = SessionLocal()
    try:
        track = RecommendationTrack(
            code=code, name=name, direction=direction,
            source=source, source_id=source_id,
            target_price=target_price, stop_loss=stop_loss,
            entry_price=entry_price, confidence=confidence,
            horizon_days=horizon_days, note=note,
            status='pending'
        )
        db.add(track)
        db.commit()
        db.refresh(track)
        return track
    except Exception as e:
        db.rollback()
        logger.error(f"创建推荐跟踪失败: {e}")
        raise
    finally:
        db.close()


# 最小命中阈值：买入需涨幅>=1% (覆盖成本) 才算命中
MIN_HIT_THRESHOLD = 1.0

def evaluate_tracks(horizon_days: int = None) -> dict:
    """评估所有待检查的推荐记录（比对horizon_days处的实际价格）"""
    db = SessionLocal()
    try:
        # 查询状态为 pending/tracked 且已过预测周期的记录
        h_days = horizon_days or 5
        cutoff_date = datetime.now() - timedelta(days=h_days + 1)
        tracks = db.query(RecommendationTrack).filter(
            RecommendationTrack.status.in_(['pending', 'tracked']),
            RecommendationTrack.created_at <= cutoff_date
        ).all()

        checked = 0
        for track in tracks:
            try:
                from data_fetchers import get_daily_kline
                kline = get_daily_kline(track.code, count=max(60, h_days + 10))
                if kline is None or len(kline) < h_days + 2:
                    continue

                track_horizon = track.horizon_days or h_days

                # 在horizon_days处取价 (不是最新收盘价!)
                entry_date = track.created_at.strftime('%Y-%m-%d')
                # 找入场日期在kline中的位置
                kline_dates = kline['date'].values if 'date' in kline.columns else []
                entry_idx = None
                for idx, d in enumerate(kline_dates):
                    if str(d)[:10] >= entry_date:
                        entry_idx = idx
                        break

                if entry_idx is None:
                    entry_idx = 0

                # 检查是否已过足够天数
                horizon_idx = entry_idx + track_horizon
                if horizon_idx >= len(kline):
                    continue  # 数据不足, 稍后评估

                horizon_price = float(kline['close'].values[horizon_idx])
                track.result_price = horizon_price

                if track.entry_price and track.entry_price > 0:
                    track.result_return_pct = round(
                        (horizon_price / track.entry_price - 1) * 100, 2
                    )

                # 判断命中 (需超过最低阈值)
                if track.result_return_pct is not None:
                    r = track.result_return_pct
                    if track.direction == 'buy' and r >= MIN_HIT_THRESHOLD:
                        track.result_hit = True
                    elif track.direction == 'sell' and r <= -MIN_HIT_THRESHOLD:
                        track.result_hit = True
                    elif track.direction == 'hold' and abs(r) < MIN_HIT_THRESHOLD:
                        track.result_hit = True
                    elif abs(r) < MIN_HIT_THRESHOLD and r != 0:
                        track.result_hit = None
                    else:
                        track.result_hit = False

                track.status = 'hit' if track.result_hit else 'missed'
                track.result_checked_at = datetime.now()
                checked += 1

            except Exception as e:
                logger.warning(f"评估推荐 {track.id} ({track.code})失败: {e}")
                continue

        db.commit()
        return {'checked': checked, 'total_pending': len(tracks)}
    except Exception as e:
        db.rollback()
        logger.error(f"评估推荐记录失败: {e}")
        return {'error': str(e)}
    finally:
        db.close()


def _binomial_pvalue(hits: int, total: int) -> float:
    """二项检验：胜率是否显著高于50%随机猜测"""
    try:
        from scipy.stats import binom_test
        return round(float(binom_test(hits, total, 0.5, alternative='greater')), 6)
    except ImportError:
        # scipy不可用时, 用正态近似
        import math
        if total < 10:
            return 1.0
        p_hat = hits / total
        z = (p_hat - 0.5) / math.sqrt(0.5 * 0.5 / total)
        # 单侧p值 (正态近似)
        return round(1.0 - 0.5 * (1 + math.erf(z / math.sqrt(2))), 6)


def _wilson_ci(hits: int, total: int, z: float = 1.96) -> tuple:
    """Wilson score confidence interval for binomial proportion"""
    import math
    if total == 0:
        return (0.0, 0.0)
    p = hits / total
    denom = 1 + z*z/total
    center = (p + z*z/(2*total)) / denom
    margin = z * math.sqrt((p*(1-p) + z*z/(4*total)) / total) / denom
    return (round(max(0, center - margin) * 100, 1), round(min(1, center + margin) * 100, 1))


def get_track_stats(source: str = None, days: int = 30) -> dict:
    """获取推荐跟踪统计（含统计显著性检验）"""
    db = SessionLocal()
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        query = db.query(RecommendationTrack).filter(
            RecommendationTrack.created_at >= cutoff_date,
            RecommendationTrack.status.in_(['hit', 'missed']),
            RecommendationTrack.result_hit.isnot(None)
        )
        if source:
            query = query.filter(RecommendationTrack.source == source)

        tracks = query.all()
        total = len(tracks)
        if total == 0:
            return {'total': 0, 'message': '暂无评估数据'}

        hits = sum(1 for t in tracks if t.result_hit)
        win_rate = round(hits / total * 100, 1)
        returns = [t.result_return_pct for t in tracks if t.result_return_pct is not None]
        avg_return = round(sum(returns) / len(returns), 2) if returns else 0

        # 统计显著性
        p_value = _binomial_pvalue(hits, total)
        ci_low, ci_high = _wilson_ci(hits, total)
        significant = p_value < 0.05

        # 按来源分组
        by_source = {}
        for t in tracks:
            src = t.source or 'unknown'
            if src not in by_source:
                by_source[src] = {'total': 0, 'hits': 0, 'returns': []}
            by_source[src]['total'] += 1
            if t.result_hit:
                by_source[src]['hits'] += 1
            if t.result_return_pct is not None:
                by_source[src]['returns'].append(t.result_return_pct)

        source_stats = {}
        for src, data in by_source.items():
            src_p = _binomial_pvalue(data['hits'], data['total']) if data['total'] >= 5 else None
            src_ci = _wilson_ci(data['hits'], data['total']) if data['total'] >= 5 else (0, 0)
            source_stats[src] = {
                'total': data['total'],
                'hits': data['hits'],
                'win_rate': round(data['hits'] / data['total'] * 100, 1) if data['total'] else 0,
                'avg_return': round(sum(data['returns']) / len(data['returns']), 2) if data['returns'] else 0,
                'p_value': src_p,
                'ci_95': f"{src_ci[0]}% - {src_ci[1]}%",
            }

        return {
            'total': total,
            'hits': hits,
            'win_rate': win_rate,
            'avg_return': avg_return,
            'ci_95': f"{ci_low}% - {ci_high}%",
            'p_value': p_value,
            'significant': significant,
            'significant_label': '统计显著 (p<0.05)' if significant else '不显著 (p>=0.05)',
            'by_source': source_stats,
            'period_days': days,
        }
    except Exception as e:
        logger.error(f"获取推荐统计失败: {e}")
        return {'error': str(e)}
    finally:
        db.close()


def list_tracks(source: str = None, status: str = None,
                limit: int = 50, offset: int = 0) -> List[Dict]:
    """获取推荐跟踪列表"""
    db = SessionLocal()
    try:
        query = db.query(RecommendationTrack)
        if source:
            query = query.filter(RecommendationTrack.source == source)
        if status:
            query = query.filter(RecommendationTrack.status == status)
        tracks = query.order_by(
            RecommendationTrack.created_at.desc()
        ).limit(limit).offset(offset).all()

        return [{
            'id': t.id, 'code': t.code, 'name': t.name,
            'direction': t.direction, 'source': t.source,
            'entry_price': t.entry_price, 'target_price': t.target_price,
            'result_price': t.result_price,
            'result_return_pct': t.result_return_pct,
            'result_hit': t.result_hit,
            'confidence': t.confidence,
            'status': t.status, 'note': t.note,
            'created_at': t.created_at.isoformat() if t.created_at else None,
            'result_checked_at': t.result_checked_at.isoformat() if t.result_checked_at else None,
        } for t in tracks]
    except Exception as e:
        logger.error(f"获取推荐列表失败: {e}")
        return []
    finally:
        db.close()


# ═══════════════════════════════════════════
# API 路由注册
# ═══════════════════════════════════════════

def register_track_routes(app):
    """注册推荐跟踪API路由"""

    from flask import jsonify, request

    @app.route('/api/track/stats', methods=['GET'])
    def track_stats():
        """获取推荐跟踪统计"""
        source = request.args.get('source')
        days = int(request.args.get('days', 30))
        stats = get_track_stats(source=source, days=days)
        return jsonify({'success': True, 'data': stats})

    @app.route('/api/track/list', methods=['GET'])
    def track_list():
        """获取推荐跟踪列表"""
        source = request.args.get('source')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 50))
        offset = int(request.args.get('offset', 0))
        tracks = list_tracks(source=source, status=status, limit=limit, offset=offset)
        return jsonify({'success': True, 'data': tracks, 'count': len(tracks)})

    @app.route('/api/track/evaluate', methods=['POST'])
    def track_evaluate():
        """触发评估（检查到期的推荐记录）"""
        from flask import request
        horizon_days = int((request.json or {}).get('horizon_days', 5))
        result = evaluate_tracks(horizon_days=horizon_days)
        return jsonify({'success': True, 'data': result})

    @app.route('/api/track/check/<code>', methods=['GET'])
    def track_check_code(code):
        """查询某只股票的所有推荐记录"""
        db = SessionLocal()
        try:
            tracks = db.query(RecommendationTrack).filter(
                RecommendationTrack.code == code
            ).order_by(RecommendationTrack.created_at.desc()).limit(20).all()
            data = [{
                'id': t.id, 'direction': t.direction, 'source': t.source,
                'entry_price': t.entry_price, 'target_price': t.target_price,
                'result_return_pct': t.result_return_pct,
                'result_hit': t.result_hit, 'confidence': t.confidence,
                'status': t.status,
                'created_at': t.created_at.isoformat() if t.created_at else None,
            } for t in tracks]
            return jsonify({'success': True, 'data': data})
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
        finally:
            db.close()

    logger.info("推荐跟踪API已注册")
