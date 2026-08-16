"""人物识别与人物关系网络。

- 人名识别：jieba.posseg 的 nr 词性 + 用户自定义人物名单
- 关系强度：同一段落内两人共现次数（可扩展到滑动窗口）
- 输出：节点（含频次）与边（含共现次数），供 ECharts graph 绘制
"""
from __future__ import annotations

from collections import Counter

import networkx as nx

from . import preprocessing

# jieba 人名相关词性
_PERSON_POS = {"nr", "nrfg", "nrt", "nrf", "nr1", "nr2", "nri"}


def extract_persons(text: str, custom_names: list[str] | None = None) -> list[dict]:
    """识别文本中出现的人物及频次。"""
    custom = [n.strip() for n in (custom_names or []) if n.strip()]
    if custom:
        preprocessing.add_user_words(custom)

    counter: Counter[str] = Counter()

    # 1) 词性标注识别人名
    for word, flag in preprocessing.word_seg_with_pos(text):
        if flag in _PERSON_POS and len(word) >= 2:
            counter[word] += 1

    # 2) 用户自定义名单（直接全文匹配计数）
    for name in custom:
        if name:
            cnt = text.count(name)
            if cnt > 0:
                counter[name] = max(counter.get(name, 0), cnt)

    return [{"name": n, "freq": c} for n, c in counter.most_common()]


def build_network(text: str, custom_names: list[str] | None = None, max_nodes: int = 60) -> dict:
    """构建人物共现网络。

    返回 {nodes: [{name, value}], links: [{source, target, value}]}
    """
    persons = extract_persons(text, custom_names)
    if not persons:
        return _empty_result()

    # 取高频人物作为节点（控制规模）
    persons = persons[:max_nodes]
    name_freq = {p["name"]: p["freq"] for p in persons}
    name_set = set(name_freq)

    cooccur: Counter[tuple[str, str]] = Counter()
    paragraphs = preprocessing.split_paragraphs(text)
    for para in paragraphs:
        seg = set(preprocessing.word_seg_with_pos(para))
        present = [w for w, f in seg if w in name_set and f in _PERSON_POS]
        present = sorted(set(present))
        for i in range(len(present)):
            for j in range(i + 1, len(present)):
                a, b = present[i], present[j]
                if a != b:
                    cooccur[(a, b)] += 1

    # 构建 networkx 图计算中心性
    G = nx.Graph()
    G.add_nodes_from(name_freq)
    G.add_weighted_edges_from([(a, b, w) for (a, b), w in cooccur.items()])

    degree = dict(G.degree(weight="weight"))  # 加权度 = 关系强度之和
    degree_cent = nx.degree_centrality(G) if len(G) > 0 else {}
    try:
        between = nx.betweenness_centrality(G, normalized=True) if len(G) > 1 else {n: 0.0 for n in G}
    except Exception:
        between = {n: 0.0 for n in G}
    try:
        eigen = nx.eigenvector_centrality(G, max_iter=500) if len(G) > 1 else {n: 0.0 for n in G}
    except Exception:
        eigen = {n: 0.0 for n in G}

    centrality = sorted(
        (
            {
                "name": n,
                "degree": round(float(degree.get(n, 0)), 3),
                "degree_centrality": round(float(degree_cent.get(n, 0)), 4),
                "betweenness": round(float(between.get(n, 0)), 4),
                "eigenvector": round(float(eigen.get(n, 0)), 4),
            }
            for n in name_freq
        ),
        key=lambda x: x["degree"],
        reverse=True,
    )

    # 社区发现（贪心模块度），用于人物聚类
    communities: list[list[str]] = []
    try:
        if len(G) > 1 and G.number_of_edges() > 0:
            for comm in nx.algorithms.community.greedy_modularity_communities(G):
                communities.append(sorted(comm))
    except Exception:
        communities = []

    nodes = [{"name": n, "value": v} for n, v in name_freq.items()]
    links = [
        {"source": a, "target": b, "value": w}
        for (a, b), w in cooccur.most_common()
    ]
    top_relations = [
        {"a": a, "b": b, "value": w}
        for (a, b), w in cooccur.most_common(20)
    ]

    return {
        "nodes": nodes,
        "links": links,
        "top_persons": [{"name": n, "freq": v} for n, v in name_freq.items()],
        "centrality": centrality,
        "top_relations": top_relations,
        "communities": communities,
    }


def _empty_result() -> dict:
    return {
        "nodes": [], "links": [], "top_persons": [],
        "centrality": [], "top_relations": [], "communities": [],
    }
