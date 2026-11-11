"""基于 RAGFlow 客户端生成 LangChain 工具。"""

from langchain_core.tools import StructuredTool

from agent.ragflow.client import RagflowClient


def create_knowledge_search_tool(client: RagflowClient) -> StructuredTool:
    """创建知识库检索工具；闭包绑定当前 RagflowClient。"""

    def knowledge_search(query: str) -> str:
        """从企业知识库检索与问题相关的文档片段（对接独立部署的 RAGFlow）。

        Args:
            query: 检索问句，尽量具体
        """
        # 真正检索逻辑在客户端，便于单测与替换实现
        return client.retrieve(query.strip())

    return StructuredTool.from_function(
        func=knowledge_search,
        name="knowledge_search",
        description=(
            "从已连接的 RAGFlow 知识库检索文档片段并返回原文摘要。"
            "用户要查找/整理/总结知识库、论文、微生物相关资料，"
            "或任何需引用已上传文档的问题时，必须调用本工具；"
            "参数 query 填写具体检索词或完整问题。"
        ),
    )
