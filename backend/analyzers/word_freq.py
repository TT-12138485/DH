"""词频统计与关键词提取。

- 词频：jieba 分词 + 停用词过滤后的计数排行
- 关键词：TF-IDF（以段落为文档）与 TextRank（jieba.analyse）
- 词云：取高频词，供前端 ECharts wordcloud 使用
"""
from __future__ import annotations

from collections import Counter

import jieba.analyse
from sklearn.feature_extraction.text import TfidfVectorizer

from . import preprocessing


def word_frequency(text: str, top_n: int = 200) -> list[dict]:
    """词频排行，返回 [{word, count}]，按 count 降序。"""
    words = preprocessing.tokenize(text)
    counter = Counter(words)
    return [{"word": w, "count": c} for w, c in counter.most_common(top_n)]


def keywords_tfidf(text: str, top_n: int = 20) -> list[dict]:
    """以段落为文档计算 TF-IDF，取全语料均值作为关键词权重。"""
    docs = preprocessing.split_paragraphs(text)
    if not docs:
        return []
    stop = preprocessing.load_stopwords()
    # 用空格连接分词结果，喂给 TfidfVectorizer 的 token_pattern
    corpus = [" ".join(preprocessing.tokenize(d, stop)) for d in docs]
    corpus = [c for c in corpus if c.strip()]
    if len(corpus) < 1:
        return []
    try:
        vec = TfidfVectorizer(token_pattern=r"(?u)\b\w+\b")
        m = vec.fit_transform(corpus)
    except ValueError:
        return []
    vocab = vec.get_feature_names_out()
    scores = m.mean(axis=0).A1  # 每词在所有文档上的平均权重
    ranked = sorted(zip(vocab, scores), key=lambda x: x[1], reverse=True)
    return [{"word": w, "score": round(float(s), 5)} for w, s in ranked[:top_n]]


def keywords_textrank(text: str, top_n: int = 20) -> list[dict]:
    """jieba.analyse.textrank 关键词。"""
    try:
        pairs = jieba.analyse.textrank(text, topK=top_n, withWeight=True)
    except Exception:
        return []
    return [{"word": w, "score": round(float(s), 5)} for w, s in pairs]


def wordcloud_data(text: str, top_n: int = 150) -> list[dict]:
    """词云数据，返回 [{name, value}]。"""
    freq = word_frequency(text, top_n)
    return [{"name": f["word"], "value": f["count"]} for f in freq]


# jieba 词性 → 中文类别分组（实词/虚词合并）
_POS_GROUPS: dict[str, set[str]] = {
    "名词": {"n", "nr", "nrfg", "nrt", "ns", "nt", "nz", "ng", "nl"},
    "动词": {"v", "vd", "vn", "vf", "vx", "vi"},
    "形容词": {"a", "ad", "an", "ag", "al"},
    "副词": {"d", "dg", "df"},
    "代词": {"r", "rr", "rz", "ryt", "rys", "rg"},
    "数词": {"m", "mq"},
    "量词": {"q", "qv", "qt"},
    "介词": {"p", "pba", "pbei"},
    "连词": {"c", "cc"},
    "助词": {"u", "uzhe", "ule", "ugu", "ud", "ude1", "ude2", "ude3", "usuo", "udeng", "uyy", "udh", "uls", "uzhi", "ulian"},
    "语气词": {"y"},
    "叹词": {"e"},
    "拟声词": {"o"},
    "区别词": {"b"},
    "方位词": {"f"},
    "时间词": {"t"},
    "处所词": {"s"},
    "其他": {"x", "w"},
}
# 实词类别（承载语义信息）
_CONTENT_GROUPS = {"名词", "动词", "形容词", "副词", "数词", "量词", "区别词", "方位词", "时间词", "处所词"}

_POS_LOOKUP: dict[str, str] = {}
for _grp, _tags in _POS_GROUPS.items():
    for _t in _tags:
        _POS_LOOKUP[_t] = _grp


def lexical_analysis(text: str, top_n: int = 30) -> dict:
    """词汇结构分析：词性分布、二元搭配、词长分布、实词占比。"""
    stop = preprocessing.load_stopwords()

    # 1) 词性分布
    pos_counter: Counter[str] = Counter()
    total_tokens = 0
    content_tokens = 0
    for word, flag in preprocessing.word_seg_with_pos(text):
        w = word.strip()
        if not w:
            continue
        grp = _POS_LOOKUP.get(flag, "其他")
        pos_counter[grp] += 1
        total_tokens += 1
        if grp in _CONTENT_GROUPS:
            content_tokens += 1
    pos_list = [
        {"pos": g, "count": c, "ratio": round(c / total_tokens, 4) if total_tokens else 0}
        for g, c in pos_counter.most_common()
    ]

    # 2) 二元搭配（句内相邻词对，去停用词）
    bigram_counter: Counter[str] = Counter()
    for sent in preprocessing.split_sentences(text):
        toks = preprocessing.tokenize(sent, stop)
        for i in range(len(toks) - 1):
            bigram_counter[toks[i] + toks[i + 1]] += 1
    bigrams = [{"word": b, "count": c} for b, c in bigram_counter.most_common(top_n)]

    # 3) 词长分布
    len_counter: Counter[int] = Counter()
    for w in preprocessing.tokenize(text, stop):
        len_counter[len(w)] += 1
    word_length = [
        {"length": l, "count": c}
        for l, c in sorted(len_counter.items())
    ]

    return {
        "pos": pos_list,
        "bigrams": bigrams,
        "word_length": word_length,
        "content_ratio": round(content_tokens / total_tokens, 4) if total_tokens else 0,
        "total_tokens": total_tokens,
    }
