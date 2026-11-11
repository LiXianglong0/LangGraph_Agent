"""Agent 目录持久化：Postgres 表 agents；无库时回退内置种子。"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

# 与前端初始目录对齐的种子数据（首次建表写入）
_SEED_AGENTS: list[dict[str, Any]] = [
    {
        "id": "general",
        "code": "AGENT1",
        "name": "通用助手",
        "summary": "日常问答、多工具协作的通用对话入口。",
        "description": (
            "面向一般问答与任务协助：可调用计算、时间、天气等工具；"
            "需要时也可打开知识库。适合作为默认操作台。"
        ),
        "features": [
            "多轮对话与会话记忆",
            "可调用本地演示工具（计算 / 时间 / 天气）",
            "可选启用知识库检索",
            "参数面板可临时调整模型与工具",
        ],
        "tags": ["默认", "多工具"],
        "tools": None,
        "rag_enabled": False,
        "system_prompt": (
            "你是「通用助手」。优先直接清晰回答用户；"
            "需要精确计算、当前时间或天气时再调用对应工具。回答简洁、可执行。"
        ),
        "flowchart": """flowchart TD
  U[用户提问] --> A[通用助手 LLM]
  A -->|需要计算| C[calculator]
  A -->|需要时间| T[get_current_time]
  A -->|需要天气| W[get_weather]
  A -->|可选 RAG| K[knowledge_search]
  C --> A
  T --> A
  W --> A
  K --> A
  A --> R[回复用户]""",
        "sort_order": 10,
    },
    {
        "id": "knowledge",
        "code": "AGENT2",
        "name": "知识库助手",
        "summary": "面向文档 / 论文检索与引用回答。",
        "description": (
            "专为 RAGFlow 知识库设计：默认开启检索，主要使用 knowledge_search。"
            "适合整理资料、引用片段、对照文献编号回答。"
        ),
        "features": [
            "默认启用知识库检索",
            "工具聚焦 knowledge_search",
            "回答中尽量使用 [n] 引用编号",
            "对话页可下载命中源文件",
        ],
        "tags": ["RAG", "检索"],
        "tools": ["knowledge_search"],
        "rag_enabled": True,
        "system_prompt": (
            "你是「知识库助手」。回答必须优先依据 knowledge_search / 检索片段；"
            "引用时使用 [1]、[2] 等形式，与源文件编号一致。片段不足时说明缺失，禁止编造文献。"
        ),
        "flowchart": """flowchart TD
  U[用户问题] --> A[知识库助手]
  A --> K[knowledge_search<br/>RAGFlow]
  K --> A
  A --> R[带引用编号的回答]
  R --> D[可下载源文件]""",
        "sort_order": 20,
    },
    {
        "id": "toolkit",
        "code": "AGENT3",
        "name": "工具助手",
        "summary": "演示本地工具调用：计算、时间、天气。",
        "description": "不启用知识库，专注展示 ReAct 工具循环。适合验证工具链路与调试 Agent 流程。",
        "features": [
            "calculator 数学计算",
            "get_current_time 本地时间",
            "get_weather 模拟天气",
            "关闭 RAG，流程更短更清晰",
        ],
        "tags": ["工具", "演示"],
        "tools": ["calculator", "get_current_time", "get_weather"],
        "rag_enabled": False,
        "system_prompt": (
            "你是「工具助手」。遇到计算、时间、天气类问题必须先调用对应工具再回答；"
            "不要编造工具结果。"
        ),
        "flowchart": """flowchart TD
  U[用户] --> A[工具助手]
  A -->|算式| C[calculator]
  A -->|时间| T[get_current_time]
  A -->|城市天气| W[get_weather]
  C --> A
  T --> A
  W --> A
  A --> R[基于工具结果回复]""",
        "sort_order": 30,
    },
    {
        "id": "css_sellable",
        "code": "AGENT4",
        "name": "CSS可售物料判断",
        "summary": (
            "可售 / 不可售原因 / 是否配置价格 / QAD 订单状态；"
            "分别调用 CSS 诊断或 QAD 接口。"
        ),
        "description": (
            "专用助手：1) 是否可售 2) 为何不可售 "
            "3) 客户+物料是否配置价格 4) 8 位 QAD 单号查状态。不使用知识库。"
        ),
        "features": [
            "意图：可售 / 不可售原因 / 配置价格 / 订单状态 / 快码字典",
            "可售槽位：客户、订单类型、物料或客户物料号",
            "价格槽位：客户编码 + 物料号",
            "订单状态：8 位字母数字 bill_no",
            "快码经验目录 + css_lookup_values",
        ],
        "tags": ["CSS", "可售", "物料", "QAD", "价格", "订单状态", "快码"],
        "tools": [
            "css_check_sellable",
            "css_explain_unsellable",
            "qad_check_price_configured",
            "qad_check_order_status",
            "css_list_lookup_catalog",
            "css_lookup_values",
        ],
        "rag_enabled": False,
        "system_prompt": (
            "你是「CSS可售/QAD」专用助手。禁止说无法查询。"
            "「CSC70173订单状态」这类话必须用 qad_check_order_status。"
            "有【已自动调用工具】结果时直接据此中文答复。"
        ),
        "flowchart": """flowchart TD
  U[用户对话] --> I[意图识别]
  I -->|是否可售/为何不可售| S1[收客户/订单类型/物料]
  I -->|是否配置价格| S2[收客户+物料号]
  I -->|订单状态| S3[收8位QAD单号]
  I -->|不清| Q[追问]
  S1 --> D[diagnoseMaterialSellable]
  S2 --> P[BatchGetQad58]
  S3 --> O[SalesOrderStatusWS]
  D --> R[回复]
  P --> R
  O --> R""",
        "sort_order": 1,
    },
]

_DDL = (
    """
    CREATE TABLE IF NOT EXISTS agents (
        id            TEXT PRIMARY KEY,
        code          TEXT NOT NULL UNIQUE,
        name          TEXT NOT NULL,
        summary       TEXT NOT NULL DEFAULT '',
        description   TEXT NOT NULL DEFAULT '',
        features      JSONB NOT NULL DEFAULT '[]'::jsonb,
        tags          JSONB NOT NULL DEFAULT '[]'::jsonb,
        tools         JSONB,
        rag_enabled   BOOLEAN NOT NULL DEFAULT FALSE,
        system_prompt TEXT NOT NULL DEFAULT '',
        flowchart     TEXT NOT NULL DEFAULT '',
        enabled       BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order    INT NOT NULL DEFAULT 0,
        created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS idx_agents_sort
        ON agents (enabled, sort_order, code)
    """,
)


def _row_to_agent(row: dict[str, Any]) -> dict[str, Any]:
    features = row.get("features")
    tags = row.get("tags")
    tools = row.get("tools")
    if isinstance(features, str):
        features = json.loads(features)
    if isinstance(tags, str):
        tags = json.loads(tags)
    if isinstance(tools, str):
        tools = json.loads(tools)
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "summary": row.get("summary") or "",
        "description": row.get("description") or "",
        "features": features or [],
        "tags": tags or [],
        "tools": tools,
        "ragEnabled": bool(row.get("rag_enabled")),
        "systemPrompt": row.get("system_prompt") or "",
        "flowchart": row.get("flowchart") or "",
        "enabled": bool(row.get("enabled", True)),
        "sortOrder": int(row.get("sort_order") or 0),
    }


class AgentStore:
    """Agent 目录存储。"""

    def __init__(self, pool: Any | None = None) -> None:
        self._pool = pool
        self._lock = threading.Lock()
        self._file = Path(__file__).resolve().parents[1] / "data" / "agents.json"
        if self._pool is not None:
            self._setup_pg()
            self._seed_pg_if_empty()
        else:
            self._seed_file_if_empty()

    def _setup_pg(self) -> None:
        with self._pool.connection() as conn:
            for stmt in _DDL:
                conn.execute(stmt)

    def _seed_pg_if_empty(self) -> None:
        with self._pool.connection() as conn:
            n = conn.execute("SELECT COUNT(*) AS c FROM agents").fetchone()["c"]
            if int(n) > 0:
                return
            for a in _SEED_AGENTS:
                self._upsert_pg(conn, a)

    def _seed_file_if_empty(self) -> None:
        if self._file.is_file():
            return
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._file.write_text(
            json.dumps(_SEED_AGENTS, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _upsert_pg(self, conn: Any, a: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO agents (
                id, code, name, summary, description, features, tags, tools,
                rag_enabled, system_prompt, flowchart, enabled, sort_order, updated_at
            ) VALUES (
                %(id)s, %(code)s, %(name)s, %(summary)s, %(description)s,
                %(features)s::jsonb, %(tags)s::jsonb, %(tools)s::jsonb,
                %(rag_enabled)s, %(system_prompt)s, %(flowchart)s,
                COALESCE(%(enabled)s, TRUE), COALESCE(%(sort_order)s, 0), NOW()
            )
            ON CONFLICT (id) DO UPDATE SET
                code = EXCLUDED.code,
                name = EXCLUDED.name,
                summary = EXCLUDED.summary,
                description = EXCLUDED.description,
                features = EXCLUDED.features,
                tags = EXCLUDED.tags,
                tools = EXCLUDED.tools,
                rag_enabled = EXCLUDED.rag_enabled,
                system_prompt = EXCLUDED.system_prompt,
                flowchart = EXCLUDED.flowchart,
                enabled = EXCLUDED.enabled,
                sort_order = EXCLUDED.sort_order,
                updated_at = NOW()
            """,
            {
                "id": a["id"],
                "code": a["code"],
                "name": a["name"],
                "summary": a.get("summary") or "",
                "description": a.get("description") or "",
                "features": json.dumps(a.get("features") or [], ensure_ascii=False),
                "tags": json.dumps(a.get("tags") or [], ensure_ascii=False),
                "tools": json.dumps(a.get("tools"), ensure_ascii=False)
                if a.get("tools") is not None
                else None,
                "rag_enabled": bool(a.get("rag_enabled", False)),
                "system_prompt": a.get("system_prompt") or "",
                "flowchart": a.get("flowchart") or "",
                "enabled": a.get("enabled", True),
                "sort_order": int(a.get("sort_order") or 0),
            },
        )

    def list_agents(self, include_disabled: bool = False) -> list[dict[str, Any]]:
        if self._pool is not None:
            with self._pool.connection() as conn:
                if include_disabled:
                    rows = conn.execute(
                        "SELECT * FROM agents ORDER BY sort_order, code"
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM agents WHERE enabled = TRUE "
                        "ORDER BY sort_order, code"
                    ).fetchall()
            return [_row_to_agent(dict(r)) for r in rows]

        with self._lock:
            data = json.loads(self._file.read_text(encoding="utf-8"))
        out = []
        for a in data:
            item = {
                "id": a["id"],
                "code": a["code"],
                "name": a["name"],
                "summary": a.get("summary") or "",
                "description": a.get("description") or "",
                "features": a.get("features") or [],
                "tags": a.get("tags") or [],
                "tools": a.get("tools"),
                "ragEnabled": bool(a.get("rag_enabled", False)),
                "systemPrompt": a.get("system_prompt") or "",
                "flowchart": a.get("flowchart") or "",
                "enabled": bool(a.get("enabled", True)),
                "sortOrder": int(a.get("sort_order") or 0),
            }
            if include_disabled or item["enabled"]:
                out.append(item)
        out.sort(key=lambda x: (x["sortOrder"], x["code"]))
        return out

    def get_agent(self, agent_id: str) -> dict[str, Any] | None:
        aid = (agent_id or "").strip()
        if not aid:
            return None
        if self._pool is not None:
            with self._pool.connection() as conn:
                row = conn.execute(
                    "SELECT * FROM agents WHERE id = %s", (aid,)
                ).fetchone()
            return _row_to_agent(dict(row)) if row else None
        for a in self.list_agents(include_disabled=True):
            if a["id"] == aid:
                return a
        return None

    def upsert_agent(self, payload: dict[str, Any]) -> dict[str, Any]:
        """创建或更新 Agent（供后续管理 / 脚本写入）。"""
        required = ("id", "code", "name")
        for k in required:
            if not (payload.get(k) or "").strip():
                raise ValueError(f"缺少字段: {k}")
        row = {
            "id": payload["id"].strip(),
            "code": payload["code"].strip(),
            "name": payload["name"].strip(),
            "summary": payload.get("summary") or "",
            "description": payload.get("description") or "",
            "features": payload.get("features") or [],
            "tags": payload.get("tags") or [],
            "tools": payload.get("tools"),
            "rag_enabled": bool(
                payload.get("rag_enabled", payload.get("ragEnabled", False))
            ),
            "system_prompt": payload.get("system_prompt")
            or payload.get("systemPrompt")
            or "",
            "flowchart": payload.get("flowchart") or "",
            "enabled": bool(payload.get("enabled", True)),
            "sort_order": int(
                payload.get("sort_order", payload.get("sortOrder", 100)) or 100
            ),
        }
        if self._pool is not None:
            with self._pool.connection() as conn:
                self._upsert_pg(conn, row)
            return self.get_agent(row["id"])  # type: ignore[return-value]

        with self._lock:
            data = []
            if self._file.is_file():
                data = json.loads(self._file.read_text(encoding="utf-8"))
            data = [a for a in data if a.get("id") != row["id"]]
            data.append(row)
            self._file.parent.mkdir(parents=True, exist_ok=True)
            self._file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        return self.get_agent(row["id"])  # type: ignore[return-value]
