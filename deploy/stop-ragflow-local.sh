#!/usr/bin/env bash
# 停止 RAGFlow 栈 + 本机 TEI 容器
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[info] 停止本机 TEI ..."
docker rm -f docker-tei-cpu-1 2>/dev/null || true

echo "[info] 停止 RAGFlow ..."
bash "$ROOT_DIR/deploy/stop-ragflow.sh" "${@:-}"

echo "[ok] 已全部停止"
