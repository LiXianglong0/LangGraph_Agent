#!/usr/bin/env bash
# 兼容旧名 → 本机 TEI 可选入口
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
exec bash "$ROOT_DIR/deploy/start-with-local-tei.sh"
