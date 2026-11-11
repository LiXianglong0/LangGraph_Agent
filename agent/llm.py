"""智谱模型封装（OpenAI 兼容接口）。"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# 固定从项目根目录加载 .env（避免 PyCharm 工作目录不是根目录时读不到）
load_dotenv(Path(__file__).resolve().parents[1] / ".env")

# 智谱 OpenAI 兼容接口地址（可由 .env 覆盖）
ZHIPU_BASE_URL = (
    os.getenv("ZHIPU_BASE_URL") or "https://open.bigmodel.cn/api/paas/v4/"
).rstrip("/") + "/"
# 默认免费模型（可由 .env 覆盖）
ZHIPU_MODEL = os.getenv("ZHIPU_MODEL") or "glm-4-flash"


def create_llm(
    api_key: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    temperature: float = 0.7,
) -> ChatOpenAI:
    """创建绑定智谱 API 的 ChatOpenAI 实例，参数可覆盖环境变量默认值。"""
    key = api_key or os.getenv("ZHIPU_API_KEY")
    if not key:
        raise ValueError(
            "未找到 API Key，请在页面配置或写入 .env 的 ZHIPU_API_KEY"
        )

    # 通过 OpenAI 兼容协议调用智谱模型
    return ChatOpenAI(
        model=model or ZHIPU_MODEL,
        api_key=key,
        base_url=base_url or ZHIPU_BASE_URL,
        temperature=temperature,
    )
