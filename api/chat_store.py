"""按用户记录会话列表（元数据）；消息正文仍由 LangGraph Checkpointer 按 thread_id 保存。"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# psycopg 的 execute 不能一次跑多条语句，须拆开
_DDL_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS chat_threads (
        user_id    TEXT NOT NULL,
        thread_id  TEXT NOT NULL,
        title      TEXT NOT NULL DEFAULT '新对话',
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        PRIMARY KEY (user_id, thread_id)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_chat_threads_user_updated
        ON chat_threads (user_id, updated_at DESC)
    """,
)


class ChatStore:
    """会话元数据存储：有 DATABASE_URL 用 Postgres，否则用本地 JSON 文件。"""

    def __init__(self, pool: Any | None = None) -> None:
        self._pool = pool
        self._lock = threading.Lock()
        self._file = Path(__file__).resolve().parents[1] / "data" / "chat_threads.json"
        if self._pool is not None:
            self._setup_pg()

    def _setup_pg(self) -> None:
        with self._pool.connection() as conn:
            for stmt in _DDL_STATEMENTS:
                conn.execute(stmt)

    def _read_file(self) -> dict[str, list[dict[str, Any]]]:
        if not self._file.is_file():
            return {}
        try:
            return json.loads(self._file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    def _write_file(self, data: dict[str, list[dict[str, Any]]]) -> None:
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    @staticmethod
    def _title_from_message(message: str) -> str:
        text = (message or "").strip().replace("\n", " ")
        if not text:
            return "新对话"
        return text if len(text) <= 40 else text[:40] + "…"

    def touch(self, user_id: str, thread_id: str, message: str = "") -> None:
        """创建或更新会话；首次写入时用首条用户消息作标题。"""
        uid = (user_id or "").strip() or "anonymous"
        tid = (thread_id or "").strip() or "web-session"
        title = self._title_from_message(message)
        now = datetime.now(timezone.utc).isoformat()

        if self._pool is not None:
            with self._pool.connection() as conn:
                conn.execute(
                    """
                    INSERT INTO chat_threads (user_id, thread_id, title, updated_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (user_id, thread_id) DO UPDATE
                    SET updated_at = NOW(),
                        title = CASE
                            WHEN chat_threads.title = '新对话' AND EXCLUDED.title <> '新对话'
                            THEN EXCLUDED.title
                            ELSE chat_threads.title
                        END
                    """,
                    (uid, tid, title),
                )
            return

        with self._lock:
            data = self._read_file()
            rows = data.setdefault(uid, [])
            found = None
            for row in rows:
                if row.get("thread_id") == tid:
                    found = row
                    break
            if found is None:
                rows.append(
                    {
                        "user_id": uid,
                        "thread_id": tid,
                        "title": title,
                        "updated_at": now,
                    }
                )
            else:
                found["updated_at"] = now
                if found.get("title") in (None, "", "新对话") and title != "新对话":
                    found["title"] = title
            rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
            self._write_file(data)

    def list_threads(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        """按更新时间倒序列出会话。"""
        uid = (user_id or "").strip() or "anonymous"
        limit = max(1, min(int(limit or 50), 200))

        if self._pool is not None:
            with self._pool.connection() as conn:
                rows = conn.execute(
                    """
                    SELECT user_id, thread_id, title,
                           to_char(updated_at AT TIME ZONE 'UTC',
                                   'YYYY-MM-DD"T"HH24:MI:SS"Z"') AS updated_at
                    FROM chat_threads
                    WHERE user_id = %s
                    ORDER BY updated_at DESC
                    LIMIT %s
                    """,
                    (uid, limit),
                ).fetchall()
            return [dict(r) for r in rows]

        with self._lock:
            rows = list(self._read_file().get(uid, []))
        rows.sort(key=lambda r: r.get("updated_at") or "", reverse=True)
        return rows[:limit]

    def delete_thread(self, user_id: str, thread_id: str) -> bool:
        """删除会话元数据（不删除 checkpointer 内消息，可按需扩展）。"""
        uid = (user_id or "").strip() or "anonymous"
        tid = (thread_id or "").strip()
        if not tid:
            return False

        if self._pool is not None:
            with self._pool.connection() as conn:
                cur = conn.execute(
                    "DELETE FROM chat_threads WHERE user_id = %s AND thread_id = %s",
                    (uid, tid),
                )
                return cur.rowcount > 0

        with self._lock:
            data = self._read_file()
            rows = data.get(uid, [])
            new_rows = [r for r in rows if r.get("thread_id") != tid]
            changed = len(new_rows) != len(rows)
            data[uid] = new_rows
            if changed:
                self._write_file(data)
            return changed
