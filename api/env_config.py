"""将页面配置写入项目根目录 .env（仅更新白名单键，保留其它行）。"""

from __future__ import annotations

import re
from pathlib import Path

# 允许由 API 写入的环境变量（勿把 DATABASE_URL 等敏感运维项暴露给随意清空）
ALLOWED_KEYS = frozenset(
    {
        "ZHIPU_API_KEY",
        "ZHIPU_MODEL",
        "ZHIPU_BASE_URL",
        "ZHIPU_TEMPERATURE",
        "RAGFLOW_ENABLED",
        "RAGFLOW_BASE_URL",
        "RAGFLOW_API_KEY",
        "RAGFLOW_DATASET_IDS",
    }
)

_ENV_LINE = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$")


def env_path() -> Path:
    """项目根目录 .env 路径。"""
    return Path(__file__).resolve().parents[1] / ".env"


def upsert_env(updates: dict[str, str]) -> Path:
    """按键合并写入 .env；空字符串表示删除该键（若存在）。

    Args:
        updates: 键值对；键必须在 ALLOWED_KEYS 内。

    Returns:
        写入的 .env 路径。
    """
    cleaned: dict[str, str] = {}
    for key, value in updates.items():
        if key not in ALLOWED_KEYS:
            raise ValueError(f"不允许写入的配置项: {key}")
        cleaned[key] = "" if value is None else str(value)

    path = env_path()
    existing_lines: list[str] = []
    if path.is_file():
        existing_lines = path.read_text(encoding="utf-8").splitlines()

    seen: set[str] = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        m = _ENV_LINE.match(stripped)
        if not m:
            new_lines.append(line)
            continue
        key = m.group(1)
        if key in cleaned:
            seen.add(key)
            val = cleaned[key]
            if val == "":
                # 明确清空：跳过该行（删除键）
                continue
            new_lines.append(f"{key}={val}")
        else:
            new_lines.append(line)

    for key, val in cleaned.items():
        if key in seen or val == "":
            continue
        new_lines.append(f"{key}={val}")

    text = "\n".join(new_lines).rstrip() + "\n"
    path.write_text(text, encoding="utf-8")
    return path
