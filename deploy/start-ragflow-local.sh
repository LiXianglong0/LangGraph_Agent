#!/usr/bin/env bash
# 推荐入口：仅启动 RAGFlow（Embedding 用公网模型，不启本机 TEI）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT_DIR"

echo "[info] 关闭本地 TEI 配置（使用公网 Embedding）..."
bash "$ROOT_DIR/deploy/disable-local-embedding.sh"

echo "[info] 停止残留 TEI 容器 ..."
docker rm -f docker-tei-cpu-1 2>/dev/null || true

echo "[info] 启动 RAGFlow ..."
bash "$ROOT_DIR/deploy/start-ragflow.sh"

echo
echo "[info] 等待 RAGFlow ..."
for i in $(seq 1 40); do
  code="$(curl -sS -m 3 -o /dev/null -w '%{http_code}' http://127.0.0.1:8088/api/v1/system/healthz 2>/dev/null || echo 000)"
  if [ "$code" = "200" ]; then
    echo "[ok] RAGFlow 健康检查通过"
    break
  fi
  if [ "$i" -eq 40 ]; then
    echo "[warn] RAGFlow 暂未 200（当前 $code），稍后打开 http://localhost:8088"
  fi
  sleep 3
done

echo
echo "[ok] 启动完成"
echo "     RAGFlow: http://localhost:8088"
echo "     Embedding: 在「模型提供商」使用公网模型（智谱 / 硅基流动等）"
echo "     停止:     ./deploy/stop-ragflow-local.sh"
echo
echo "     若仍要本机 TEI: ./deploy/start-with-local-tei.sh"
