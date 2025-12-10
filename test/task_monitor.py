"""
任务监控脚本
提供Web界面查看任务状态和手动控制功能
"""

import sys
import os
import json
import time
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request
import threading
from typing import Dict, Any

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from scheduled_tasks import TaskManager

app = Flask(__name__)
task_manager = None

# HTML模板
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Japan 任务监控系统</title>
    <style>
        body {
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 20px;
            text-align: center;
        }
        .header h1 {
            margin: 0;
            font-size: 24px;
        }
        .status-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 20px;
        }
        .status-card {
            border: 1px solid #ddd;
            border-radius: 8px;
            padding: 15px;
            background: #fafafa;
        }
        .status-card h3 {
            margin-top: 0;
            color: #333;
            border-bottom: 2px solid #eee;
            padding-bottom: 10px;
        }
        .status-item {
            display: flex;
            justify-content: space-between;
            margin: 8px 0;
            padding: 5px 0;
        }
        .status-label {
            font-weight: bold;
            color: #555;
        }
        .status-value {
            color: #333;
        }
        .status-running {
            color: #28a745;
            font-weight: bold;
        }
        .status-stopped {
            color: #dc3545;
            font-weight: bold;
        }
        .status-warning {
            color: #ffc107;
            font-weight: bold;
        }
        .controls {
            padding: 20px;
            border-top: 1px solid #eee;
            background: #f8f9fa;
        }
        .btn {
            background: #007bff;
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 4px;
            cursor: pointer;
            margin: 5px;
            font-size: 14px;
        }
        .btn:hover {
            background: #0056b3;
        }
        .btn-danger {
            background: #dc3545;
        }
        .btn-danger:hover {
            background: #c82333;
        }
        .btn-success {
            background: #28a745;
        }
        .btn-success:hover {
            background: #218838;
        }
        .sensor-data {
            background: #e8f5e8;
            border-left: 4px solid #28a745;
            padding: 10px;
            margin: 10px 0;
            border-radius: 4px;
        }
        .log-section {
            margin-top: 20px;
            padding: 20px;
            border-top: 1px solid #eee;
        }
        .log-box {
            background: #f8f9fa;
            border: 1px solid #ddd;
            border-radius: 4px;
            padding: 15px;
            height: 200px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        .refresh-info {
            text-align: center;
            color: #666;
            font-size: 12px;
            margin-top: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Japan 任务监控系统</h1>
            <p>传感器数据采集与上传任务实时监控</p>
        </div>
        
        <div class="status-grid">
            <div class="status-card">
                <h3>📊 系统状态</h3>
                <div class="status-item">
                    <span class="status-label">调度器状态:</span>
                    <span class="status-value" id="scheduler-status">加载中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">系统时间:</span>
                    <span class="status-value" id="current-time">{{ current_time }}</span>
                </div>
                <div class="status-item">
                    <span class="status-label">运行时长:</span>
                    <span class="status-value" id="uptime">计算中...</span>
                </div>
            </div>
            
            <div class="status-card">
                <h3>🔬 传感器数据采集</h3>
                <div class="status-item">
                    <span class="status-label">服务状态:</span>
                    <span class="status-value" id="sensor-status">加载中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">任务状态:</span>
                    <span class="status-value" id="sensor-task-status">加载中...</span>
                </div>
                <div class="sensor-data" id="sensor-data">
                    <strong>实时传感器数据:</strong><br>
                    <div id="sensor-values">加载中...</div>
                </div>
            </div>
            
            <div class="status-card">
                <h3>📤 数据上传任务</h3>
                <div class="status-item">
                    <span class="status-label">任务状态:</span>
                    <span class="status-value" id="upload-status">加载中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">下次执行:</span>
                    <span class="status-value" id="next-upload">计算中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">上次结果:</span>
                    <span class="status-value" id="last-upload-result">暂无数据</span>
                </div>
            </div>
            
            <div class="status-card">
                <h3>🌐 HTTP请求任务</h3>
                <div class="status-item">
                    <span class="status-label">目标URL:</span>
                    <span class="status-value" id="http-url">加载中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">超时设置:</span>
                    <span class="status-value" id="http-timeout">加载中...</span>
                </div>
                <div class="status-item">
                    <span class="status-label">重试次数:</span>
                    <span class="status-value" id="http-retries">加载中...</span>
                </div>
            </div>
        </div>
        
        <div class="controls">
            <h3>🎛️ 任务控制</h3>
            <button class="btn btn-success" onclick="startSensorTask()">启动传感器服务</button>
            <button class="btn btn-danger" onclick="stopSensorTask()">停止传感器服务</button>
            <button class="btn" onclick="triggerUpload()">手动执行上传</button>
            <button class="btn" onclick="refreshStatus()">刷新状态</button>
            <button onclick="triggerHttpRequest()" class="btn btn-primary">发送HTTP请求</button>
            <button onclick="showUpdateUrlDialog()" class="btn btn-secondary">更新HTTP URL</button>
        </div>
        
        <div class="log-section">
            <h3>📋 系统日志</h3>
            <div class="log-box" id="log-content">
                日志加载中...
            </div>
        </div>
        
        <div class="refresh-info">
            页面每30秒自动刷新 | 最后更新: <span id="last-update">{{ current_time }}</span>
        </div>
    </div>

    <script>
        let startTime = new Date();
        
        // 更新系统时间和运行时长
        function updateTime() {
            const now = new Date();
            document.getElementById('current-time').textContent = now.toLocaleString('zh-CN');
            
            const uptime = Math.floor((now - startTime) / 1000);
            const hours = Math.floor(uptime / 3600);
            const minutes = Math.floor((uptime % 3600) / 60);
            const seconds = uptime % 60;
            document.getElementById('uptime').textContent = `${hours}时${minutes}分${seconds}秒`;
        }
        
        // 获取状态信息
        async function refreshStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                
                // 更新调度器状态
                const schedulerStatus = data.scheduler_running ? 
                    '<span class="status-running">运行中</span>' : 
                    '<span class="status-stopped">已停止</span>';
                document.getElementById('scheduler-status').innerHTML = schedulerStatus;
                
                // 更新传感器状态
                if (data.tasks.sensor_data) {
                    const sensorRunning = data.tasks.sensor_data.service_status.running;
                    const sensorStatus = sensorRunning ? 
                        '<span class="status-running">运行中</span>' : 
                        '<span class="status-stopped">已停止</span>';
                    document.getElementById('sensor-status').innerHTML = sensorStatus;
                    
                    // 更新传感器数据
                    const sensorData = data.tasks.sensor_data.service_status.data;
                    let dataHtml = '';
                    if (sensorData) {
                        dataHtml = `
                            溶解氧: ${sensorData.dissolved_oxygen || 'N/A'}<br>
                            液位: ${sensorData.liquid_level || 'N/A'} mm<br>
                            pH: ${sensorData.ph || 'N/A'}<br>
                            pH温度: ${sensorData.ph_temperature || 'N/A'} °C<br>
                            浊度: ${sensorData.turbidity || 'N/A'} NTU
                        `;
                    } else {
                        dataHtml = '暂无数据';
                    }
                    document.getElementById('sensor-values').innerHTML = dataHtml;
                }
                
                // 更新上传任务状态
                if (data.tasks.data_upload) {
                    document.getElementById('upload-status').innerHTML = 
                        '<span class="status-running">已配置</span>';
                }
                
                document.getElementById('last-update').textContent = new Date().toLocaleString('zh-CN');
                
            } catch (error) {
                console.error('获取状态失败:', error);
            }
        }
        
        // 控制函数
        async function startSensorTask() {
            try {
                const response = await fetch('/api/start_sensor', {method: 'POST'});
                const result = await response.json();
                alert(result.message);
                refreshStatus();
            } catch (error) {
                alert('操作失败: ' + error.message);
            }
        }
        
        async function stopSensorTask() {
            try {
                const response = await fetch('/api/stop_sensor', {method: 'POST'});
                const result = await response.json();
                alert(result.message);
                refreshStatus();
            } catch (error) {
                alert('操作失败: ' + error.message);
            }
        }
        
        // 更新状态显示
        function updateStatusDisplay(data) {
            // 更新系统状态
            document.getElementById('system-status').textContent = 
                data.status === 'running' ? '运行中' : '已停止';
            document.getElementById('system-status').className = 
                'status-value ' + (data.status === 'running' ? 'status-running' : 'status-stopped');
            
            // 更新传感器状态
            document.getElementById('sensor-status').textContent = 
                data.sensor_service_running ? '运行中' : '已停止';
            document.getElementById('sensor-status').className = 
                'status-value ' + (data.sensor_service_running ? 'status-running' : 'status-stopped');
            
            // 更新HTTP任务状态
            if (data.http_task_info) {
                document.getElementById('http-url').textContent = 
                    data.http_task_info.target_url || 'N/A';
                document.getElementById('http-timeout').textContent = 
                    (data.http_task_info.timeout || 'N/A') + '秒';
                document.getElementById('http-retries').textContent = 
                    data.http_task_info.max_retries || 'N/A';
            } else {
                document.getElementById('http-url').textContent = 'N/A';
                document.getElementById('http-timeout').textContent = 'N/A';
                document.getElementById('http-retries').textContent = 'N/A';
            }
        }
        
        async function triggerUpload() {
            try {
                const response = await fetch('/api/trigger_upload', {method: 'POST'});
                const result = await response.json();
                alert(result.message);
                refreshStatus();
            } catch (error) {
                alert('操作失败: ' + error.message);
            }
        }
        
        // 手动触发HTTP请求
        function triggerHttpRequest() {
            fetch('/api/trigger_http', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('HTTP请求发送成功');
                } else {
                    alert('HTTP请求发送失败: ' + data.message);
                }
                refreshStatus();
            })
            .catch(error => {
                alert('HTTP请求发送失败: ' + error.message);
            });
        }
        
        // 显示更新URL对话框
        function showUpdateUrlDialog() {
            const url = prompt('请输入新的HTTP请求目标URL:', 'http://localhost:5002/api/messages/');
            if (url && url.trim()) {
                updateHttpUrl(url.trim());
            }
        }
        
        // 更新HTTP URL
        function updateHttpUrl(url) {
            fetch('/api/update_http_url', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ url: url })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    alert('HTTP URL更新成功');
                } else {
                    alert('HTTP URL更新失败: ' + data.message);
                }
                refreshStatus();
            })
            .catch(error => {
                alert('HTTP URL更新失败: ' + error.message);
            });
        }
        
        // 定时更新
        setInterval(updateTime, 1000);
        setInterval(refreshStatus, 30000);
        
        // 初始化
        updateTime();
        refreshStatus();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """主页面"""
    return render_template_string(HTML_TEMPLATE, current_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'))

@app.route('/api/status')
def get_status():
    """获取系统状态API"""
    if task_manager:
        return jsonify(task_manager.get_status())
    else:
        return jsonify({"error": "任务管理器未初始化"})

@app.route('/api/start_sensor', methods=['POST'])
def start_sensor():
    """启动传感器服务API"""
    try:
        if task_manager and task_manager.sensor_task:
            result = task_manager.sensor_task.execute()
            return jsonify({
                "success": result.get("success", False),
                "message": result.get("message", "操作完成")
            })
        else:
            return jsonify({"success": False, "message": "传感器任务未初始化"})
    except Exception as e:
        return jsonify({"success": False, "message": f"操作失败: {str(e)}"})

@app.route('/api/stop_sensor', methods=['POST'])
def stop_sensor():
    """停止传感器服务API"""
    try:
        if task_manager and task_manager.sensor_task:
            task_manager.sensor_task.stop_service()
            return jsonify({"success": True, "message": "传感器服务已停止"})
        else:
            return jsonify({"success": False, "message": "传感器任务未初始化"})
    except Exception as e:
        return jsonify({"success": False, "message": f"操作失败: {str(e)}"})

@app.route('/api/trigger_upload', methods=['POST'])
def trigger_upload():
    """手动触发上传API"""
    try:
        if task_manager and task_manager.upload_task:
            result = task_manager.upload_task.execute()
            return jsonify({
                "success": result.get("success", False),
                "message": result.get("message", "上传任务执行完成")
            })
        else:
            return jsonify({"success": False, "message": "上传任务未初始化"})
    except Exception as e:
        return jsonify({"success": False, "message": f"操作失败: {str(e)}"})

@app.route('/api/trigger_http', methods=['POST'])
def trigger_http_request():
    """手动触发HTTP请求任务"""
    try:
        if task_manager and task_manager.is_running:
            result = task_manager.trigger_http_request()
            return jsonify(result)
        else:
            return jsonify({
                "success": False,
                "message": "任务管理器未运行"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"触发HTTP请求失败: {str(e)}"
        })

@app.route('/api/update_http_url', methods=['POST'])
def update_http_url():
    """更新HTTP请求目标URL"""
    try:
        data = request.get_json()
        url = data.get('url')
        
        if not url:
            return jsonify({
                "success": False,
                "message": "URL参数缺失"
            })
        
        if task_manager:
            success = task_manager.update_http_target_url(url)
            return jsonify({
                "success": success,
                "message": "URL更新成功" if success else "URL更新失败"
            })
        else:
            return jsonify({
                "success": False,
                "message": "任务管理器未初始化"
            })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"更新URL失败: {str(e)}"
        })

def run_web_server():
    """运行Web服务器"""
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)

def main():
    """主函数"""
    global task_manager
    
    print("=" * 60)
    print("AI Japan 任务监控系统启动中...")
    print("=" * 60)
    
    try:
        # 创建任务管理器
        task_manager = TaskManager()
        task_manager.setup_tasks()
        task_manager.start_scheduler()
        
        print("✅ 任务调度器启动成功")
        
        # 在单独线程中启动Web服务器
        web_thread = threading.Thread(target=run_web_server, daemon=True)
        web_thread.start()
        
        print("✅ Web监控界面启动成功")
        print("🌐 访问地址: http://localhost:5000")
        print("📊 监控界面: http://127.0.0.1:5000")
        print("=" * 60)
        print("系统运行中，按 Ctrl+C 停止...")
        
        # 保持主线程运行
        while True:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在停止系统...")
    except Exception as e:
        print(f"系统启动失败: {e}")
        return 1
    finally:
        if task_manager:
            task_manager.stop_scheduler()
        print("系统已停止")
    
    return 0

if __name__ == "__main__":
    exit(main())