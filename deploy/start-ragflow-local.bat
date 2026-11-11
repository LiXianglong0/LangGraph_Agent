@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
REM 仅 RAGFlow，Embedding 用公网模型（不启本机 TEI）
wsl -e bash -lc "cd /mnt/d/study/LangGraph_Agent && sed -i 's/\r$//' deploy/disable-local-embedding.sh deploy/start-ragflow-local.sh deploy/stop-ragflow-local.sh && chmod +x deploy/disable-local-embedding.sh deploy/start-ragflow-local.sh deploy/stop-ragflow-local.sh && ./deploy/start-ragflow-local.sh"
pause
