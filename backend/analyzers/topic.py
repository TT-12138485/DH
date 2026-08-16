"""LDA 主题建模。

以段落为「文档」，用 sklearn 的 LatentDirichletAllocation 抽取主题。
输出：每个主题的关键词及权重、每段文档的主题分布（供堆叠/热力可视化）。
"""
from __future__ import annotations

import numpy as np
from sklearn.decomposition import LatentDirichletAllocation
from sklearn.feature_extraction.text import CountVectorizer

from . import preprocessing


def analyze(text: str, num_topics: int = 5, top_words: int = 12) -> dict:
    """LDA 主题分析。num_topics 会被限制在 [2, 12]。"""
    docs = preprocessing.split_paragraphs(text)
    docs = [d for d in docs if len(d.strip()) >= 4]
    stop = preprocessing.load_stopwords()
    corpus = [" ".join(preprocessing.tokenize(d, stop)) for d in docs]
    corpus = [c for c in corpus if c.strip()]
    if len(corpus) < 3:
        return {"num_topics": 0, "topics": [], "doc_topics": [],
                "paragraphs": len(corpus), "warning": "文本过短，段落不足，无法有效建模主题"}

    num_topics = max(2, min(int(num_topics), 12, len(corpus)))

    vec = CountVectorizer(token_pattern=r"(?u)\b\w+\b", min_df=1)
    X = vec.fit_transform(corpus)
    vocab = vec.get_feature_names_out()
    n_features = X.shape[1]
    if n_features < 10:
        return {"num_topics": 0, "topics": [], "doc_topics": [],
                "paragraphs": len(corpus), "warning": "词汇量过少，无法建模主题"}

    lda = LatentDirichletAllocation(
        n_components=num_topics,
        max_iter=20,
        learning_method="online",
        random_state=42,
        n_jobs=1,
    )
    doc_topics = lda.fit_transform(X)

    # 整体主题占比（各文档分布求均值）
    topic_weights = doc_topics.mean(axis=0)
    topic_weights = topic_weights / topic_weights.sum() if topic_weights.sum() > 0 else topic_weights
    dominant = doc_topics.argmax(axis=1)  # 每段的主导主题

    try:
        perplexity = float(lda.perplexity(X))
    except Exception:
        perplexity = None

    topics: list[dict] = []
    for k, comp in enumerate(lda.components_):
        idx = np.argsort(comp)[::-1][:top_words]
        total = comp.sum()
        keywords = [
            {"word": str(vocab[i]), "weight": round(float(comp[i] / total), 5)}
            for i in idx
        ]
        topics.append({
            "id": k,
            "keywords": keywords,
            "weight": round(float(topic_weights[k]), 5),
            "doc_count": int((dominant == k).sum()),
        })

    doc_topic_list: list[dict] = []
    for i, dist in enumerate(doc_topics):
        doc_topic_list.append({
            "doc": f"第{i + 1}段",
            "preview": _truncate(docs[i], 14),
            "topics": [round(float(x), 5) for x in dist],
            "dominant": int(dist.argmax()),
            "dominant_weight": round(float(dist.max()), 5),
        })

    # 主题流：按段落顺序的主题分布（供堆叠面积图）
    topic_flow = {
        "labels": [d["doc"] for d in doc_topic_list],
        "series": [
            {
                "name": f"主题{k + 1}",
                "data": [round(float(doc_topics[i][k]), 5) for i in range(len(doc_topics))],
            }
            for k in range(num_topics)
        ],
    }

    return {
        "num_topics": num_topics,
        "topics": topics,
        "doc_topics": doc_topic_list,
        "topic_weights": [round(float(x), 5) for x in topic_weights],
        "topic_flow": topic_flow,
        "perplexity": round(perplexity, 2) if perplexity is not None else None,
        "paragraphs": len(corpus),
    }


def _truncate(s: str, n: int) -> str:
    return s if len(s) <= n else s[:n] + "…"
