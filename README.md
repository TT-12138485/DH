# 中文文本数字人文分析网站

一个可部署到公网的中文文本数字人文分析 Web 工具。粘贴或上传中文文本，一键完成：

- **词频统计**：jieba 分词 + 停用词过滤后的高频词排行
- **关键词提取**：TF-IDF 与 TextRank 两种算法
- **词云**：ECharts 词云可视化
- **人物关系网络**：人名识别（词性标注 + 自定义名单）+ 段落共现网络
- **情感分析**：词典法（含程度副词、否定词）+ 分段情感走势
- **主题建模**：LDA 主题聚类 + 段落主题分布热力图

## 技术栈

- 后端：FastAPI + uvicorn
- 文本处理：jieba / scikit-learn
- 前端：原生 HTML/CSS/JS + ECharts（图表自托管，无需 CDN）
- 部署：Docker

## 本地运行

```bash
pip install -r backend/requirements.txt
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

浏览器打开 http://localhost:8000

## Docker 部署到云服务器

1. 把整个 `literary-dh-web` 目录上传到服务器（已安装 Docker）；
2. 在目录内执行：

```bash
bash deploy.sh
# 或手动：
docker compose up -d --build
```

3. 浏览器访问 `http://<服务器IP>:8000`。

如需绑定域名 + HTTPS，可在服务器上再套一层 Nginx/Caddy 反代（`proxy_pass http://127.0.0.1:8000`）。

## 目录结构

```
literary-dh-web/
├── backend/
│   ├── main.py               # FastAPI 入口（API + 静态托管）
│   ├── requirements.txt
│   ├── analyzers/            # 四大分析模块 + 预处理
│   └── dictionaries/         # 停用词 / 情感词典
├── frontend/
│   ├── index.html
│   ├── css/style.css
│   ├── js/app.js
│   └── js/vendor/            # ECharts + wordcloud（自托管）
├── Dockerfile
├── docker-compose.yml
└── deploy.sh
```

## API

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/analyze` | 分析文本，JSON 体：`{"text": "...", "custom_names": [], "num_topics": 5, "top_n": 200}` |
| POST | `/api/extract` | 上传 txt/docx/pdf 抽取纯文本（multipart `file`） |
| GET  | `/api/health` | 健康检查 |

## 说明

- 情感词典为内置常用词典，可替换 `backend/dictionaries/` 下文件扩展词表。
- 单篇长文本的主题建模以「段落」作为文档单元，段落过少时会返回 `warning`。
