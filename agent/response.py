"""从 Agent 运行结果中提取最终回复。"""

from langchain_core.messages import AIMessage


def extract_final_answer(result: dict) -> str:
    """从 Agent 返回的消息列表中提取最终 AI 文本回复。"""
    messages = result.get("messages") or []
    # 从后往前找最后一条有内容的 AI 消息
    for msg in reversed(messages):
        if isinstance(msg, AIMessage) and msg.content:
            return str(msg.content)
    return "(无回复内容)"
