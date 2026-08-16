"""词典法情感分析。

思路：
1. 分词后，在情感词附近窗口内寻找程度副词与否定词；
2. 程度副词放大/缩小情感权重，否定词翻转极性；
3. 汇总得到整体倾向，并按分段（段落）计算走势。

词典来源：backend/dictionaries/{positive,negative,degree_words,negation_words}.txt
"""
from __future__ import annotations

from collections import Counter

from . import preprocessing

# 情感词前后查找程度副词/否定词的窗口（词数）
_WINDOW = 4


def _score_sentence(words: list[str], pos: set[str], neg: set[str],
                    degree: dict[str, float], negation: set[str]) -> float:
    """计算单个分词序列的情感得分（>0 积极，<0 消极）。"""
    score = 0.0
    for i, w in enumerate(words):
        if w in pos:
            weight = _apply_modifiers(words, i, degree, negation)
            score += weight
        elif w in neg:
            weight = _apply_modifiers(words, i, degree, negation)
            score -= weight
    return score


def _apply_modifiers(words: list[str], idx: int, degree: dict[str, float],
                     negation: set[str]) -> float:
    """在情感词窗口内累乘程度副词、翻转否定词。"""
    weight = 1.0
    neg_count = 0
    lo = max(0, idx - _WINDOW)
    for w in words[lo:idx]:
        if w in degree:
            weight *= degree[w]
        elif w in negation:
            neg_count += 1
    if neg_count % 2 == 1:
        weight *= -1
    return weight


def _seg_to_words(seg: list[tuple[str, str]]) -> list[str]:
    return [w for w, _ in seg]


def analyze(text: str) -> dict:
    """整体情感 + 分段走势 + 极值段落 + 情感修饰统计。"""
    pos = preprocessing.load_positive_words()
    neg = preprocessing.load_negative_words()
    degree = preprocessing.load_degree_words()
    negation = preprocessing.load_negation_words()

    paragraphs = preprocessing.split_paragraphs(text)
    curve: list[dict] = []
    pos_hits: Counter = Counter()
    neg_hits: Counter = Counter()
    degree_used: Counter = Counter()
    negation_used: Counter = Counter()
    total = 0.0
    best = worst = None

    for i, para in enumerate(paragraphs):
        seg = preprocessing.word_seg_with_pos(para)
        words = _seg_to_words(seg)
        s = _score_sentence(words, pos, neg, degree, negation)
        total += s
        curve.append({"index": i + 1, "score": round(s, 4),
                      "label": _truncate(para, 12)})
        # 收集情感词命中 + 修饰词统计
        for w in words:
            if w in pos:
                pos_hits[w] += 1
            elif w in neg:
                neg_hits[w] += 1
            if w in degree:
                degree_used[w] += 1
            elif w in negation:
                negation_used[w] += 1

        if best is None or s > best[0]:
            best = (s, i + 1, _truncate(para, 60))
        if worst is None or s < worst[0]:
            worst = (s, i + 1, _truncate(para, 60))

    pos_count = sum(pos_hits.values())
    neg_count = sum(neg_hits.values())
    overall = _summarize(total, pos_count, neg_count)

    scores = [c["score"] for c in curve]
    return {
        "overall": overall,
        "curve": curve,
        "positive_words": [{"word": w, "count": c} for w, c in pos_hits.most_common(30)],
        "negative_words": [{"word": w, "count": c} for w, c in neg_hits.most_common(30)],
        "extremes": {
            "most_positive": {"index": best[1], "score": best[0], "text": best[2]} if best else None,
            "most_negative": {"index": worst[1], "score": worst[0], "text": worst[2]} if worst else None,
        },
        "distribution": _histogram(scores),
        "modifiers": {
            "degree_count": sum(degree_used.values()),
            "negation_count": sum(negation_used.values()),
            "degree_words": [{"word": w, "count": c} for w, c in degree_used.most_common(15)],
            "negation_words": [{"word": w, "count": c} for w, c in negation_used.most_common(10)],
        },
    }


def _histogram(scores: list[float], bins: int = 5) -> list[dict]:
    """将段落情感得分分桶，返回 [{range, count}]。"""
    if not scores:
        return []
    lo, hi = min(scores), max(scores)
    if hi - lo < 1e-9:
        return [{"range": f"{lo:.2f}", "count": len(scores)}]
    width = (hi - lo) / bins
    buckets = [0] * bins
    for s in scores:
        idx = min(int((s - lo) / width), bins - 1)
        buckets[idx] += 1
    out = []
    for i, c in enumerate(buckets):
        a = lo + i * width
        b = a + width
        out.append({"range": f"{a:.2f} ~ {b:.2f}", "count": c})
    return out


def _summarize(total: float, pos_count: int, neg_count: int) -> dict:
    """综合得分与倾向标签。"""
    if pos_count + neg_count == 0:
        ratio = 0.5
    else:
        ratio = pos_count / (pos_count + neg_count)
    # 将 [-∞, ∞] 得分压到 [-1, 1]
    norm = 0.0
    if total != 0:
        norm = total / (abs(total) + 3.0)

    if ratio >= 0.6:
        label = "偏积极"
    elif ratio <= 0.4:
        label = "偏消极"
    else:
        label = "中性"

    return {
        "score": round(norm, 4),
        "positive_ratio": round(ratio, 4),
        "positive_count": pos_count,
        "negative_count": neg_count,
        "label": label,
    }


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"
