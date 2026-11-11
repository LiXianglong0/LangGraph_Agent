# LangGraph Agent

**LangGraph + FastAPI + Vue**，RAGFlow 可在**同一 Git 仓库**用总 Docker Compose 一起编排（进程/容器仍分离，HTTP 对接）。

## 日常启停（速查）

| 服务 | 地址 | 启动 | 停止 |
|------|------|------|------|
| RAGFlow（公网 Embedding） | http://localhost:8088 | `./deploy/start-ragflow-local.sh` | `./deploy/stop-ragflow-local.sh` |
| Agent API | http://localhost:8001 | `python -m api.main` | Ctrl+C |
| Vue | http://localhost:5173 | `web\start.bat` 或 `cd web && ./start.sh` | Ctrl+C |

完整说明（含总栈 / 首次 bootstrap）：→ [deploy/README.md](deploy/README.md)

## 方式 B：本地开发（仅 Agent）

```powershell
cd D:\study\LangGraph_Agent
pip install -r requirements.txt
python -m api.main

cd web
npm install
npm run dev
```

前端控制台（http://localhost:5173）：

| 菜单 | 用途 |
|------|------|
| 首页 | 状态总览与功能入口 |
| 智能对话 | 独立问答页（温度/工具/知识库开关） |
| 模型服务 / 知识库 / 系统 | 稳定配置与环境同步 |

## 文档

→ [docs/框架说明.md](docs/框架说明.md)
