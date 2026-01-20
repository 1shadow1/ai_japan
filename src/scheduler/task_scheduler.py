"""
日本养殖项目 - 企业级定时任务调度器
功能：支持多种频率的定时任务调度，包括数据采集、文件上传、系统维护等
作者：AI Assistant
版本：1.0
创建时间：2024
"""

import os
import sys
import json
import time
import logging
import threading
import signal
from datetime import datetime, timedelta
from typing import Dict, List, Callable, Optional, Any
from abc import ABC, abstractmethod
from functools import wraps
from concurrent.futures import ThreadPoolExecutor, Future
import subprocess
from enum import Enum

# ==================== 枚举定义 ====================
class TaskStatus(Enum):
    """任务状态枚举"""
    PENDING = "pending"      # 等待执行
    RUNNING = "running"      # 正在执行
    COMPLETED = "completed"  # 执行完成
    FAILED = "failed"        # 执行失败
    STOPPED = "stopped"      # 已停止
    DISABLED = "disabled"    # 已禁用

class ScheduleType(Enum):
    """调度类型枚举"""
    INTERVAL = "interval"    # 间隔调度
    CRON = "cron"           # Cron表达式调度
    ONCE = "once"           # 一次性任务

# ==================== 配置管理类 ====================
class SchedulerConfig:
    """调度器配置管理类"""
    
    def __init__(self, config_file: str = "scheduler_config.json"):
        self.config_file = config_file
        self.config = self._load_default_config()
        self._load_config()
    
    def _load_default_config(self) -> dict:
        """加载默认配置"""
        return {
            "scheduler": {
                "max_workers": 10,
                "check_interval": 1,  # 秒
                "enable_monitoring": True,
                "log_level": "INFO"
            },
            "tasks": {
                "default_timeout": 300,  # 5分钟
                "max_retries": 3,
                "retry_delay": 5
            },
            "logging": {
                "log_dir": "logs",
                "log_file": "scheduler.log",
                "max_log_size": "10MB",
                "backup_count": 5
            }
        }
    
    def _load_config(self):
        """从文件加载配置"""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                    self._merge_config(self.config, file_config)
                logging.info(f"配置文件加载成功: {self.config_file}")
            except Exception as e:
                logging.warning(f"配置文件加载失败，使用默认配置: {e}")
        else:
            self.save_config()
    
    def _merge_config(self, default: dict, override: dict):
        """递归合并配置"""
        for key, value in override.items():
            if key in default and isinstance(default[key], dict) and isinstance(value, dict):
                self._merge_config(default[key], value)
            else:
                default[key] = value
    
    def save_config(self):
        """保存配置到文件"""
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4, ensure_ascii=False)
            logging.info(f"配置文件保存成功: {self.config_file}")
        except Exception as e:
            logging.error(f"配置文件保存失败: {e}")
    
    def get(self, key_path: str, default=None):
        """获取配置值，支持点分隔的路径"""
        keys = key_path.split('.')
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

# ==================== 任务基类 ====================
class BaseTask(ABC):
    """任务基类，所有任务都应继承此类"""
    
    def __init__(self, task_id: str, name: str, description: str = ""):
        self.task_id = task_id
        self.name = name
        self.description = description
        self.status = TaskStatus.PENDING
        self.last_run = None
        self.next_run = None
        self.run_count = 0
        self.success_count = 0
        self.failure_count = 0
        self.last_error = None
        self.created_at = datetime.now()
        self.updated_at = datetime.now()
    
    @abstractmethod
    def execute(self) -> bool:
        """
        执行任务的具体逻辑
        
        Returns:
            bool: 执行是否成功
        """
        pass
    
    def get_status_info(self) -> dict:
        """获取任务状态信息"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "run_count": self.run_count,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "success_rate": f"{(self.success_count / max(self.run_count, 1)) * 100:.1f}%",
            "last_error": self.last_error,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat()
        }

# ==================== 具体任务实现 ====================
class ScriptTask(BaseTask):
    """脚本执行任务"""
    
    def __init__(self, task_id: str, name: str, script_path: str, 
                 args: List[str] = None, working_dir: str = None, 
                 timeout: int = 300, description: str = ""):
        super().__init__(task_id, name, description)
        self.script_path = script_path
        self.args = args or []
        self.working_dir = working_dir or os.getcwd()
        self.timeout = timeout
    
    def execute(self) -> bool:
        """执行脚本文件"""
        try:
            cmd = [sys.executable, self.script_path] + self.args
            logging.info(f"执行脚本任务: {self.name} - {' '.join(cmd)}")
            
            result = subprocess.run(
                cmd,
                cwd=self.working_dir,
                timeout=self.timeout,
                capture_output=True,
                text=True
            )
            
            if result.returncode == 0:
                logging.info(f"脚本任务执行成功: {self.name}")
                if result.stdout:
                    logging.debug(f"脚本输出: {result.stdout}")
                return True
            else:
                error_msg = f"脚本执行失败，返回码: {result.returncode}"
                if result.stderr:
                    error_msg += f", 错误信息: {result.stderr}"
                logging.error(error_msg)
                self.last_error = error_msg
                return False
                
        except subprocess.TimeoutExpired:
            error_msg = f"脚本执行超时 ({self.timeout}秒)"
            logging.error(error_msg)
            self.last_error = error_msg
            return False
        except Exception as e:
            error_msg = f"脚本执行异常: {str(e)}"
            logging.error(error_msg)
            self.last_error = error_msg
            return False

class FunctionTask(BaseTask):
    """函数执行任务"""
    
    def __init__(self, task_id: str, name: str, func: Callable, 
                 args: tuple = (), kwargs: dict = None, description: str = ""):
        super().__init__(task_id, name, description)
        self.func = func
        self.args = args
        self.kwargs = kwargs or {}
    
    def execute(self) -> bool:
        """执行函数"""
        try:
            logging.info(f"执行函数任务: {self.name}")
            result = self.func(*self.args, **self.kwargs)
            
            # 如果函数返回布尔值，使用它作为成功标志
            if isinstance(result, bool):
                success = result
            else:
                # 否则认为没有异常就是成功
                success = True
            
            if success:
                logging.info(f"函数任务执行成功: {self.name}")
            else:
                logging.warning(f"函数任务执行失败: {self.name}")
                self.last_error = "函数返回False"
            
            return success
            
        except Exception as e:
            error_msg = f"函数执行异常: {str(e)}"
            logging.error(error_msg)
            self.last_error = error_msg
            return False

# ==================== 调度规则类 ====================
class ScheduleRule:
    """调度规则类，定义任务的执行时间规则"""
    
    def __init__(self, schedule_type: ScheduleType, **kwargs):
        self.schedule_type = schedule_type
        self.params = kwargs
        self._validate_params()
    
    def _validate_params(self):
        """验证调度参数"""
        if self.schedule_type == ScheduleType.INTERVAL:
            if 'seconds' not in self.params:
                raise ValueError("间隔调度必须指定seconds参数")
            if self.params['seconds'] <= 0:
                raise ValueError("间隔时间必须大于0")
        elif self.schedule_type == ScheduleType.ONCE:
            if 'run_at' not in self.params:
                raise ValueError("一次性任务必须指定run_at参数")
    
    def get_next_run_time(self, last_run: Optional[datetime] = None) -> Optional[datetime]:
        """
        计算下次执行时间
        
        Args:
            last_run: 上次执行时间
            
        Returns:
            下次执行时间，如果不再执行则返回None
        """
        now = datetime.now()
        
        if self.schedule_type == ScheduleType.INTERVAL:
            if last_run is None:
                return now
            return last_run + timedelta(seconds=self.params['seconds'])
        
        elif self.schedule_type == ScheduleType.ONCE:
            run_at = self.params['run_at']
            if isinstance(run_at, str):
                run_at = datetime.fromisoformat(run_at)
            
            if last_run is None and run_at > now:
                return run_at
            return None  # 一次性任务执行后不再执行
        
        return None

# ==================== 任务调度器 ====================
class TaskScheduler:
    """企业级任务调度器"""
    
    def __init__(self, config_file: str = "scheduler_config.json"):
        self.config = SchedulerConfig(config_file)
        self.tasks: Dict[str, BaseTask] = {}
        self.schedules: Dict[str, ScheduleRule] = {}
        self.running = False
        self.executor = None
        self.scheduler_thread = None
        self.futures: Dict[str, Future] = {}
        # 停止事件，用于在退出时打断重试等待，提升优雅关闭速度
        self.stop_event: threading.Event = threading.Event()
        
        # 设置日志
        self._setup_logging()
        
        # 注册信号处理
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logging.info("任务调度器初始化完成")
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = self.config.get('logging.log_dir', 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, self.config.get('logging.log_file', 'scheduler.log'))
        log_level = getattr(logging, self.config.get('scheduler.log_level', 'INFO'))
        
        # 配置日志格式
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
        )
        
        # 文件处理器
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        
        # 配置根日志器（先清理已有处理器以避免重复输出）
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)
        for h in list(root_logger.handlers):
            try:
                root_logger.removeHandler(h)
            except Exception:
                pass
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)
    
    def _signal_handler(self, signum, frame):
        """信号处理器，用于优雅关闭"""
        logging.info(f"接收到信号 {signum}，开始优雅关闭...")
        self.stop()
    
    def add_task(self, task: BaseTask, schedule_rule: ScheduleRule):
        """
        添加任务到调度器
        
        Args:
            task: 任务实例
            schedule_rule: 调度规则
        """
        if task.task_id in self.tasks:
            raise ValueError(f"任务ID已存在: {task.task_id}")
        
        self.tasks[task.task_id] = task
        self.schedules[task.task_id] = schedule_rule
        
        # 计算首次执行时间
        task.next_run = schedule_rule.get_next_run_time()
        task.updated_at = datetime.now()
        
        logging.info(f"任务添加成功: {task.name} (ID: {task.task_id})")
        
        if task.next_run:
            logging.info(f"下次执行时间: {task.next_run}")
    
    def remove_task(self, task_id: str) -> bool:
        """
        移除任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否移除成功
        """
        if task_id not in self.tasks:
            logging.warning(f"任务不存在: {task_id}")
            return False
        
        # 如果任务正在执行，先停止它
        if task_id in self.futures:
            future = self.futures[task_id]
            if not future.done():
                future.cancel()
            del self.futures[task_id]
        
        # 移除任务
        task_name = self.tasks[task_id].name
        del self.tasks[task_id]
        del self.schedules[task_id]
        
        logging.info(f"任务移除成功: {task_name} (ID: {task_id})")
        return True
    
    def start(self):
        """启动调度器"""
        if self.running:
            logging.warning("调度器已在运行中")
            return
        
        self.running = True
        # 清除停止事件，进入运行状态
        self.stop_event.clear()
        max_workers = self.config.get('scheduler.max_workers', 10)
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        
        # 启动调度线程
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()
        
        logging.info(f"任务调度器启动成功，最大工作线程数: {max_workers}")
    
    def stop(self):
        """停止调度器"""
        if not self.running:
            return
        
        logging.info("正在停止任务调度器...")
        self.running = False
        # 触发停止事件以打断任务重试/睡眠
        try:
            self.stop_event.set()
        except Exception:
            pass
        
        # 等待调度线程结束
        if self.scheduler_thread and self.scheduler_thread.is_alive():
            self.scheduler_thread.join(timeout=5)

        # 优雅停止各任务的后台线程/资源（如果任务实现了对应的停止方法）
        for task in list(self.tasks.values()):
            for method_name in ("stop_stream", "stop_service", "stop"):
                try:
                    method = getattr(task, method_name, None)
                    if callable(method):
                        logging.info(f"调用任务清理方法: {task.name}.{method_name}()")
                        method()
                except Exception as e:
                    logging.warning(f"调用 {task.name}.{method_name}() 失败: {e}")

        # 关闭线程池
        if self.executor:
            try:
                import sys
                if sys.version_info >= (3, 9):
                    self.executor.shutdown(wait=True, cancel_futures=True)
                else:
                    self.executor.shutdown(wait=True)
            except TypeError:
                # 兼容旧版本不支持 cancel_futures 参数
                self.executor.shutdown(wait=True)
        
        # 更新所有运行中任务的状态
        for task in self.tasks.values():
            if task.status == TaskStatus.RUNNING:
                task.status = TaskStatus.STOPPED
                task.updated_at = datetime.now()
        
        logging.info("任务调度器已停止")
    
    def _scheduler_loop(self):
        """调度器主循环"""
        check_interval = self.config.get('scheduler.check_interval', 1)
        
        while self.running:
            try:
                now = datetime.now()
                
                # 检查需要执行的任务
                for task_id, task in self.tasks.items():
                    if (task.next_run and 
                        task.next_run <= now and 
                        task.status not in [TaskStatus.RUNNING, TaskStatus.DISABLED]):
                        
                        self._execute_task(task_id)
                
                # 清理已完成的Future
                self._cleanup_futures()
                
                time.sleep(check_interval)
                
            except Exception as e:
                logging.error(f"调度器循环异常: {e}")
                time.sleep(check_interval)
    
    def _execute_task(self, task_id: str):
        """执行任务"""
        task = self.tasks[task_id]
        schedule_rule = self.schedules[task_id]
        
        # 更新任务状态
        task.status = TaskStatus.RUNNING
        task.last_run = datetime.now()
        task.run_count += 1
        task.updated_at = datetime.now()
        
        # logging.info(f"开始执行任务: {task.name} (第{task.run_count}次)")
        
        # 提交任务到线程池
        future = self.executor.submit(self._run_task_with_retry, task)
        self.futures[task_id] = future
        
        # 计算下次执行时间
        task.next_run = schedule_rule.get_next_run_time(task.last_run)
    
    def _run_task_with_retry(self, task: BaseTask):
        """带重试机制的任务执行"""
        max_retries = self.config.get('tasks.max_retries', 3)
        retry_delay = self.config.get('tasks.retry_delay', 5)
        
        for attempt in range(max_retries + 1):
            # 如果已经收到停止信号，直接结束任务
            if not self.running or (hasattr(self, 'stop_event') and self.stop_event.is_set()):
                task.status = TaskStatus.STOPPED
                task.updated_at = datetime.now()
                logging.info(f"停止重试并中止任务: {task.name}")
                return
            try:
                success = task.execute()
                
                if success:
                    task.status = TaskStatus.COMPLETED
                    task.success_count += 1
                    task.last_error = None
                    # logging.info(f"任务执行成功: {task.name}")
                    return
                else:
                    if attempt < max_retries:
                        logging.warning(f"任务执行失败，{retry_delay}秒后重试 (第{attempt + 1}/{max_retries}次): {task.name}")
                        # 使用事件等待以便在停止时立即打断
                        if hasattr(self, 'stop_event'):
                            self.stop_event.wait(retry_delay)
                        else:
                            time.sleep(retry_delay)
                    else:
                        task.status = TaskStatus.FAILED
                        task.failure_count += 1
                        logging.error(f"任务执行失败，已达最大重试次数: {task.name}")
                        
            except Exception as e:
                error_msg = f"任务执行异常: {str(e)}"
                task.last_error = error_msg
                
                if attempt < max_retries:
                    logging.warning(f"{error_msg}，{retry_delay}秒后重试 (第{attempt + 1}/{max_retries}次): {task.name}")
                    # 使用事件等待以便在停止时立即打断
                    if hasattr(self, 'stop_event'):
                        self.stop_event.wait(retry_delay)
                    else:
                        time.sleep(retry_delay)
                else:
                    task.status = TaskStatus.FAILED
                    task.failure_count += 1
                    logging.error(f"{error_msg}，已达最大重试次数: {task.name}")
        
        task.updated_at = datetime.now()
    
    def _cleanup_futures(self):
        """清理已完成的Future对象"""
        completed_tasks = []
        for task_id, future in self.futures.items():
            if future.done():
                completed_tasks.append(task_id)
        
        for task_id in completed_tasks:
            del self.futures[task_id]
    
    def get_task_status(self, task_id: str = None) -> Dict[str, Any]:
        """
        获取任务状态信息
        
        Args:
            task_id: 任务ID，如果为None则返回所有任务状态
            
        Returns:
            任务状态信息
        """
        if task_id:
            if task_id not in self.tasks:
                return {"error": f"任务不存在: {task_id}"}
            return self.tasks[task_id].get_status_info()
        else:
            return {
                "scheduler_status": "running" if self.running else "stopped",
                "total_tasks": len(self.tasks),
                "running_tasks": len([t for t in self.tasks.values() if t.status == TaskStatus.RUNNING]),
                "tasks": {tid: task.get_status_info() for tid, task in self.tasks.items()}
            }

# ==================== 预定义任务函数 ====================
def create_data_upload_task() -> ScriptTask:
    """创建数据上传任务"""
    return ScriptTask(
        task_id="data_upload",
        name="数据上传任务",
        script_path="client/updata.py",
        description="定期上传传感器数据和操作日志"
    )

def create_sensor_collection_task() -> ScriptTask:
    """创建传感器数据采集任务"""
    return ScriptTask(
        task_id="sensor_collection",
        name="传感器数据采集",
        script_path="sensor_data_collection.py",
        description="采集PH、溶解氧、液位、浊度等传感器数据"
    )

def create_heartbeat_task() -> ScriptTask:
    """创建心跳检测任务"""
    return ScriptTask(
        task_id="heartbeat",
        name="心跳检测",
        script_path="client/heart_beat.py",
        description="定期发送心跳信号确认系统状态"
    )

def create_log_cleanup_task() -> FunctionTask:
    """创建日志清理任务"""
    def cleanup_logs():
        """清理7天前的日志文件"""
        log_dir = "logs"
        if not os.path.exists(log_dir):
            return True
        
        cutoff_time = datetime.now() - timedelta(days=7)
        cleaned_count = 0
        
        for filename in os.listdir(log_dir):
            filepath = os.path.join(log_dir, filename)
            if os.path.isfile(filepath):
                file_time = datetime.fromtimestamp(os.path.getmtime(filepath))
                if file_time < cutoff_time:
                    try:
                        os.remove(filepath)
                        cleaned_count += 1
                        logging.info(f"删除过期日志文件: {filename}")
                    except Exception as e:
                        logging.error(f"删除日志文件失败: {filename} - {e}")
        
        logging.info(f"日志清理完成，删除了{cleaned_count}个文件")
        return True
    
    return FunctionTask(
        task_id="log_cleanup",
        name="日志清理任务",
        func=cleanup_logs,
        description="清理7天前的日志文件"
    )

# ==================== 主程序 ====================
def main():
    """主程序入口"""
    print("=" * 60)
    print("日本养殖项目 - 企业级定时任务调度器")
    print("=" * 60)
    
    # 创建调度器
    scheduler = TaskScheduler()
    
    try:
        # 添加预定义任务
        
        # 1. 数据上传任务 - 每小时执行一次
        upload_task = create_data_upload_task()
        upload_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=3600)  # 1小时
        scheduler.add_task(upload_task, upload_schedule)
        
        # 2. 传感器数据采集 - 每5分钟执行一次
        sensor_task = create_sensor_collection_task()
        sensor_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=300)  # 5分钟
        scheduler.add_task(sensor_task, sensor_schedule)
        
        # 3. 心跳检测 - 每30秒执行一次
        heartbeat_task = create_heartbeat_task()
        heartbeat_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=30)  # 30秒
        scheduler.add_task(heartbeat_task, heartbeat_schedule)
        
        # 4. 日志清理 - 每天凌晨2点执行（这里简化为每24小时）
        cleanup_task = create_log_cleanup_task()
        cleanup_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=86400)  # 24小时
        scheduler.add_task(cleanup_task, cleanup_schedule)
        
        # 启动调度器
        scheduler.start()
        
        print("\n调度器已启动，按 Ctrl+C 停止")
        print("\n当前任务列表:")
        status = scheduler.get_task_status()
        for task_id, task_info in status['tasks'].items():
            print(f"- {task_info['name']} (ID: {task_id})")
            print(f"  状态: {task_info['status']}")
            print(f"  下次执行: {task_info['next_run']}")
            print()
        
        # 保持程序运行
        while scheduler.running:
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在停止调度器...")
    except Exception as e:
        logging.error(f"程序异常: {e}")
    finally:
        scheduler.stop()
        print("调度器已停止，程序退出")

if __name__ == "__main__":
    main()