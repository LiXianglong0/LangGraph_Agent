"""Agent 进程内单例：复用 Checkpointer，配置变化时重建图。"""

from __future__ import annotations

import os
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from agent.checkpoint import create_checkpointer
from agent.graph import build_agent
from agent.llm import ZHIPU_BASE_URL, ZHIPU_MODEL
from agent.ragflow.client import RagflowSettings
from agent.response import extract_final_answer
from agent.tools import list_tool_metas
from api.agent_store import AgentStore
from api.chat_store import ChatStore
from api.schemas import ModelConfig, RagflowConfig

# 固定从项目根目录加载 .env
load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def _env_ragflow_defaults() -> RagflowConfig:
    """从环境变量读取 RAGFlow 默认配置，便于服务器侧预置。"""
    ids_raw = os.getenv("RAGFLOW_DATASET_IDS", "")
    dataset_ids = [x.strip() for x in ids_raw.split(",") if x.strip()]
    return RagflowConfig(
        enabled=os.getenv("RAGFLOW_ENABLED", "false").lower() in {"1", "true", "yes"},
        base_url=os.getenv("RAGFLOW_BASE_URL", "http://127.0.0.1:8088"),
        api_key=os.getenv("RAGFLOW_API_KEY", ""),
        dataset_ids=dataset_ids,
    )


def to_ragflow_settings(cfg: RagflowConfig) -> RagflowSettings:
    """API 配置转运行时 Settings。"""
    return RagflowSettings(
        enabled=cfg.enabled,
        base_url=cfg.base_url,
        api_key=cfg.api_key,
        dataset_ids=list(cfg.dataset_ids),
        page_size=cfg.page_size,
        similarity_threshold=cfg.similarity_threshold,
    )


class AgentService:
    """管理全局 Checkpointer 与当前 Agent 实例。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        # 有 DATABASE_URL 时用 Postgres 持久化；否则 MemorySaver
        self._checkpointer, self._db_pool = create_checkpointer()
        # 按用户记录会话列表（Postgres 或 data/chat_threads.json）
        self.chat_store = ChatStore(self._db_pool)
        # Agent 目录（Postgres agents 表或 data/agents.json）
        self.agent_store = AgentStore(self._db_pool)
        self._agent = None
        self._config_key: tuple | None = None

    def _fingerprint(self, cfg: ModelConfig) -> tuple:
        """用配置生成指纹，变化则需要重建 Agent。"""
        tools = tuple(cfg.tool_names) if cfg.tool_names is not None else ("*",)
        rf = cfg.ragflow
        return (
            cfg.api_key,
            cfg.model,
            cfg.base_url,
            cfg.temperature,
            tools,
            rf.enabled,
            rf.base_url,
            rf.api_key,
            tuple(rf.dataset_ids),
            rf.page_size,
            rf.similarity_threshold,
            getattr(cfg, "agent_id", "") or "",
            getattr(cfg, "system_prompt", "") or "",
        )

    def _merge_ragflow_credentials(self, ragflow_cfg: RagflowConfig) -> RagflowConfig:
        """仅在已启用时补全 Key/地址/数据集；绝不把 enabled=false 强行改成 true。"""
        if not ragflow_cfg.enabled:
            return ragflow_cfg
        env_rf = _env_ragflow_defaults()
        updates: dict[str, Any] = {}
        if not ragflow_cfg.api_key and env_rf.api_key:
            updates["api_key"] = env_rf.api_key
        if not (ragflow_cfg.base_url or "").strip() and env_rf.base_url:
            updates["base_url"] = env_rf.base_url
        if not ragflow_cfg.dataset_ids and env_rf.dataset_ids:
            updates["dataset_ids"] = env_rf.dataset_ids
        return ragflow_cfg.model_copy(update=updates) if updates else ragflow_cfg

    def apply_agent_profile(self, cfg: ModelConfig) -> ModelConfig:
        """按 Agent 档案锁定工具、系统提示与是否允许知识库。"""
        agent_id = (getattr(cfg, "agent_id", "") or "").strip()
        system_prompt = (getattr(cfg, "system_prompt", "") or "").strip()
        tool_names = cfg.tool_names
        ragflow_cfg = self._merge_ragflow_credentials(cfg.ragflow)

        if agent_id:
            row = self.agent_store.get_agent(agent_id)
            if row:
                if not system_prompt:
                    system_prompt = (row.get("systemPrompt") or "").strip()
                # 档案规定关闭 RAG 时，忽略前端勾选与环境默认
                if not bool(row.get("ragEnabled")):
                    ragflow_cfg = ragflow_cfg.model_copy(update={"enabled": False})
                archived_tools = row.get("tools")
                if isinstance(archived_tools, list):
                    tool_names = [str(x) for x in archived_tools]

        return ModelConfig(
            api_key=cfg.api_key,
            model=cfg.model,
            base_url=cfg.base_url,
            temperature=cfg.temperature,
            tool_names=tool_names,
            ragflow=ragflow_cfg,
            agent_id=agent_id,
            system_prompt=system_prompt,
        )

    def ensure_agent(self, cfg: ModelConfig):
        """确保 Agent 与当前配置一致，返回可 invoke 的图。"""
        api_key = cfg.api_key.strip() or (os.getenv("ZHIPU_API_KEY") or "")
        if not api_key:
            raise ValueError("未配置 API Key：请在请求 config.api_key 或 .env 中提供")

        profiled = self.apply_agent_profile(cfg)
        effective = ModelConfig(
            api_key=api_key,
            model=profiled.model or ZHIPU_MODEL,
            base_url=profiled.base_url or ZHIPU_BASE_URL,
            temperature=profiled.temperature,
            tool_names=profiled.tool_names,
            ragflow=profiled.ragflow,
            agent_id=profiled.agent_id,
            system_prompt=profiled.system_prompt,
        )
        key = self._fingerprint(effective)

        with self._lock:
            if self._agent is None or self._config_key != key:
                self._agent = build_agent(
                    api_key=effective.api_key,
                    model=effective.model,
                    base_url=effective.base_url,
                    temperature=effective.temperature,
                    tool_names=effective.tool_names,
                    ragflow=to_ragflow_settings(effective.ragflow),
                    checkpointer=self._checkpointer,
                    system_prompt=effective.system_prompt or None,
                )
                self._config_key = key
            return self._agent

    def _resolve_ragflow(self, cfg: ModelConfig) -> RagflowConfig:
        """按 Agent 档案解析是否真正启用知识库。"""
        return self.apply_agent_profile(cfg).ragflow

    def chat(
        self,
        message: str,
        thread_id: str,
        cfg: ModelConfig,
        user_id: str = "anonymous",
    ) -> dict[str, Any]:
        """执行一轮对话；启用知识库时附带可下载源文件列表。

        启用且配置齐全的 RAGFlow 时，先自动检索再交给模型，
        避免 glm-4-flash 等模型只「口头说要调工具」却不真正 tool_call。
        专用 Agent（ragEnabled=false）不会自动检索知识库。
        """
        profiled = self.apply_agent_profile(cfg)
        agent = self.ensure_agent(profiled)
        user_text = message.strip()
        sources: list[dict[str, Any]] = []

        # 专用业务预调（如「CSC70173订单状态」），避免弱模型拒调工具
        from agent.intent_prefetch import prefetch_business_context

        boosted = prefetch_business_context(user_text, profiled.tool_names)
        if boosted:
            user_text = boosted

        ragflow_cfg = profiled.ragflow
        settings = to_ragflow_settings(ragflow_cfg)
        if settings.is_ready() and not boosted:
            from agent.ragflow.client import RagflowClient

            retrieved = RagflowClient(settings).retrieve_with_sources(user_text)
            sources = [
                {
                    "index": s.index,
                    "document_id": s.document_id,
                    "dataset_id": s.dataset_id,
                    "name": s.name,
                    "score": s.score,
                }
                for s in retrieved.sources
            ]
            user_text = (
                f"用户问题：{message.strip()}\n\n"
                f"【知识库自动检索结果】\n{retrieved.text}\n\n"
                "请严格依据以上检索片段回答；引用文献时必须使用对应表中的编号，"
                "写成 [1]、[2] 这种形式，且编号必须与「引用编号与文件对应表」一致；"
                "不要写「来源[1]」以外的自造编号。若片段不足请说明缺什么，不要编造。"
            )

        result: dict[str, Any] = agent.invoke(
            {"messages": [HumanMessage(content=user_text)]},
            {"configurable": {"thread_id": thread_id}},
        )
        # 按用户登记会话，便于历史列表分用户展示
        try:
            self.chat_store.touch(user_id, thread_id, message)
        except Exception:  # noqa: BLE001
            pass
        return {"answer": extract_final_answer(result), "sources": sources}

    def get_history(self, thread_id: str) -> list[dict[str, str]]:
        """从 Checkpointer 读取会话历史，供 F5 后前端回填。

        配置 DATABASE_URL 后进程重启仍可恢复；否则仅进程内 MemorySaver。
        """
        tid = (thread_id or "").strip() or "web-session"
        try:
            # 用默认配置确保图已编译（共享同一 checkpointer）
            agent = self.ensure_agent(ModelConfig())
        except ValueError:
            return []

        snap = agent.get_state({"configurable": {"thread_id": tid}})
        values = getattr(snap, "values", None) or {}
        raw_messages = values.get("messages") or []

        history: list[dict[str, str]] = []
        for msg in raw_messages:
            # 只回填用户话与最终助手文本，跳过纯工具调用中间态
            if isinstance(msg, HumanMessage) and msg.content:
                content = str(msg.content)
                # 自动检索会改写 HumanMessage，展示时只还原用户原话
                if content.startswith("用户问题："):
                    content = content.split("\n", 1)[0].removeprefix("用户问题：").strip()
                history.append({"role": "user", "content": content})
            elif isinstance(msg, AIMessage) and msg.content:
                tool_calls = getattr(msg, "tool_calls", None) or []
                if tool_calls:
                    continue
                history.append({"role": "assistant", "content": str(msg.content)})
        return history

    @staticmethod
    def list_tools(ragflow_enabled: bool = False) -> list[dict[str, str]]:
        """列出工具（含可选 knowledge_search）。"""
        return list_tool_metas(ragflow_enabled=ragflow_enabled)

    @staticmethod
    def defaults() -> dict[str, Any]:
        """返回前端初始化默认值。"""
        ragflow = _env_ragflow_defaults()
        try:
            temperature = float(os.getenv("ZHIPU_TEMPERATURE", "0.7"))
        except ValueError:
            temperature = 0.7
        return {
            "model": os.getenv("ZHIPU_MODEL") or ZHIPU_MODEL,
            "base_url": os.getenv("ZHIPU_BASE_URL") or ZHIPU_BASE_URL,
            "temperature": temperature,
            "has_env_api_key": bool(os.getenv("ZHIPU_API_KEY")),
            "tools": AgentService.list_tools(ragflow_enabled=True),
            "ragflow": ragflow,
        }


# 进程级单例
agent_service = AgentService()
