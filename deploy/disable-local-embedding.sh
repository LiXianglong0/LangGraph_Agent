#!/usr/bin/env bash
# 关闭本地 TEI：从 ragflow.env 去掉 tei-cpu/tei-gpu（Embedding 改用公网模型时用）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/ragflow.env"

if [ ! -f "$ENV_FILE" ]; then
  echo "[error] 未找到 $ENV_FILE"
  exit 1
fi

python3 - "$ENV_FILE" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
text2, n = re.subn(
    r"^(COMPOSE_PROFILES=.*?)(?:,tei-(?:cpu|gpu))+",
    r"\1",
    text,
    count=1,
    flags=re.M,
)
if n == 0:
    def strip_any(m: re.Match) -> str:
        line = m.group(0)
        if line.lstrip().startswith("#"):
            return line
        return re.sub(r",tei-(cpu|gpu)", "", line)

    text2, n = re.subn(r"^COMPOSE_PROFILES=.*$", strip_any, text, count=1, flags=re.M)

path.write_text(text2, encoding="utf-8")
print("[ok] patched", path, "removed tei profiles, n=", n)
PY

echo "[ok] 已关闭本地 TEI 配置"
grep -E '^(COMPOSE_PROFILES|TEI_MODEL)=' "$ENV_FILE" || true
