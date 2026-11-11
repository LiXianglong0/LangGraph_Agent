#!/usr/bin/env bash
# 在 deploy/ragflow.env 中启用本地 TEI Embedding（只改配置，不启动）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT_DIR/deploy/ragflow.env"

# tei-gpu（默认）或 tei-cpu
TEI_PROFILE="${TEI_PROFILE:-tei-cpu}"
# 本机 16G 内存建议 bge-small-en-v1.5；更大内存再试 BAAI/bge-m3
TEI_MODEL="${TEI_MODEL:-BAAI/bge-small-en-v1.5}"

if [ ! -f "$ENV_FILE" ]; then
  echo "[error] 未找到 $ENV_FILE，请先 ./deploy/bootstrap-ragflow.sh"
  exit 1
fi
if [[ "$TEI_PROFILE" != "tei-gpu" && "$TEI_PROFILE" != "tei-cpu" ]]; then
  echo "[error] TEI_PROFILE 只能是 tei-gpu 或 tei-cpu"
  exit 1
fi

echo "[info] TEI_PROFILE=$TEI_PROFILE"
echo "[info] TEI_MODEL=$TEI_MODEL"

# 用 Python 改写，避免模型名中的 / 弄坏 sed
python3 - "$ENV_FILE" "$TEI_PROFILE" "$TEI_MODEL" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
tei_profile = sys.argv[2]
tei_model = sys.argv[3]
text = path.read_text(encoding="utf-8")

# 主 COMPOSE_PROFILES：去掉旧 tei-* 再追加
def patch_profiles(m: re.Match) -> str:
    base = m.group(1)
    base = re.sub(r",tei-(cpu|gpu)", "", base)
    return f"{base},{tei_profile}"

text2, n = re.subn(
    r"^(COMPOSE_PROFILES=\$\{DOC_ENGINE\},\$\{DEVICE\},metadata-\$\{METADATA_DB_PROFILE\})(?:,tei-(?:cpu|gpu))*",
    patch_profiles,
    text,
    count=1,
    flags=re.M,
)
if n == 0:
    # 兜底：任意 COMPOSE_PROFILES= 行（非注释）
    def patch_any(m: re.Match) -> str:
        line = m.group(0)
        if line.lstrip().startswith("#"):
            return line
        line = re.sub(r",tei-(cpu|gpu)", "", line)
        if f",{tei_profile}" not in line and not line.endswith(tei_profile):
            line = line.rstrip() + f",{tei_profile}"
        return line

    text2, n = re.subn(
        r"^COMPOSE_PROFILES=.*$",
        patch_any,
        text,
        count=1,
        flags=re.M,
    )
text = text2

# 注释掉分散启用行
text = re.sub(
    r"^(\s*)COMPOSE_PROFILES=\$\{COMPOSE_PROFILES\},tei-(cpu|gpu)\s*$",
    r"# COMPOSE_PROFILES=${COMPOSE_PROFILES},tei-\2",
    text,
    flags=re.M,
)

# TEI_MODEL=
if re.search(r"^TEI_MODEL=", text, flags=re.M):
    text = re.sub(r"^TEI_MODEL=.*$", f"TEI_MODEL={tei_model}", text, count=1, flags=re.M)
else:
    text = text.rstrip() + f"\nTEI_MODEL={tei_model}\n"

# HF_ENDPOINT
if re.search(r"^#?\s*HF_ENDPOINT=", text, flags=re.M):
    text = re.sub(
        r"^#?\s*HF_ENDPOINT=.*$",
        "HF_ENDPOINT=https://hf-mirror.com",
        text,
        count=1,
        flags=re.M,
    )
else:
    text = text.rstrip() + "\nHF_ENDPOINT=https://hf-mirror.com\n"

path.write_text(text, encoding="utf-8")
print("[ok] patched", path)
PY

echo "[ok] 已更新 $ENV_FILE"
grep -E '^(COMPOSE_PROFILES|TEI_MODEL|HF_ENDPOINT)=' "$ENV_FILE" || true
echo
echo "下一步: ./deploy/start-local-embedding.sh"
# 若镜像已用加速拉好，可直接:
# ./deploy/start-ragflow.sh
