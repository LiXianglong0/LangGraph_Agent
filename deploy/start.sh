#!/usr/bin/env bash
# 启动总栈：Agent API + RAGFlow
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

cd "$DEPLOY_DIR"

if [ ! -f "$DEPLOY_DIR/ragflow.env" ] || [ ! -d "$ROOT_DIR/third_party/ragflow/docker" ]; then
  echo "[error] 请先执行: ./deploy/bootstrap-ragflow.sh"
  exit 1
fi

# Elasticsearch 需要足够的 mmap
current_map="$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)"
if [ "$current_map" -lt 262144 ]; then
  echo "[info] 设置 vm.max_map_count=262144 ..."
  sudo sysctl -w vm.max_map_count=262144 >/dev/null
fi

echo "[info] 启动 langgraph-stack（Agent + RAGFlow）..."
docker compose --env-file ragflow.env -f docker-compose.yml up -d --build

echo
docker compose -f docker-compose.yml ps
echo
echo "[ok] Agent API : http://localhost:${AGENT_API_PORT:-8001}"
echo "     API 文档  : http://localhost:${AGENT_API_PORT:-8001}/docs"
echo "     RAGFlow   : http://localhost:8088"
echo "     Vue 开发  : 仍在宿主机执行 cd web && npm run dev"
