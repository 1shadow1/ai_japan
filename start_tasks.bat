@echo off
chcp 65001 >nul
title AI Japan 定时任务系统

echo ========================================
echo    AI Japan 定时任务系统启动脚本
echo ========================================
echo.
echo 正在启动定时任务系统...
echo.
echo 功能说明:
echo 1. 传感器数据采集 - 后台持续运行
echo 2. 数据上传任务 - 每日凌晨2点执行
echo 3. Web监控界面 - http://localhost:5000
echo.
echo ========================================

cd /d "%~dp0"

python scheduled_tasks.py

echo.
echo 系统已停止，按任意键退出...
pause >nul