#!/usr/bin/env bash
# 仅启动 RAGFlow（分步调试用，不起 Agent）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
RF_DIR="$ROOT_DIR/third_party/ragflow/docker"
ENV_FILE="$ROOT_DIR/deploy/ragflow.env"

if [ ! -f "$RF_DIR/docker-compose.yml" ]; then
  echo "[error] 未找到 RAGFlow，请先执行: ./deploy/bootstrap-ragflow.sh"
  exit 1
fi
if [ ! -f "$ENV_FILE" ]; then
  echo "[error] 未找到 deploy/ragflow.env，请先执行: ./deploy/bootstrap-ragflow.sh"
  exit 1
fi

# Elasticsearch 需要足够的 mmap
current_map="$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)"
if [ "$current_map" -lt 262144 ]; then
  echo "[info] 设置 vm.max_map_count=262144 ..."
  sudo sysctl -w vm.max_map_count=262144 >/dev/null
fi

# 把编排 env 同步到官方目录，便于直接在该目录 compose
cp "$ENV_FILE" "$RF_DIR/.env"

cd "$RF_DIR"
echo "[info] 仅启动 RAGFlow ..."
docker compose --env-file .env -f docker-compose.yml up -d

echo
docker compose ps
echo
echo "[ok] RAGFlow Web: http://localhost:8088"
echo "     健康检查: curl -f http://localhost:8088/api/v1/system/healthz"
echo "     停用: ./deploy/stop-ragflow.sh"
