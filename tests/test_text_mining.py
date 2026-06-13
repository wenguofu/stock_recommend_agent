"""TDD Red — 文本挖掘测试

覆盖 design.md text_mining.py 契约:
  - extract_keywords(items, top) → [{word, count}, ...] 按 count 降序
  - sentiment_index(items) → [{date, score, count}, ...]
  - 词表 POSITIVE / NEGATIVE / STOPWORDS
  - 长度 < 2 的词和停用词过滤
"""
import pytest


def test_extract_keywords_basic_frequency():
    from services.text_mining import extract_keywords

    items = [
        "公司业绩增长超出预期",
        "业绩持续增长",
        "新产品利好",
        "业绩利好",
    ]
    kw = extract_keywords(items, top=10)
    # "业绩" 出现 3 次, "增长" 出现 2 次, "利好" 出现 2 次
    by_word = {k["word"]: k["count"] for k in kw}
    assert by_word.get("业绩") == 3
    assert by_word.get("增长") == 2
    assert by_word.get("利好") == 2


def test_extract_keywords_filters_stopwords_and_short():
    from services.text_mining import extract_keywords

    items = ["的了和是的在我你他我们", "把被将应能可"]
    kw = extract_keywords(items, top=10)
    # 单字 + 停用词应全部过滤 (无论 jieba 或 降级 bigram)
    assert kw == []


def test_extract_keywords_top_n_limits_results():
    from services.text_mining import extract_keywords

    items = ["业绩增长利好突破新高订单"]
    kw = extract_keywords(items, top=3)
    assert len(kw) == 3


def test_extract_keywords_sorted_desc():
    from services.text_mining import extract_keywords

    items = ["利好利好", "业绩", "增长增长增长"]
    kw = extract_keywords(items, top=10)
    counts = [k["count"] for k in kw]
    assert counts == sorted(counts, reverse=True)


def test_extract_keywords_empty_input():
    from services.text_mining import extract_keywords

    assert extract_keywords([], top=10) == []


def test_sentiment_index_positive_only_returns_positive_score():
    from services.text_mining import sentiment_index

    items = [
        {"date": "2025-01-01", "title": "公司业绩突破新高, 利好不断"},
        {"date": "2025-01-01", "title": "订单增长超预期"},
    ]
    idx = sentiment_index(items)
    assert len(idx) == 1
    assert idx[0]["score"] > 0


def test_sentiment_index_negative_only_returns_negative_score():
    from services.text_mining import sentiment_index

    items = [
        {"date": "2025-01-02", "title": "公司亏损严重, 面临退市风险"},
        {"date": "2025-01-02", "title": "股价跌停, 利空不断"},
    ]
    idx = sentiment_index(items)
    assert len(idx) == 1
    assert idx[0]["score"] < 0


def test_sentiment_index_grouped_by_date():
    from services.text_mining import sentiment_index

    items = [
        {"date": "2025-01-01", "title": "业绩利好"},
        {"date": "2025-01-02", "title": "亏损利空"},
        {"date": "2025-01-01", "title": "订单增长"},
    ]
    idx = sentiment_index(items)
    dates = [x["date"] for x in idx]
    assert dates == ["2025-01-01", "2025-01-02"]


def test_sentiment_index_empty_title_skipped():
    """空标题不能导致 zero-division"""
    from services.text_mining import sentiment_index

    items = [
        {"date": "2025-01-01", "title": ""},
        {"date": "2025-01-01", "title": "   "},
        {"date": "2025-01-01", "title": "业绩利好"},
    ]
    idx = sentiment_index(items)
    assert len(idx) == 1
    assert idx[0]["score"] > 0


def test_sentiment_index_neutral_returns_zero():
    """正负词都没命中 → score = 0"""
    from services.text_mining import sentiment_index

    items = [{"date": "2025-01-01", "title": "今天发布公告"}]
    idx = sentiment_index(items)
    assert idx[0]["score"] == 0


def test_positive_and_negative_lexicons_have_overlap_guard():
    """POSITIVE 与 NEGATIVE 不应共用词 (避免内部冲突)"""
    from services.text_mining import POSITIVE, NEGATIVE

    assert POSITIVE.isdisjoint(NEGATIVE), "POSITIVE 和 NEGATIVE 词表有交集"