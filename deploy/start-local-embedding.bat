@echo off
chcp 65001 >nul
cd /d "%~dp0\.."
REM 可选：本机 TEI（需本地模型文件）
wsl -e bash -lc "cd /mnt/d/study/LangGraph_Agent && sed -i 's/\r$//' deploy/start-with-local-tei.sh deploy/ensure-local-tei.sh deploy/enable-local-embedding.sh && chmod +x deploy/start-with-local-tei.sh deploy/ensure-local-tei.sh deploy/enable-local-embedding.sh && ./deploy/start-with-local-tei.sh"
pause
