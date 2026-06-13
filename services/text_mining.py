"""文本挖掘 — 关键词提取 + 情绪指数

A 股常用正/负词表, 内置停用词, 不引第三方 (jieba 可选, 失败降级到 char bigram).
"""
from typing import List, Dict, Iterable

# A 股常用正面词
POSITIVE = {
    "利好", "业绩", "突破", "增长", "上涨", "新高", "受益", "订单",
    "回购", "分红", "中标", "合作", "签约", "扩产", "放量", "龙头",
    "独家", "优势", "强劲", "创新", "盈利", "扭亏", "提高", "增长",
    "超预期", "看好", "买入", "增持",
}

# A 股常用负面词
NEGATIVE = {
    "利空", "亏损", "下跌", "下滑", "减持", "减仓", "风险", "下调",
    "问询", "处罚", "停牌", "违规", "诉讼", "退市", "不及预期",
    "风险提示", "暴跌", "跌停", "卖出", "看空",
}

# 停用词
STOPWORDS = {
    "的", "了", "和", "是", "在", "有", "我", "你", "他",
    "我们", "你们", "他们", "这", "那", "就", "也", "都",
    "与", "及", "或", "为", "以", "其", "于", "上", "下", "中",
    "对", "从", "到", "把", "被", "将", "应", "能", "可",
}


def _tokenize(text: str) -> Iterable[str]:
    """切词: 优先 jieba, 失败降级到 char bigram (2-gram).

    单字全部过滤 (len < 2), 停用词过滤.
    """
    try:
        import jieba
        for w in jieba.cut(text):
            w = w.strip()
            if len(w) < 2 or w in STOPWORDS:
                continue
            yield w
    except ImportError:
        # 降级: 2-gram, 任一字在停用词表内则丢弃
        text = text.strip()
        for i in range(len(text) - 1):
            w = text[i:i + 2]
            if w in STOPWORDS:
                continue
            # 任一字符是停用单字 → 过滤 (避免"的了" / "在了" 等)
            if w[0] in STOPWORDS or w[1] in STOPWORDS:
                continue
            yield w


def extract_keywords(items: List[str], top: int = 20) -> List[Dict]:
    """提取词频 top N

    items: 字符串列表 (新闻标题 + 帖子标题)
    返回: [{word, count}, ...] 按 count 降序
    """
    counter: Dict[str, int] = {}
    for text in items:
        for w in _tokenize(text):
            counter[w] = counter.get(w, 0) + 1
    return [
        {"word": w, "count": c}
        for w, c in sorted(counter.items(), key=lambda x: -x[1])[:top]
    ]


def sentiment_index(items: List[Dict], days: int = 30) -> List[Dict]:
    """每日情绪指数 (-1 ~ 1)

    items: [{date, title, source}, ...]
    返回: [{date, score, count}, ...] 按 date 升序
    score = (pos - neg) / total, total=0 → 0

    守卫:
      - 空 title 跳过 (避免 zero-division)
      - 仅包含日期前缀 (YYYY-MM-DD)
    """
    by_date: Dict[str, List[float]] = {}
    for it in items:
        d = (it.get("date") or "")[:10]
        if not d:
            continue
        title = (it.get("title") or "").strip()
        if not title:
            continue
        pos = sum(1 for w in POSITIVE if w in title)
        neg = sum(1 for w in NEGATIVE if w in title)
        total = pos + neg
        if total == 0:
            score = 0.0
        else:
            score = (pos - neg) / total
        by_date.setdefault(d, []).append(score)

    return [
        {"date": d, "score": round(sum(s) / len(s), 3), "count": len(s)}
        for d, s in sorted(by_date.items())
    ]