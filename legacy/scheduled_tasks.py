"""
定时任务配置和管理
集成传感器数据采集、数据上传和HTTP请求任务
"""

import sys
import os
import time
import threading
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

# 添加项目路径到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入调度器和任务模块
from schedule.task_scheduler import TaskScheduler, BaseTask, ScheduleRule, TaskStatus, ScheduleType
from sensor_data_service import SensorDataService
from http_request_task import HttpRequestTask
import subprocess
import logging

class SensorDataTask(Task):
    """传感器数据采集任务 - 后台持续运行"""
    
    def __init__(self):
        super().__init__(
            task_id="sensor_data_collection",
            name="传感器数据采集服务",
            description="后台持续采集传感器数据并记录到CSV文件",
            task_type=TaskType.FUNCTION
        )
        self.sensor_service: Optional[SensorDataService] = None
        self.service_thread: Optional[threading.Thread] = None
    
    def execute(self) -> Dict[str, Any]:
        """启动传感器数据采集服务"""
        try:
            if self.sensor_service and self.sensor_service.is_running():
                return {
                    "success": True,
                    "message": "传感器服务已在运行中",
                    "status": "already_running"
                }
            
            # 创建传感器服务实例
            self.sensor_service = SensorDataService()
            
            # 在单独线程中启动服务
            def run_service():
                try:
                    self.sensor_service.start()
                    # 保持服务运行
                    while self.sensor_service.is_running():
                        time.sleep(1)
                except Exception as e:
                    logging.error(f"传感器服务运行异常: {e}")
            
            self.service_thread = threading.Thread(target=run_service, daemon=True)
            self.service_thread.start()
            
            # 等待服务启动
            time.sleep(2)
            
            if self.sensor_service.is_running():
                return {
                    "success": True,
                    "message": "传感器数据采集服务启动成功",
                    "status": "started",
                    "start_time": datetime.now().isoformat()
                }
            else:
                return {
                    "success": False,
                    "message": "传感器服务启动失败",
                    "status": "failed"
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"传感器任务执行失败: {str(e)}",
                "error": str(e)
            }
    
    def stop_service(self):
        """停止传感器服务"""
        if self.sensor_service:
            self.sensor_service.stop()
            self.sensor_service = None
        
        if self.service_thread and self.service_thread.is_alive():
            self.service_thread.join(timeout=10)
            self.service_thread = None
    
    def get_service_status(self) -> Dict[str, Any]:
        """获取服务状态"""
        if not self.sensor_service:
            return {"running": False, "data": None}
        
        return {
            "running": self.sensor_service.is_running(),
            "data": self.sensor_service.get_current_data()
        }

class DataUploadTask(Task):
    """数据上传任务 - 每日执行一次"""
    
    def __init__(self):
        super().__init__(
            task_id="daily_data_upload",
            name="每日数据上传",
            description="每天执行一次数据上传到服务器",
            task_type=TaskType.SCRIPT
        )
        self.upload_script_path = os.path.join(project_root, "client", "updata.py")
    
    def execute(self) -> Dict[str, Any]:
        """执行数据上传脚本"""
        try:
            # 检查上传脚本是否存在
            if not os.path.exists(self.upload_script_path):
                return {
                    "success": False,
                    "message": f"上传脚本不存在: {self.upload_script_path}",
                    "error": "script_not_found"
                }
            
            # 执行上传脚本
            start_time = datetime.now()
            
            result = subprocess.run(
                [sys.executable, self.upload_script_path],
                cwd=os.path.dirname(self.upload_script_path),
                capture_output=True,
                text=True,
                timeout=300  # 5分钟超时
            )
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            return {
                "success": result.returncode == 0,
                "message": "数据上传完成" if result.returncode == 0 else "数据上传失败",
                "return_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "execution_time": execution_time,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat()
            }
            
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "message": "数据上传超时",
                "error": "timeout",
                "timeout": 300
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"数据上传任务执行失败: {str(e)}",
                "error": str(e)
            }

class TaskManager:
    """任务管理器 - 统一管理所有定时任务"""
    
    def __init__(self):
        self.scheduler = TaskScheduler()
        self.sensor_task: Optional[SensorDataTask] = None
        self.upload_task: Optional[DataUploadTask] = None
        self.http_task: Optional[HttpRequestTask] = None
        self.setup_logging()
    
    def setup_logging(self):
        """设置日志系统"""
        log_dir = os.path.join(project_root, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'scheduled_tasks.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('TaskManager')
    
    def setup_tasks(self):
        """设置所有定时任务"""
        
        # 1. 创建传感器数据采集任务（后台持续运行）
        self.sensor_task = SensorDataTask()
        
        # 传感器任务立即启动一次，然后每小时检查一次状态
        sensor_rule = ScheduleRule(
            interval_seconds=3600,  # 每小时检查一次
            max_executions=None,    # 无限次执行
            start_time=datetime.now()
        )
        
        self.scheduler.add_task(self.sensor_task, sensor_rule)
        
        # 2. 创建数据上传任务（每日执行一次）
        self.upload_task = DataUploadTask()
        
        # 设置每天凌晨2点执行上传任务
        tomorrow_2am = datetime.now().replace(hour=2, minute=0, second=0, microsecond=0)
        if tomorrow_2am <= datetime.now():
            tomorrow_2am += timedelta(days=1)
        
        upload_rule = ScheduleRule(
            interval_seconds=24 * 3600,  # 每24小时执行一次
            max_executions=None,         # 无限次执行
            start_time=tomorrow_2am
        )
        
        self.scheduler.add_task(self.upload_task, upload_rule)
        
        # 3. 创建HTTP请求任务（每小时执行一次）
        self.http_task = HttpRequestTask()
        
        # 设置每小时执行HTTP请求任务
        next_hour = datetime.now().replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
        
        http_rule = ScheduleRule(
            interval_seconds=3600,  # 每小时执行一次
            max_executions=None,    # 无限次执行
            start_time=next_hour
        )
        
        self.scheduler.add_task(self.http_task, http_rule)
        
        self.logger.info("所有定时任务设置完成")
        self.logger.info(f"传感器任务: 立即启动，每小时检查状态")
        self.logger.info(f"上传任务: {tomorrow_2am.strftime('%Y-%m-%d %H:%M:%S')} 首次执行，之后每日执行")
        self.logger.info(f"HTTP请求任务: {next_hour.strftime('%Y-%m-%d %H:%M:%S')} 首次执行，之后每小时执行")
    
    def start_scheduler(self):
        """启动任务调度器"""
        try:
            self.logger.info("启动任务调度器...")
            
            # 立即启动传感器服务
            if self.sensor_task:
                self.logger.info("立即启动传感器数据采集服务...")
                result = self.sensor_task.execute()
                self.logger.info(f"传感器服务启动结果: {result}")
            
            # 启动调度器
            self.scheduler.start()
            self.logger.info("任务调度器启动成功")
            
        except Exception as e:
            self.logger.error(f"启动调度器失败: {e}")
            raise
    
    def stop_scheduler(self):
        """停止任务调度器"""
        try:
            self.logger.info("停止任务调度器...")
            
            # 停止传感器服务
            if self.sensor_task:
                self.sensor_task.stop_service()
            
            # 停止HTTP任务
            if self.http_task:
                self.http_task.cleanup()
            
            # 停止调度器
            self.scheduler.stop()
            self.logger.info("任务调度器已停止")
            
        except Exception as e:
            self.logger.error(f"停止调度器失败: {e}")
    
    def get_status(self) -> Dict[str, Any]:
        """获取所有任务状态"""
        status = {
            "scheduler_running": self.scheduler.is_running(),
            "tasks": {}
        }
        
        # 获取传感器任务状态
        if self.sensor_task:
            status["tasks"]["sensor_data"] = {
                "task_info": {
                    "id": self.sensor_task.task_id,
                    "name": self.sensor_task.name,
                    "status": self.scheduler.get_task_status(self.sensor_task.task_id)
                },
                "service_status": self.sensor_task.get_service_status()
            }
        
        # 获取上传任务状态
        if self.upload_task:
            status["tasks"]["data_upload"] = {
                "task_info": {
                    "id": self.upload_task.task_id,
                    "name": self.upload_task.name,
                    "status": self.scheduler.get_task_status(self.upload_task.task_id)
                }
            }
        
        # 获取HTTP任务状态
        if self.http_task:
            status["tasks"]["http_request"] = {
                "task_info": {
                    "id": self.http_task.task_id,
                    "name": self.http_task.name,
                    "status": self.scheduler.get_task_status(self.http_task.task_id)
                },
                "request_info": self.http_task.get_request_info()
            }
        
        return status
    
    def run_forever(self):
        """保持程序运行"""
        try:
            self.setup_tasks()
            self.start_scheduler()
            
            self.logger.info("定时任务系统运行中，按 Ctrl+C 停止...")
            
            # 保持主线程运行
            while True:
                time.sleep(10)
                
                # 定期打印状态信息
                if datetime.now().second % 60 == 0:  # 每分钟打印一次
                    status = self.get_status()
                    self.logger.info(f"系统状态: 调度器运行={status['scheduler_running']}")
                    
                    if "sensor_data" in status["tasks"]:
                        sensor_status = status["tasks"]["sensor_data"]["service_status"]
                        self.logger.info(f"传感器服务: 运行={sensor_status['running']}")
                
        except KeyboardInterrupt:
            self.logger.info("接收到中断信号，正在停止系统...")
        except Exception as e:
            self.logger.error(f"系统运行异常: {e}")
        finally:
            self.stop_scheduler()

def main():
    """主函数"""
    print("=" * 60)
    print("AI Japan 传感器数据采集与上传定时任务系统")
    print("=" * 60)
    print("功能说明:")
    print("1. 传感器数据采集: 后台持续运行，实时采集并记录传感器数据")
    print("2. 数据上传任务: 每日凌晨2点自动上传数据到服务器")
    print("3. HTTP请求任务: 每小时发送传感器数据到指定服务器")
    print("4. 任务监控: 自动监控任务状态，异常时自动重试")
    print("=" * 60)
    
    # 创建任务管理器
    task_manager = TaskManager()
    
    try:
        # 运行任务系统
        task_manager.run_forever()
    except Exception as e:
        print(f"系统启动失败: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())