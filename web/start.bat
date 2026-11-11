@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo [info] 启动 Vue 前端 Vite ...
if not exist "node_modules\" (
  echo [info] 安装依赖，使用 npmmirror ...
  call npm install --registry=https://registry.npmmirror.com
  if errorlevel 1 (
    echo [error] npm install 失败
    pause
    exit /b 1
  )
)

echo [ok] 浏览器打开 http://localhost:5173/
echo      后端需另开终端: python -m api.main ，默认端口 8001
echo.
call npm run dev
