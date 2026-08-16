#!/usr/bin/env bash
# 部署脚本：在国内云服务器（需已安装 Docker）上构建并启动服务
# 用法：bash deploy.sh
set -euo pipefail

cd "$(dirname "$0")"

echo "==> 构建镜像"
docker compose build

echo "==> 启动服务"
docker compose up -d

echo "==> 完成，访问 http://<服务器IP>:8000"
echo "    查看日志：docker compose logs -f"
