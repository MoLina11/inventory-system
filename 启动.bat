@echo off
chcp 65001 >nul
title 出入库管理系统

echo ============================================
echo   出入库管理系统 - 启动中...
echo ============================================
echo.

REM 检查 Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到 Python，请先安装 Python 3
    echo 下载地址: https://www.python.org/downloads/
    pause
    exit /b 1
)

REM 安装依赖
echo [1/3] 安装依赖...
pip install -r requirements.txt -q

REM 启动服务
echo [2/3] 启动服务器...
start /b python server.py > server.log 2>&1

REM 等待启动
timeout /t 3 /nobreak >nul

echo [3/3] 服务已启动！
echo.
echo ============================================
echo   访问地址: http://localhost:8001
echo   手机访问: http://你的电脑IP:8001
echo ============================================
echo.
echo 按任意键打开浏览器...
pause >nul
start http://localhost:8001
