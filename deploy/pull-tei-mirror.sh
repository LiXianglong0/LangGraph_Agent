#!/usr/bin/env bash
# 用国内镜像加速拉取 TEI（约 4GB），再打成官方名供 compose 使用
set -euo pipefail

TAG="${TEI_TAG:-cpu-1.8}"
OFFICIAL="infiniflow/text-embeddings-inference:${TAG}"
# DaoCloud 公共镜像加速（失效时可换其它 mirror）
MIRROR="docker.m.daocloud.io/infiniflow/text-embeddings-inference:${TAG}"

echo "[info] 从镜像加速拉取: $MIRROR"
echo "       （官方名: $OFFICIAL，体积约 4GB，请耐心等待）"
docker pull "$MIRROR"
docker tag "$MIRROR" "$OFFICIAL"
echo "[ok] 已就绪: $OFFICIAL"
docker images "$OFFICIAL"
echo
echo "下一步: ./deploy/start-ragflow.sh"
