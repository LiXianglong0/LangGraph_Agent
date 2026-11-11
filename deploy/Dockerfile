# LangGraph Agent FastAPI 镜像
FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY agent ./agent
COPY api ./api

EXPOSE 8001

# 生产不启用 reload；与本地 / Vite 代理统一为 8001
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8001"]
