"""LangGraph ReAct Agent CLI 入口。"""

from langchain_core.messages import HumanMessage

from agent.graph import build_agent
from agent.response import extract_final_answer


def main() -> None:
    """交互式命令行循环：输入问题，打印 Agent 最终回答。"""
    print("LangGraph ReAct Agent（智谱 glm-4-flash）")
    print("输入问题开始对话，输入 quit / exit 退出。\n")

    # 编译 Agent 图（启动时校验 API Key）
    agent = build_agent()
    # 固定会话 ID：后续 invoke 会读到此前的用户与助手消息
    config = {"configurable": {"thread_id": "cli-session"}}

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已退出。")
            break

        if not user_input:
            continue
        if user_input.lower() in {"quit", "exit"}:
            print("已退出。")
            break

        # 只传入本轮用户消息，历史由 checkpointer 按 thread_id 合并
        result = agent.invoke(
            {"messages": [HumanMessage(content=user_input)]},
            config,
        )
        answer = extract_final_answer(result)
        print(f"助手: {answer}\n")


if __name__ == "__main__":
    main()
