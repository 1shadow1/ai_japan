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
echo 2. 数据上传任务 - 每10分钟执行（默认）
echo 3. Web监控界面 - http://localhost:5000
echo.
echo ========================================

cd /d "%~dp0"

rem 启用模拟模式与干运行开关（可根据需要修改为0关闭）
set AIJ_SENSOR_SIMULATE=0
set AIJ_UPLOAD_DRY_RUN=0
rem 配置流式上传目标与间隔（按需覆盖）
set AIJ_STREAM_API_URL=http://8.216.33.92:5000/api/updata_sensor_data
set AIJ_STREAM_INTERVAL=10

python -m src.app.main

echo.
echo 系统已停止，按任意键退出...
pause >nul