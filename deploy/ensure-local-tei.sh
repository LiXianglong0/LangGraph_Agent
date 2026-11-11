#!/usr/bin/env bash
# 确保本机 TEI 可用：清理同名冲突容器，挂载已下载模型，并加入 DNS 别名 tei
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MODEL="${TEI_MODEL:-BAAI/bge-small-en-v1.5}"
MODEL_DIR="$ROOT_DIR/deploy/tei-models/$MODEL"
IMG="infiniflow/text-embeddings-inference:cpu-1.8"
NET="$(docker network ls --format '{{.Name}}' | grep -E '^docker_ragflow$' | head -1 || true)"
NET="${NET:-docker_ragflow}"

if ! docker image inspect "$IMG" >/dev/null 2>&1; then
  echo "[error] 未找到镜像 $IMG"
  echo "        请先: ./deploy/pull-tei-mirror.sh"
  exit 1
fi

if [ ! -f "$MODEL_DIR/config.json" ] || { [ ! -f "$MODEL_DIR/model.safetensors" ] && [ ! -f "$MODEL_DIR/pytorch_model.bin" ]; }; then
  echo "[error] 本地模型不完整: $MODEL_DIR"
  echo "        需要至少 config.json + model.safetensors"
  echo "        可从 hf-mirror 下载到该目录，或保留此前已下载的 bge-small-en-v1.5"
  exit 1
fi

# 已健康则跳过
if curl -fsS -m 3 "http://127.0.0.1:6380/" >/dev/null 2>&1; then
  # 确认 ragflow 能解析 tei
  if docker ps --format '{{.Names}}' | grep -qx 'docker-ragflow-cpu-1'; then
    if docker exec docker-ragflow-cpu-1 getent hosts tei >/dev/null 2>&1; then
      echo "[ok] TEI 已在运行且别名 tei 可用"
      exit 0
    fi
  else
    echo "[ok] TEI 已在运行: http://127.0.0.1:6380"
    exit 0
  fi
fi

echo "[info] 重建 TEI（模型=$MODEL，网络=$NET）..."
docker rm -f docker-tei-cpu-1 2>/dev/null || true

docker run -d --name docker-tei-cpu-1 --hostname tei \
  --network "$NET" --network-alias tei \
  -p 6380:80 \
  -v "$MODEL_DIR:/data/$MODEL:ro" \
  --restart unless-stopped \
  "$IMG" \
  --model-id "/data/$MODEL" --auto-truncate

echo "[info] 等待 TEI ..."
for i in $(seq 1 60); do
  if curl -fsS -m 3 "http://127.0.0.1:6380/" >/dev/null 2>&1; then
    echo "[ok] TEI 就绪: http://127.0.0.1:6380  model=$MODEL"
    exit 0
  fi
  sleep 2
done

echo "[error] TEI 启动超时，日志："
docker logs --tail 40 docker-tei-cpu-1 2>&1 || true
exit 1
