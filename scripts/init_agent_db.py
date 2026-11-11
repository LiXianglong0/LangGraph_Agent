# -*- coding: utf-8 -*-
"""在远程 PostgreSQL 上新建 Agent API 专用库，并初始化 LangGraph checkpoint 表。

用法示例（密码勿写入仓库）：
  set PGHOST=172.30.105.51
  set PGPORT=5432
  set PGUSER=postgres
  set PGPASSWORD=***
  set AGENT_DB_NAME=langgraph_agent
  python scripts/init_agent_db.py
"""

from __future__ import annotations

import os
import sys
from urllib.parse import quote_plus


def main() -> int:
    """创建数据库并执行 checkpointer.setup()。"""
    host = os.getenv("PGHOST", "172.30.105.51")
    port = os.getenv("PGPORT", "5432")
    user = os.getenv("PGUSER", "postgres")
    password = os.getenv("PGPASSWORD", "")
    new_db = os.getenv("AGENT_DB_NAME", "langgraph_agent")

    if not password:
        print("[error] 请设置环境变量 PGPASSWORD", file=sys.stderr)
        return 1

    import psycopg

    admin_uri = (
        f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/postgres"
    )
    print(f"[info] 连接 {host}:{port} ...")
    with psycopg.connect(admin_uri, autocommit=True) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (new_db,))
            exists = cur.fetchone() is not None
            if exists:
                print(f"[info] 数据库已存在: {new_db}")
            else:
                # 新建独立库，与 erpe2eoms 隔离
                cur.execute(
                    f'CREATE DATABASE "{new_db}" OWNER "{user}" ENCODING \'UTF8\''
                )
                print(f"[ok] 已创建数据库: {new_db}")

    db_uri = f"postgresql://{user}:{quote_plus(password)}@{host}:{port}/{new_db}"
    print("[info] 初始化 LangGraph checkpoint 表 ...")
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(db_uri) as checkpointer:
        checkpointer.setup()
    print("[ok] checkpoint 表已就绪")
    print()
    print("请写入项目根目录 .env（已 gitignore）：")
    print(f"DATABASE_URL={db_uri}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
