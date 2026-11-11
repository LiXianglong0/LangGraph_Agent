#!/usr/bin/env bash
# 启动 Vue 前端（Vite）
set -euo pipefail
cd "$(dirname "$0")"

echo "[info] 启动 Vue 前端..."
if [ ! -d node_modules ]; then
  echo "[info] 安装依赖（npmmirror）..."
  npm install --registry=https://registry.npmmirror.com
fi

echo "[ok] 浏览器打开 http://localhost:5173/"
echo "     后端需另开终端: python -m api.main  （默认端口 8001）"
npm run dev
