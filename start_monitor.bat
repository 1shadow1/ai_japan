@echo off
chcp 65001 >nul
title AI Japan 任务监控系统

echo ========================================
echo    AI Japan 任务监控系统
echo ========================================
echo.
echo 正在启动Web监控界面...
echo.
echo 监控功能:
echo 1. 实时查看任务状态
echo 2. 传感器数据监控
echo 3. 手动控制任务执行
echo 4. 系统日志查看
echo.
echo 访问地址: http://localhost:5000
echo ========================================

cd /d "%~dp0"

python task_monitor.py

echo.
echo 监控系统已停止，按任意键退出...
pause >nul