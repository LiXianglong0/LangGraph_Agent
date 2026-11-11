#!/usr/bin/env bash
# 仅停止 RAGFlow
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RF_DIR="$ROOT_DIR/third_party/ragflow/docker"

if [ ! -f "$RF_DIR/docker-compose.yml" ]; then
  echo "[error] 未找到 RAGFlow 目录"
  exit 1
fi

# 顺带清理可能由 ensure-local-tei 单独拉起的容器，避免下次 name conflict
docker rm -f docker-tei-cpu-1 2>/dev/null || true

cd "$RF_DIR"
if [ "${1:-}" = "--volumes" ] || [ "${1:-}" = "-v" ]; then
  echo "[warn] 停止 RAGFlow 并删除数据卷 ..."
  docker compose --env-file .env -f docker-compose.yml down -v
else
  echo "[info] 停止 RAGFlow（保留数据）..."
  docker compose --env-file .env -f docker-compose.yml down
fi
echo "[ok] 已停止。"
