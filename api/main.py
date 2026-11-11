"""FastAPI 入口：对外提供聊天与配置相关接口。"""

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

# 启动时先加载根目录 .env，再导入依赖它的模块
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from api.agent_service import agent_service
from api.schemas import (
    AgentInfo,
    AgentListResponse,
    AgentUpsertRequest,
    ChatRequest,
    ChatResponse,
    DefaultsResponse,
    DownloadDocumentRequest,
    HistoryMessage,
    HistoryResponse,
    RagflowConfig,
    SaveConfigRequest,
    SaveConfigResponse,
    SourceFile,
    ThreadInfo,
    ThreadListResponse,
    ToolInfo,
)

app = FastAPI(title="LangGraph Agent API", version="1.0.0")

# 允许本地 Vue 开发服务器跨域（5173/5174 等）
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root() -> dict:
    """根路径提示，避免浏览器打开端口时看到裸 404。"""
    return {"service": "LangGraph Agent API", "docs": "/docs", "health": "/api/health"}


@app.get("/api/health")
def health() -> dict:
    """健康检查。"""
    return {"status": "ok", "service": "langgraph-agent"}


@app.get("/api/tools", response_model=list[ToolInfo])
def get_tools() -> list[ToolInfo]:
    """返回可用工具列表。"""
    return [ToolInfo(**item) for item in agent_service.list_tools()]


@app.get("/api/agents", response_model=AgentListResponse)
def list_agents() -> AgentListResponse:
    """列出已启用的 Agent 目录（来自 Postgres / 本地 JSON）。"""
    try:
        rows = agent_service.agent_store.list_agents()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取 Agent 失败：{exc}") from exc
    return AgentListResponse(agents=[AgentInfo(**r) for r in rows])


@app.get("/api/agents/{agent_id}", response_model=AgentInfo)
def get_agent(agent_id: str) -> AgentInfo:
    """获取单个 Agent 详情。"""
    try:
        row = agent_service.agent_store.get_agent(agent_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取 Agent 失败：{exc}") from exc
    if not row:
        raise HTTPException(status_code=404, detail="Agent 不存在")
    return AgentInfo(**row)


@app.put("/api/agents/{agent_id}", response_model=AgentInfo)
def upsert_agent(agent_id: str, req: AgentUpsertRequest) -> AgentInfo:
    """创建或更新 Agent（写入数据库）。"""
    if req.id.strip() != agent_id.strip():
        raise HTTPException(status_code=400, detail="路径 id 与正文 id 不一致")
    try:
        row = agent_service.agent_store.upsert_agent(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"保存 Agent 失败：{exc}") from exc
    return AgentInfo(**row)


@app.get("/api/defaults", response_model=DefaultsResponse)
def get_defaults() -> DefaultsResponse:
    """返回前端默认模型配置、工具列表与 RAGFlow 预置。"""
    data = agent_service.defaults()
    return DefaultsResponse(
        model=data["model"],
        base_url=data["base_url"],
        temperature=data["temperature"],
        has_env_api_key=data["has_env_api_key"],
        tools=[ToolInfo(**t) for t in data["tools"]],
        ragflow=data["ragflow"],
    )


@app.post("/api/config/save", response_model=SaveConfigResponse)
def save_config(req: SaveConfigRequest) -> SaveConfigResponse:
    """把页面侧栏配置写入项目根目录 .env，供下次启动默认加载。"""
    import os

    from api.env_config import upsert_env

    updates: dict[str, str] = {
        "ZHIPU_MODEL": req.model.strip() or "glm-4-flash",
        "ZHIPU_BASE_URL": (
            req.base_url.strip() or "https://open.bigmodel.cn/api/paas/v4/"
        ),
        "ZHIPU_TEMPERATURE": str(req.temperature),
        "RAGFLOW_ENABLED": "true" if req.ragflow.enabled else "false",
        "RAGFLOW_BASE_URL": req.ragflow.base_url.strip() or "http://127.0.0.1:8088",
        "RAGFLOW_DATASET_IDS": ",".join(req.ragflow.dataset_ids),
    }
    # 页面留空则保留 .env 里已有 Key，避免误清空
    if req.api_key.strip():
        updates["ZHIPU_API_KEY"] = req.api_key.strip()
    if req.ragflow.api_key.strip():
        updates["RAGFLOW_API_KEY"] = req.ragflow.api_key.strip()

    try:
        path = upsert_env(updates)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(status_code=500, detail=f"写入 .env 失败：{exc}") from exc

    load_dotenv(path, override=True)
    for key, value in updates.items():
        os.environ[key] = value

    return SaveConfigResponse(ok=True, path=str(path), message="已保存到 .env")


@app.post("/api/ragflow/ping")
def ragflow_ping(cfg: RagflowConfig) -> dict:
    """探测 RAGFlow 是否可按当前配置检索（不改写 Agent 状态）。"""
    from agent.ragflow.client import RagflowClient

    from api.agent_service import to_ragflow_settings

    # 探测只验证连通性，不要求页面已勾选「启用」
    settings = to_ragflow_settings(cfg)
    settings.enabled = True
    if not (settings.base_url.strip() and settings.api_key.strip() and settings.dataset_ids):
        return {
            "ok": False,
            "message": "配置不完整：需要地址、API Key、至少一个 Dataset ID",
        }

    # 用极短问题做连通性探测
    text = RagflowClient(settings).retrieve("ping")
    ok = not text.startswith("RAGFlow 请求失败") and "未启用" not in text
    return {"ok": ok, "preview": text[:500]}


@app.get("/api/threads/{thread_id}/messages", response_model=HistoryResponse)
def get_thread_messages(thread_id: str) -> HistoryResponse:
    """按会话 ID 读取历史（F5 刷新后前端用来恢复聊天记录）。"""
    tid = thread_id.strip() or "web-session"
    try:
        msgs = agent_service.get_history(tid)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取历史失败：{exc}") from exc
    return HistoryResponse(
        thread_id=tid,
        messages=[HistoryMessage(**m) for m in msgs],
    )


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """多轮对话：同一 thread_id 共享记忆；知识库命中时附带可下载源文件。"""
    try:
        out = agent_service.chat(
            message=req.message.strip(),
            thread_id=req.thread_id.strip() or "web-session",
            cfg=req.config,
            user_id=req.user_id.strip() or "anonymous",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"调用失败：{exc}") from exc

    return ChatResponse(
        answer=out["answer"],
        thread_id=req.thread_id,
        sources=[SourceFile(**s) for s in out.get("sources") or []],
    )


@app.get("/api/users/{user_id}/threads", response_model=ThreadListResponse)
def list_user_threads(user_id: str, limit: int = 50) -> ThreadListResponse:
    """按用户列出历史会话（仅元数据；正文用 thread_id 再拉 messages）。"""
    uid = user_id.strip() or "anonymous"
    try:
        rows = agent_service.chat_store.list_threads(uid, limit=limit)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"读取会话列表失败：{exc}") from exc
    return ThreadListResponse(
        user_id=uid,
        threads=[ThreadInfo(**r) for r in rows],
    )


@app.delete("/api/users/{user_id}/threads/{thread_id}")
def delete_user_thread(user_id: str, thread_id: str) -> dict:
    """删除用户下某条会话记录（列表项）。"""
    uid = user_id.strip() or "anonymous"
    tid = thread_id.strip()
    ok = agent_service.chat_store.delete_thread(uid, tid)
    return {"ok": ok, "user_id": uid, "thread_id": tid}


@app.post("/api/ragflow/download")
def download_ragflow_document(req: DownloadDocumentRequest) -> Response:
    """代理下载 RAGFlow 文档，浏览器侧不必直连 RAGFlow。"""
    from agent.ragflow.client import RagflowClient

    from api.agent_service import to_ragflow_settings

    # 下载只需 Key/地址；临时打开 enabled 以复用校验逻辑
    cfg = req.ragflow.model_copy(update={"enabled": True})
    if not cfg.dataset_ids and req.dataset_id:
        cfg = cfg.model_copy(update={"dataset_ids": [req.dataset_id]})
    settings = to_ragflow_settings(cfg)
    if not (settings.base_url.strip() and settings.api_key.strip()):
        raise HTTPException(status_code=400, detail="请先填写 RAGFlow 地址与 API Key")

    try:
        content, filename = RagflowClient(settings).download_document(
            req.dataset_id, req.document_id
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"下载失败：{exc}") from exc

    # 简单处理中文文件名
    from urllib.parse import quote

    safe_name = quote(filename)
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_name}",
        },
    )


def run() -> None:
    """本地启动入口：python -m api.main。"""
    import uvicorn

    # 默认 8001，避免与本机其它占用 8000 的服务冲突
    uvicorn.run("api.main:app", host="0.0.0.0", port=8001, reload=True)


if __name__ == "__main__":
    run()
