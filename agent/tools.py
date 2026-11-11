"""ReAct Agent 可用的本地工具定义（不含 RAGFlow，知识库工具按配置动态注入）。"""

from datetime import datetime

from langchain_core.tools import BaseTool, tool

from agent.css.tools import CSS_TOOLS
from agent.qad.tools import QAD_TOOLS
from agent.ragflow.client import RagflowClient, RagflowSettings
from agent.ragflow.tools import create_knowledge_search_tool


@tool
def calculator(expression: str) -> str:
    """对数学表达式做安全计算，仅支持数字与四则运算及括号。

    Args:
        expression: 数学表达式，例如 "2 + 3 * (4 - 1)"
    """
    # 仅允许数字与基本运算符，避免任意代码执行
    allowed = set("0123456789+-*/().% ")
    if not expression or not all(ch in allowed for ch in expression):
        return f"非法表达式：{expression}"

    try:
        result = eval(expression, {"__builtins__": {}}, {})
        return str(result)
    except Exception as exc:  # noqa: BLE001
        return f"计算失败：{exc}"


@tool
def get_current_time() -> str:
    """获取当前本地日期与时间。"""
    # 返回可读的本地时间字符串
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@tool
def get_weather(city: str) -> str:
    """查询指定城市的天气（模拟数据，用于演示工具调用）。

    Args:
        city: 城市名称，例如 "北京"、"上海"
    """
    # 固定模拟结果，不依赖真实天气 API
    mock_data = {
        "北京": "晴，15°C，北风 2 级",
        "上海": "多云，18°C，东南风 3 级",
        "广州": "小雨，24°C，南风 2 级",
        "深圳": "阴，23°C，东风 2 级",
    }
    weather = mock_data.get(city.strip(), "晴转多云，20°C，微风")
    return f"{city}：{weather}"


# 纯本地工具（始终可注册）
LOCAL_TOOLS: list[BaseTool] = [calculator, get_current_time, get_weather]

# 兼容旧引用：默认等同本地工具
TOOLS = LOCAL_TOOLS


def build_toolset(ragflow: RagflowSettings | None = None) -> list[BaseTool]:
    """组装最终工具列表；含 CSS/QAD 业务工具；启用 RAGFlow 时追加 knowledge_search。"""
    tools: list[BaseTool] = [*LOCAL_TOOLS, *CSS_TOOLS, *QAD_TOOLS]
    # 即使尚未 ready，也注册工具，调用时返回明确配置提示，便于联调
    if ragflow is not None and ragflow.enabled:
        client = RagflowClient(ragflow)
        tools.append(create_knowledge_search_tool(client))
    return tools


def list_tool_metas(ragflow_enabled: bool = False) -> list[dict[str, str]]:
    """供 API/前端展示的工具元信息。"""
    tools = build_toolset(
        RagflowSettings(enabled=ragflow_enabled) if ragflow_enabled else None
    )
    return [{"name": t.name, "description": t.description or ""} for t in tools]
