"""检查点存储：优先 PostgreSQL，未配置 DATABASE_URL 时回退 MemorySaver。"""

from __future__ import annotations

import os
from typing import Any

from langgraph.checkpoint.memory import MemorySaver


def create_checkpointer() -> tuple[Any, Any | None]:
    """创建 checkpointer；若使用 Postgres 则同时返回连接池便于生命周期管理。

    Returns:
        (checkpointer, pool)：pool 仅在 Postgres 模式下非空。
    """
    db_url = (os.getenv("DATABASE_URL") or "").strip()
    if not db_url:
        # 本地调试：进程内记忆
        return MemorySaver(), None

    from langgraph.checkpoint.postgres import PostgresSaver
    from psycopg.rows import dict_row
    from psycopg_pool import ConnectionPool

    # 连接池供 FastAPI 长驻进程使用（勿用 from_conn_string 的 with 块）
    pool = ConnectionPool(
        conninfo=db_url,
        max_size=10,
        kwargs={
            "autocommit": True,
            "prepare_threshold": 0,
            "row_factory": dict_row,
        },
    )
    checkpointer = PostgresSaver(pool)
    # 幂等建表/迁移
    checkpointer.setup()
    return checkpointer, pool
