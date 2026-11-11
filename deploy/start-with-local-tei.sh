#!/usr/bin/env bash
# 可选：RAGFlow + 本机 TEI（需 deploy/tei-models 下已有完整模型）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

export TEI_PROFILE="${TEI_PROFILE:-tei-cpu}"
export TEI_MODEL="${TEI_MODEL:-BAAI/bge-small-en-v1.5}"

echo "[info] TEI_PROFILE=$TEI_PROFILE  TEI_MODEL=$TEI_MODEL"
bash "$ROOT_DIR/deploy/enable-local-embedding.sh"

if ! docker image inspect "infiniflow/text-embeddings-inference:cpu-1.8" >/dev/null 2>&1; then
  echo "[error] 未找到 TEI 镜像，请先: ./deploy/pull-tei-mirror.sh"
  exit 1
fi

echo "[info] 清理冲突 TEI 容器 ..."
docker rm -f docker-tei-cpu-1 2>/dev/null || true

ENV_FILE="$ROOT_DIR/deploy/ragflow.env"
RF_DIR="$ROOT_DIR/third_party/ragflow/docker"
cp "$ENV_FILE" "$RF_DIR/.env"

COMPOSE_PROFILES_NO_TEI="$(
  grep -E '^COMPOSE_PROFILES=' "$RF_DIR/.env" | head -1 \
    | sed -E 's/^COMPOSE_PROFILES=//; s/,tei-(cpu|gpu)//g'
)"
export COMPOSE_PROFILES="$COMPOSE_PROFILES_NO_TEI"

current_map="$(sysctl -n vm.max_map_count 2>/dev/null || echo 0)"
if [ "$current_map" -lt 262144 ]; then
  sudo sysctl -w vm.max_map_count=262144 >/dev/null
fi

cd "$RF_DIR"
echo "[info] 启动 RAGFlow（compose 不含 TEI）..."
docker compose --env-file .env -f docker-compose.yml up -d

bash "$ROOT_DIR/deploy/ensure-local-tei.sh"

echo
echo "[ok] RAGFlow: http://localhost:8088"
echo "     TEI:     http://127.0.0.1:6380"
echo "     Builtin Embedding: $TEI_MODEL"
echo "     停止: ./deploy/stop-ragflow-local.sh"
