"""中文数字人文分析网站后端。

FastAPI 提供：
- POST /api/analyze   全文分析（词频/关键词/人物网络/情感/主题）
- POST /api/extract   上传 txt/docx/pdf，抽取纯文本
- GET  /api/health    健康检查
- GET  /              托管前端静态页面

启动：uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analyzers import person_network, preprocessing, sentiment, topic, word_freq

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="中文数字人文分析", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class AnalyzeRequest(BaseModel):
    text: str = Field(..., description="待分析的中文文本")
    custom_names: list[str] = Field(default_factory=list, description="自定义人物名单")
    num_topics: int = Field(default=5, ge=2, le=12, description="主题数量")
    top_n: int = Field(default=200, ge=10, le=500, description="词频/关键词数量上限")


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/analyze")
def analyze(req: AnalyzeRequest) -> JSONResponse:
    text = preprocessing.clean_text(req.text)
    if not text:
        return JSONResponse(status_code=400, content={"error": "文本为空"})

    try:
        result = {
            "stats": _stats(text),
            "word_freq": word_freq.word_frequency(text, req.top_n),
            "keywords": {
                "tfidf": word_freq.keywords_tfidf(text, 20),
                "textrank": word_freq.keywords_textrank(text, 20),
            },
            "wordcloud": word_freq.wordcloud_data(text, 150),
            "lexical": word_freq.lexical_analysis(text, 30),
            "person_network": person_network.build_network(text, req.custom_names),
            "sentiment": sentiment.analyze(text),
            "topics": topic.analyze(text, req.num_topics),
        }
        return JSONResponse(content=result)
    except Exception as exc:  # 不让后端崩溃，返回可读错误
        return JSONResponse(status_code=500, content={"error": f"分析失败：{exc}"})


@app.post("/api/extract")
async def extract(file: UploadFile = File(...)) -> JSONResponse:
    """从上传文件抽取纯文本（支持 txt / docx / pdf）。"""
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    data = await file.read()
    if not data:
        return JSONResponse(status_code=400, content={"error": "文件为空"})

    try:
        if suffix in (".txt", ".md", ".text"):
            text = _read_text(data)
        elif suffix == ".docx":
            text = _read_docx(data)
        elif suffix == ".pdf":
            text = _read_pdf(data)
        else:
            return JSONResponse(
                status_code=415,
                content={"error": "暂不支持该格式，请上传 txt / docx / pdf"},
            )
    except Exception as exc:
        return JSONResponse(status_code=500, content={"error": f"解析失败：{exc}"})

    return JSONResponse(content={
        "filename": filename,
        "text": text,
        "chars": len(text),
    })


def _read_text(data: bytes) -> str:
    for enc in ("utf-8", "gb18030", "utf-16"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")


def _read_docx(data: bytes) -> str:
    import io

    import docx

    doc = docx.Document(io.BytesIO(data))
    parts = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(parts)


def _read_pdf(data: bytes) -> str:
    import io

    try:
        import pymupdf  # type: ignore

        doc = pymupdf.open(stream=data, filetype="pdf")
        pages = [page.get_text() for page in doc]
        doc.close()
        return "\n".join(pages)
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(data))
        return "\n".join((page.extract_text() or "") for page in reader.pages)


def _stats(text: str) -> dict:
    paragraphs = preprocessing.split_paragraphs(text)
    sentences = preprocessing.split_sentences(text)
    words = preprocessing.tokenize(text)
    unique = set(words)
    return {
        "chars": len(text.replace("\n", "").replace(" ", "")),
        "paragraphs": len(paragraphs),
        "sentences": len(sentences),
        "words": len(words),
        "unique_words": len(unique),
    }


# 静态前端（挂在根路径；API 路径优先匹配）
if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
