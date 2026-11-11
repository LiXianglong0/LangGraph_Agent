"""使用 LangGraph 预置 ReAct 组装 Agent 图。"""

from langgraph.checkpoint.memory import MemorySaver
from langgraph.prebuilt import create_react_agent

from agent.llm import create_llm
from agent.ragflow.client import RagflowSettings
from agent.tools import build_toolset

# 基础系统提示：约束工具使用习惯
_BASE_PROMPT = (
    "你是助手，可通过工具完成任务。"
    "需要外部信息或知识库内容时必须先调用对应工具，再基于工具结果回答；"
    "不要声称无法访问用户知识库或文件（若已提供 knowledge_search 工具）。"
)

# 启用 RAG 时追加：强制优先检索
_RAG_PROMPT = (
    "已接入 RAGFlow 知识库工具 knowledge_search。"
    "当用户提到知识库、文档、论文、资料、检索、整理、总结，"
    "或询问与已上传文档相关的内容时，必须先调用 knowledge_search，"
    "用具体检索词（可改写用户问题）查询，再根据返回片段作答。"
    "禁止在未调用该工具时回答「无法访问知识库」。"
)


def build_agent(
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
    tool_names: list[str] | None = None,
    ragflow: RagflowSettings | None = None,
    checkpointer: MemorySaver | None = None,
    system_prompt: str | None = None,
):
    """创建并返回带记忆的 ReAct Agent；支持模型、工具与 RAGFlow 配置。"""
    # 按页面/调用方参数创建模型
    llm = create_llm(
        api_key=api_key,
        model=model,
        base_url=base_url,
        temperature=temperature,
    )

    # 本地工具 +（可选）知识库检索工具
    tools = build_toolset(ragflow)
    if tool_names is not None:
        name_set = set(tool_names)
        tools = [t for t in tools if t.name in name_set]

    # 同一进程内复用 checkpointer，才能跨请求保留会话
    if checkpointer is None:
        checkpointer = MemorySaver()

    custom = (system_prompt or "").strip()
    if custom:
        prompt = custom
        if ragflow is not None and ragflow.enabled and any(
            getattr(t, "name", "") == "knowledge_search" for t in tools
        ):
            prompt = f"{custom}\n{_RAG_PROMPT}"
    else:
        prompt = _BASE_PROMPT
        if ragflow is not None and ragflow.enabled and any(
            getattr(t, "name", "") == "knowledge_search" for t in tools
        ):
            prompt = f"{_BASE_PROMPT}\n{_RAG_PROMPT}"

    # create_react_agent：模型决策 → 调工具 → 回灌结果 → 最终回答
    return create_react_agent(llm, tools, prompt=prompt, checkpointer=checkpointer)
