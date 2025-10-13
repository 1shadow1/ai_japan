@echo off
chcp 936 >nul
title AI Japan Task Runner

echo ========================================
echo      AI Japan Task Runner Script
echo ========================================
echo.
echo Starting scheduled tasks...
echo.
echo Features:
echo 1) Sensor data collection - background
echo 2) Data upload job - every 10 minutes (default)
echo 3) Web monitor - http://localhost:5000
echo.
echo ========================================

cd /d "%~dp0"

rem Enable simulation and dry-run switches (set to 0 to disable if needed)
set AIJ_SENSOR_SIMULATE=0
set AIJ_UPLOAD_DRY_RUN=0
rem Configure streaming upload target and interval
set AIJ_STREAM_API_URL=http://8.216.33.92:5000/api/updata_sensor_data
set AIJ_STREAM_INTERVAL=10

rem ================= Feeder Cloud Config =================
rem Purpose: login, find device by name, report status (aligned with test\feed.py)
set AIJ_FEEDER_USER=8619034657726
set AIJ_FEEDER_PASS=123456789
rem Device name (change if different on your cloud platform)
set AIJ_FEEDER_DEV_NAME=AI
rem Disable certificate verification for debugging; set to 1 for production
set AIJ_FEEDER_VERIFY=0
rem Short network timeout for quick test and fast exit
set AIJ_FEEDER_TIMEOUT=5
rem Gateway endpoint (same as in test\feed.py)
set AIJ_FEEDER_BASE_URL=https://ffish.huaeran.cn:8081/commonRequest

rem ================= Camera Service (optional) Network Timeout =================
rem Shorten status report and image upload timeouts to avoid blocking on exit
set AIJ_CAMERA_STATUS_TIMEOUT=5
set AIJ_CAMERA_UPLOAD_TIMEOUT=10
rem Other camera parameters (enable if needed)
rem set AIJ_CAMERA_KEYS=0:0,1:1,2:2,3:3,4:4
rem set AIJ_CAMERA_RECORD_DURATION=60
rem set AIJ_CAMERA_RECORD_FPS=30
rem set AIJ_CAMERA_OUTPUT_DIR=logs\videos
rem set AIJ_EXTRACT_INTERVAL_SEC=1
rem set AIJ_EXTRACT_OUTPUT_DIR=output
rem set AIJ_CAMERA_UPLOAD_URL=http://8.216.33.92:5000/api/updata_camera_data
rem set AIJ_CAMERA_UPLOAD_DRY_RUN=1
rem set AIJ_CAMERA_SHOW=0

python -m src.app.main

echo.
echo System stopped. Press any key to exit...
pause >nul