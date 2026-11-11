"""FastAPI 请求/响应模型。"""

from pydantic import BaseModel, Field


class RagflowConfig(BaseModel):
    """RAGFlow 对接配置（服务单独部署，本系统仅 HTTP 调用）。"""

    enabled: bool = Field(default=False, description="是否启用知识库检索工具")
    base_url: str = Field(
        default="http://127.0.0.1:8088",
        description="RAGFlow Web/API 根地址",
    )
    api_key: str = Field(default="", description="RAGFlow API Key")
    dataset_ids: list[str] = Field(
        default_factory=list,
        description="数据集 ID 列表，可在 RAGFlow 控制台复制",
    )
    page_size: int = Field(default=6, ge=1, le=30)
    similarity_threshold: float = Field(default=0.2, ge=0.0, le=1.0)


class ModelConfig(BaseModel):
    """前端可下发的模型、工具与知识库配置。"""

    api_key: str = Field(default="", description="智谱 API Key")
    model: str = Field(default="glm-4-flash", description="模型名称")
    base_url: str = Field(
        default="https://open.bigmodel.cn/api/paas/v4/",
        description="OpenAI 兼容 Base URL",
    )
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    tool_names: list[str] | None = Field(
        default=None,
        description="启用的工具名；null 表示全部启用",
    )
    ragflow: RagflowConfig = Field(default_factory=RagflowConfig)
    agent_id: str = Field(default="", description="前端选用的 Agent 标识")
    system_prompt: str = Field(
        default="",
        description="Agent 专属系统提示；空则使用后端默认提示",
    )


class ChatRequest(BaseModel):
    """对话请求。"""

    message: str = Field(..., min_length=1, description="本轮用户输入")
    thread_id: str = Field(default="web-session", description="会话 ID，用于记忆")
    user_id: str = Field(
        default="anonymous",
        description="用户标识；用于分用户记录会话列表（轻量，非完整账号体系）",
    )
    config: ModelConfig = Field(default_factory=ModelConfig)


class ThreadInfo(BaseModel):
    """某用户下的一条历史会话。"""

    user_id: str
    thread_id: str
    title: str
    updated_at: str


class ThreadListResponse(BaseModel):
    """用户会话列表。"""

    user_id: str
    threads: list[ThreadInfo]


class SourceFile(BaseModel):
    """检索命中的源文件，供前端展示下载；index 与回答中的 [n] 对应。"""

    index: int = 0
    document_id: str
    dataset_id: str
    name: str
    score: float | None = None


class ChatResponse(BaseModel):
    """对话响应。"""

    answer: str
    thread_id: str
    sources: list[SourceFile] = Field(default_factory=list)


class DownloadDocumentRequest(BaseModel):
    """经本后端代理下载 RAGFlow 文档（避免浏览器直暴露 Key 到外链）。"""

    dataset_id: str
    document_id: str
    ragflow: RagflowConfig = Field(default_factory=RagflowConfig)


class HistoryMessage(BaseModel):
    """会话历史中的一条展示消息。"""

    role: str
    content: str


class HistoryResponse(BaseModel):
    """按 thread_id 恢复的会话历史。"""

    thread_id: str
    messages: list[HistoryMessage]


class ToolInfo(BaseModel):
    """工具元信息。"""

    name: str
    description: str


class DefaultsResponse(BaseModel):
    """前端初始化默认配置。"""

    model: str
    base_url: str
    temperature: float
    has_env_api_key: bool
    tools: list[ToolInfo]
    ragflow: RagflowConfig


class SaveConfigRequest(BaseModel):
    """将页面配置持久化到项目根目录 .env。"""

    api_key: str = Field(default="", description="智谱 API Key；空则不覆盖已有 .env 值")
    model: str = Field(default="glm-4-flash")
    base_url: str = Field(default="https://open.bigmodel.cn/api/paas/v4/")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    ragflow: RagflowConfig = Field(default_factory=RagflowConfig)


class SaveConfigResponse(BaseModel):
    """保存配置结果。"""

    ok: bool = True
    path: str
    message: str = "已写入 .env"


class AgentInfo(BaseModel):
    """Agent 目录项（与前端字段对齐）。"""

    id: str
    code: str
    name: str
    summary: str = ""
    description: str = ""
    features: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tools: list[str] | None = None
    ragEnabled: bool = False
    systemPrompt: str = ""
    flowchart: str = ""
    enabled: bool = True
    sortOrder: int = 0


class AgentListResponse(BaseModel):
    """Agent 列表。"""

    agents: list[AgentInfo]


class AgentUpsertRequest(BaseModel):
    """创建或更新 Agent（管理用）。"""

    id: str
    code: str
    name: str
    summary: str = ""
    description: str = ""
    features: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    tools: list[str] | None = None
    ragEnabled: bool = False
    systemPrompt: str = ""
    flowchart: str = ""
    enabled: bool = True
    sortOrder: int = 100
