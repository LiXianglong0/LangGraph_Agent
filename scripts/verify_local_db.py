# -*- coding: utf-8 -*-
"""验证 Agent 是否能连上 .env 中的本机 PostgreSQL。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")


def main() -> int:
    url = (os.getenv("DATABASE_URL") or "").strip()
    if not url:
        print("[error] .env 未配置 DATABASE_URL")
        return 1
    print(f"[info] DATABASE_URL={url}")

    import psycopg

    with psycopg.connect(url) as conn:
        row = conn.execute("SELECT current_user, current_database()").fetchone()
        print(f"[ok] connected as {row[0]} / db={row[1]}")

    from agent.checkpoint import create_checkpointer
    from api.chat_store import ChatStore

    checkpointer, pool = create_checkpointer()
    print(f"[ok] checkpointer={type(checkpointer).__name__}")
    ChatStore(pool)
    print("[ok] chat_store ready")
    if pool is not None:
        pool.close()
    print("[ok] ALL_OK — Agent 已使用本机 PostgreSQL")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
