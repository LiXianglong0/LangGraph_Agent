# -*- coding: utf-8 -*-
"""向 agentDB 写入 / 更新一条 Agent（供你描述后落库）。

用法：
  .\\.venv\\Scripts\\python.exe scripts\\upsert_agent.py --file path\\to\\agent.json
或管道 / 直接改本文件里的 EXAMPLE 后：
  .\\.venv\\Scripts\\python.exe scripts\\upsert_agent.py
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

# 你描述的新 Agent 可先填在这里，再运行脚本
EXAMPLE = {
    "id": "my_agent",
    "code": "AGENT4",
    "name": "待命名助手",
    "summary": "一句话说明",
    "description": "详细功能说明",
    "features": ["能力1", "能力2"],
    "tags": ["自定义"],
    "tools": None,
    "ragEnabled": False,
    "systemPrompt": "你是某某助手……",
    "flowchart": """flowchart TD
  U[用户] --> A[助手]
  A --> R[回复]""",
    "enabled": True,
    "sortOrder": 40,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", help="Agent JSON 文件路径")
    args = parser.parse_args()

    if args.file:
        payload = json.loads(Path(args.file).read_text(encoding="utf-8"))
    else:
        payload = EXAMPLE

    from api.agent_store import AgentStore
    from agent.checkpoint import create_checkpointer

    _, pool = create_checkpointer()
    store = AgentStore(pool)
    row = store.upsert_agent(payload)
    print(json.dumps(row, ensure_ascii=False, indent=2))
    if pool is not None:
        pool.close()
    print("[ok] 已写入 Agent:", row["id"], row["code"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
