"""LangGraph Agent 的 Streamlit 页面：聊天 + 侧边栏配置。"""

import os
import uuid

import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.checkpoint.memory import MemorySaver

from agent.graph import build_agent
from agent.llm import ZHIPU_BASE_URL, ZHIPU_MODEL
from agent.response import extract_final_answer
from agent.tools import TOOLS

load_dotenv()


def init_session_state() -> None:
    """初始化页面会话状态（对话历史、记忆、Agent）。"""
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "thread_id" not in st.session_state:
        st.session_state.thread_id = "web-session"
    if "checkpointer" not in st.session_state:
        st.session_state.checkpointer = MemorySaver()
    if "agent" not in st.session_state:
        st.session_state.agent = None
    if "agent_config_key" not in st.session_state:
        st.session_state.agent_config_key = None


def render_sidebar() -> dict:
    """渲染侧边栏配置项，返回当前配置字典。"""
    st.sidebar.header("模型配置")

    api_key = st.sidebar.text_input(
        "API Key",
        value=os.getenv("ZHIPU_API_KEY", ""),
        type="password",
        help="智谱开放平台 API Key，也可写在 .env",
    )
    base_url = st.sidebar.text_input("Base URL", value=ZHIPU_BASE_URL)
    model = st.sidebar.text_input("模型名称", value=ZHIPU_MODEL)
    temperature = st.sidebar.slider("Temperature", 0.0, 1.0, 0.7, 0.1)

    st.sidebar.header("工具")
    # 勾选启用的本地工具
    enabled_tools = []
    for tool in TOOLS:
        if st.sidebar.checkbox(tool.name, value=True, help=tool.description):
            enabled_tools.append(tool.name)

    st.sidebar.header("会话")
    thread_id = st.sidebar.text_input("会话 ID (thread_id)", value=st.session_state.thread_id)
    st.session_state.thread_id = thread_id

    if st.sidebar.button("新建会话", use_container_width=True):
        # 换新 thread_id，并清空页面展示的聊天记录
        st.session_state.thread_id = f"web-{uuid.uuid4().hex[:8]}"
        st.session_state.messages = []
        st.rerun()

    if st.sidebar.button("清空当前会话展示", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    apply = st.sidebar.button("应用配置并重建 Agent", type="primary", use_container_width=True)

    return {
        "api_key": api_key.strip(),
        "base_url": base_url.strip(),
        "model": model.strip(),
        "temperature": float(temperature),
        "tool_names": enabled_tools,
        "apply": apply,
    }


def ensure_agent(cfg: dict) -> None:
    """按配置创建或重建 Agent（首次自动创建，之后需点「应用配置」）。"""
    if not cfg["api_key"]:
        if cfg["apply"]:
            st.sidebar.warning("请先填写 API Key")
        return

    config_key = (
        cfg["api_key"],
        cfg["base_url"],
        cfg["model"],
        cfg["temperature"],
        tuple(cfg["tool_names"]),
    )

    # 仅在尚未创建，或用户主动应用配置时重建，避免拖动滑块反复编译
    need_rebuild = st.session_state.agent is None or cfg["apply"]
    if not need_rebuild:
        return

    st.session_state.agent = build_agent(
        api_key=cfg["api_key"],
        model=cfg["model"],
        base_url=cfg["base_url"],
        temperature=cfg["temperature"],
        tool_names=cfg["tool_names"],
        checkpointer=st.session_state.checkpointer,
    )
    st.session_state.agent_config_key = config_key
    if cfg["apply"]:
        st.sidebar.success("配置已应用")


def main() -> None:
    """Streamlit 入口：左侧配置，右侧对话。"""
    st.set_page_config(page_title="LangGraph Agent", page_icon="🤖", layout="wide")
    st.title("LangGraph ReAct Agent")
    st.caption("侧边栏可配置模型与工具；同一会话 ID 具备多轮记忆。")

    init_session_state()
    cfg = render_sidebar()
    ensure_agent(cfg)

    # 回放历史消息
    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    prompt = st.chat_input("输入问题…")
    if not prompt:
        return

    if st.session_state.agent is None:
        st.error("请先在侧边栏填写 API Key，并点击「应用配置并重建 Agent」。")
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # 调用 LangGraph；历史由 checkpointer 按 thread_id 合并
    with st.chat_message("assistant"):
        with st.spinner("思考中…"):
            try:
                result = st.session_state.agent.invoke(
                    {"messages": [HumanMessage(content=prompt)]},
                    {"configurable": {"thread_id": st.session_state.thread_id}},
                )
                answer = extract_final_answer(result)
            except Exception as exc:  # noqa: BLE001
                answer = f"调用失败：{exc}"
            st.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})


if __name__ == "__main__":
    main()
