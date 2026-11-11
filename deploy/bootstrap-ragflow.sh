#!/usr/bin/env bash
# 将 RAGFlow 拉取到同仓 third_party/ragflow，并生成 deploy/ragflow.env
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TARGET="$ROOT_DIR/third_party/ragflow"
TAG="${RAGFLOW_TAG:-v1.0.0-rc2}"
ENV_OUT="$ROOT_DIR/deploy/ragflow.env"

mkdir -p "$ROOT_DIR/third_party"

if [ ! -d "$TARGET/.git" ]; then
  echo "[info] 克隆 RAGFlow ($TAG) → third_party/ragflow ..."
  git clone --depth 1 --branch "$TAG" https://github.com/infiniflow/ragflow.git "$TARGET"
else
  echo "[info] 已存在 third_party/ragflow，跳过克隆"
fi

# 基于官方 .env 生成编排用环境文件，并错开常用端口
if [ ! -f "$TARGET/docker/.env" ]; then
  echo "[error] 未找到 $TARGET/docker/.env"
  exit 1
fi

cp "$TARGET/docker/.env" "$ENV_OUT"

# 端口避免与宿主机其它服务冲突；容器内仍为 80，Agent 用服务名访问
sed -i -E 's/^SVR_WEB_HTTP_PORT=.*/SVR_WEB_HTTP_PORT=8088/' "$ENV_OUT"
sed -i -E 's/^SVR_WEB_HTTPS_PORT=.*/SVR_WEB_HTTPS_PORT=8443/' "$ENV_OUT"
sed -i -E 's/^MINIO_PORT=.*/MINIO_PORT=9100/' "$ENV_OUT"
sed -i -E 's/^MINIO_CONSOLE_PORT=.*/MINIO_CONSOLE_PORT=9101/' "$ENV_OUT"
# 使用较新的 ES/Kibana 标签（Docker Hub 易拉取）
sed -i -E 's/^STACK_VERSION=.*/STACK_VERSION=9.5.5/' "$ENV_OUT"
# 使用 Elasticsearch 8.19.23 作为文档引擎
sed -i -E 's/^DOC_ENGINE=.*/DOC_ENGINE=elasticsearch/' "$ENV_OUT"

# 确保 CPU + ES profile（若文件中已有 COMPOSE_PROFILES 则保留官方逻辑）
if ! grep -q '^DEVICE=' "$ENV_OUT"; then
  echo 'DEVICE=cpu' >> "$ENV_OUT"
fi

echo "[ok] RAGFlow 已就绪: $TARGET"
echo "[ok] 编排环境文件: $ENV_OUT"
echo "     浏览器访问 RAGFlow: http://localhost:8088"
echo "     下一步: ./deploy/start.sh"
