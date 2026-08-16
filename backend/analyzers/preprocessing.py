"""文本预处理：词典加载、分词、分段、分句、清洗。

所有词典文件位于 backend/dictionaries/，以 UTF-8 编码。
模块被多个分析器复用，故用模块级缓存避免重复读盘。
"""
from __future__ import annotations

import re
from pathlib import Path

import jieba
import jieba.posseg as pseg

DICT_DIR = Path(__file__).resolve().parent.parent / "dictionaries"

# 标点与空白字符（用于清洗，保留汉字、英文字母、数字）
_PUNCT_RE = re.compile(r"[^一-鿿A-Za-z0-9]+")

# 中文数字、常见无意义单字，用于词频过滤
_EXTRA_STOP = set("一二三四五六七八九十百千万亿零两半几些此之其彼此该等等样般")

_cache: dict[str, object] = {}


def _load_lines(name: str) -> list[str]:
    """按行读取词典文件，去空行与注释。"""
    path = DICT_DIR / name
    items: list[str] = []
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            items.append(line)
    return items


def load_stopwords() -> set[str]:
    if "stopwords" not in _cache:
        words = set(_load_lines("stopwords.txt"))
        words |= _EXTRA_STOP
        # 单字助词/虚词兜底（常见高频虚词单字）
        words |= set("的了是在我你有和就不人都一到说要去会着没看好自己这那他她它们之与及或而但并因所以")
        _cache["stopwords"] = words
    return _cache["stopwords"]  # type: ignore[return-value]


def load_positive_words() -> set[str]:
    if "positive" not in _cache:
        _cache["positive"] = set(_load_lines("positive.txt"))
    return _cache["positive"]  # type: ignore[return-value]


def load_negative_words() -> set[str]:
    if "negative" not in _cache:
        _cache["negative"] = set(_load_lines("negative.txt"))
    return _cache["negative"]  # type: ignore[return-value]


def load_degree_words() -> dict[str, float]:
    """程度副词 -> 权重。"""
    if "degree" not in _cache:
        d: dict[str, float] = {}
        for line in _load_lines("degree_words.txt"):
            parts = line.split()
            if len(parts) >= 2:
                try:
                    d[parts[0]] = float(parts[1])
                except ValueError:
                    continue
        _cache["degree"] = d
    return _cache["degree"]  # type: ignore[return-value]


def load_negation_words() -> set[str]:
    if "negation" not in _cache:
        _cache["negation"] = set(_load_lines("negation_words.txt"))
    return _cache["negation"]  # type: ignore[return-value]


def add_user_words(words: list[str]) -> None:
    """将用户自定义词（如人物名单）加入 jieba，保证分词完整。"""
    for w in words:
        w = (w or "").strip()
        if w:
            jieba.add_word(w, freq=100000, tag="nr")


def split_sentences(text: str) -> list[str]:
    """按句末标点切分句子。"""
    text = re.sub(r"\s+", "", text)
    parts = re.split(r"(?<=[。！？!?；;…])", text)
    return [p.strip() for p in parts if p.strip()]


def split_paragraphs(text: str) -> list[str]:
    """按空行/换行切分段落，过滤过短片段。"""
    raw = re.split(r"\n\s*\n|\r\n\s*\r\n", text)
    out: list[str] = []
    for p in raw:
        p = p.strip()
        if len(p) >= 2:
            out.append(p)
    # 若无空行，退化为按句号聚合（每 2 句一段）以适配单段长文本
    if len(out) <= 1:
        sents = split_sentences(text)
        out = []
        buf = ""
        for i, s in enumerate(sents):
            buf += s
            if (i + 1) % 2 == 0:
                out.append(buf)
                buf = ""
        if buf.strip():
            out.append(buf)
    return [p for p in out if p.strip()]


def tokenize(text: str, stopwords: set[str] | None = None) -> list[str]:
    """分词并去停用词，返回有意义词列表。"""
    stop = stopwords if stopwords is not None else load_stopwords()
    words = jieba.lcut(text)
    return [w for w in words if _keep_word(w, stop)]


def _keep_word(w: str, stop: set[str]) -> bool:
    w = w.strip()
    if len(w) < 2:
        return False
    if w in stop:
        return False
    if _PUNCT_RE.fullmatch(w) or w.isdigit():
        return False
    return True


def clean_text(text: str) -> str:
    """去除多余空白，统一换行。"""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.strip()


def word_seg_with_pos(text: str) -> list[tuple[str, str]]:
    """带词性分词，返回 (词, 词性) 列表。"""
    return list(pseg.cut(text))
