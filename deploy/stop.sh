#!/usr/bin/env bash
# 停止总栈；加 --volumes 会删除 RAGFlow/Agent 相关数据卷
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR/deploy"

if [ ! -f docker-compose.yml ]; then
  echo "[error] 未找到 deploy/docker-compose.yml"
  exit 1
fi

if [ "${1:-}" = "--volumes" ] || [ "${1:-}" = "-v" ]; then
  echo "[warn] 停止并删除数据卷 ..."
  docker compose --env-file ragflow.env -f docker-compose.yml down -v
else
  echo "[info] 停止服务（保留数据）..."
  docker compose --env-file ragflow.env -f docker-compose.yml down
fi

echo "[ok] 已停止。"
