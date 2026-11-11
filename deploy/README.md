# 统一 Docker 编排（Agent + RAGFlow）

同一 Git 仓库内用一份总 compose 管理：

- `agent-api`：本项目 FastAPI
- RAGFlow：官方镜像栈（克隆到 `third_party/ragflow`）

## 日常启停速查（留档）

| 服务 | 地址 | 启动 | 停止 |
|------|------|------|------|
| RAGFlow（公网 Embedding） | http://localhost:8088 | `./deploy/start-ragflow-local.sh` | `./deploy/stop-ragflow-local.sh` |
| RAGFlow + 本机 TEI（可选） | :8088 / :6380 | `./deploy/start-with-local-tei.sh` | 同上 |
| Agent API | http://localhost:8001 | `python -m api.main` 或 `./deploy/start.sh` | Ctrl+C / `./deploy/stop.sh` |
| Vue 前端 | http://localhost:5173 | Windows: `web\start.bat`；WSL: `cd web && ./start.sh` | Ctrl+C |

本仓库日常启动**不含** Ollama / 本机 TEI；LLM 与 Embedding 用公网即可。

### 1）RAGFlow（推荐：公网 Embedding）

```bash
cd /mnt/d/study/LangGraph_Agent
./deploy/start-ragflow-local.sh
# 停：./deploy/stop-ragflow-local.sh
```

Windows：`deploy\start-ragflow-local.bat`  
在 RAGFlow「模型提供商」配置智谱 / 硅基流动等 Embedding，知识库选用对应模型。

### 1b）可选：本机 TEI

需镜像 `./deploy/pull-tei-mirror.sh`，且 `deploy/tei-models/<模型>/` 含完整权重。  
`./deploy/start-with-local-tei.sh`

### 3）Agent（本地开发：API + Vue）

```powershell
# 终端 A：后端
cd D:\study\LangGraph_Agent
python -m api.main

# 终端 B：前端
cd D:\study\LangGraph_Agent\web
.\start.bat
```

WSL 前端等价：`cd /mnt/d/study/LangGraph_Agent/web && ./start.sh`

### 4）总栈（Docker：Agent API + RAGFlow 一起）

```bash
cd /mnt/d/study/LangGraph_Agent
./deploy/start.sh
./deploy/stop.sh
# ./deploy/stop.sh --volumes   # 连数据一起删
```

说明：日常若已用 `start-local-embedding.sh` / `start-ragflow.sh` 起了 RAGFlow，不要再叠一套总栈；Agent 用本地 `python -m api.main` + Vue 即可。

---

## 首次准备（推荐在 WSL）

```bash
cd /mnt/d/study/LangGraph_Agent
chmod +x deploy/*.sh
./deploy/bootstrap-ragflow.sh
cp -n .env.example .env   # 至少配置模型 / RAGFLOW_*
```

文档引擎：`DOC_ENGINE=elasticsearch`，`STACK_VERSION=9.5.5`。

```bash
docker pull elasticsearch:9.5.5
# 或：docker pull docker.m.daocloud.io/library/elasticsearch:9.5.5
#     docker tag docker.m.daocloud.io/library/elasticsearch:9.5.5 elasticsearch:9.5.5
```

## 仅启动 Agent 容器

```bash
cd deploy
docker compose -f docker-compose.agent-only.yml up -d --build
```

## 文件说明

| 文件 | 作用 |
|------|------|
| `docker-compose.yml` | 总编排（include Agent + RAGFlow） |
| `docker-compose.agent.yml` | Agent 服务 |
| `docker-compose.agent-only.yml` | 只起 Agent |
| `Dockerfile` | Agent 镜像 |
| `bootstrap-ragflow.sh` | 克隆 RAGFlow + 生成端口错开后的 env |
| `start-ragflow-local.sh` / `.bat` | **推荐**：仅 RAGFlow，公网 Embedding |
| `stop-ragflow-local.sh` | 停 RAGFlow（并清 TEI 残留） |
| `disable-local-embedding.sh` | 从 env 去掉 tei 配置 |
| `start-with-local-tei.sh` | 可选：RAGFlow + 本机 TEI |
| `ensure-local-tei.sh` / `enable-local-embedding.sh` | 本机 TEI 辅助 |
| `start-ragflow.sh` / `stop-ragflow.sh` | 底层 compose 启停 |
| `pull-tei-mirror.sh` | 国内镜像加速拉 TEI |
| `start.sh` / `stop.sh` | 总栈启停 |
| `ragflow.env` | bootstrap 生成，勿手改进 Git |
