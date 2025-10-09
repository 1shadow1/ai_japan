"""
任务调度器使用示例
展示如何创建和管理各种类型的定时任务
"""

import time
import logging
from datetime import datetime, timedelta
from task_scheduler import (
    TaskScheduler, BaseTask, ScriptTask, FunctionTask,
    ScheduleRule, ScheduleType, TaskStatus
)

# ==================== 自定义任务示例 ====================

class DatabaseBackupTask(BaseTask):
    """数据库备份任务示例"""
    
    def __init__(self, task_id: str, db_config: dict):
        super().__init__(
            task_id=task_id,
            name="数据库备份任务",
            description="定期备份数据库数据"
        )
        self.db_config = db_config
    
    def execute(self) -> bool:
        """执行数据库备份"""
        try:
            logging.info("开始数据库备份...")
            
            # 模拟备份过程
            backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql"
            
            # 这里应该是实际的数据库备份逻辑
            # 例如：mysqldump 或 pg_dump 命令
            time.sleep(2)  # 模拟备份耗时
            
            logging.info(f"数据库备份完成: {backup_file}")
            return True
            
        except Exception as e:
            logging.error(f"数据库备份失败: {e}")
            return False

class SystemMonitorTask(BaseTask):
    """系统监控任务示例"""
    
    def __init__(self, task_id: str):
        super().__init__(
            task_id=task_id,
            name="系统监控任务",
            description="监控系统资源使用情况"
        )
    
    def execute(self) -> bool:
        """执行系统监控"""
        try:
            import psutil
            
            # 获取系统信息
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            logging.info(f"系统监控 - CPU: {cpu_percent}%, 内存: {memory.percent}%, 磁盘: {disk.percent}%")
            
            # 检查是否有资源使用过高的情况
            if cpu_percent > 80 or memory.percent > 80 or disk.percent > 90:
                logging.warning("系统资源使用率过高！")
            
            return True
            
        except ImportError:
            logging.warning("psutil模块未安装，跳过系统监控")
            return True
        except Exception as e:
            logging.error(f"系统监控失败: {e}")
            return False

# ==================== 函数任务示例 ====================

def send_daily_report():
    """发送日报的示例函数"""
    try:
        logging.info("生成并发送日报...")
        
        # 模拟生成报告
        report_data = {
            "date": datetime.now().strftime("%Y-%m-%d"),
            "sensor_readings": 1234,
            "upload_success": 98.5,
            "system_uptime": "99.9%"
        }
        
        # 这里应该是实际的报告生成和发送逻辑
        time.sleep(1)  # 模拟处理时间
        
        logging.info(f"日报发送成功: {report_data}")
        return True
        
    except Exception as e:
        logging.error(f"日报发送失败: {e}")
        return False

def check_network_connectivity():
    """检查网络连接的示例函数"""
    import subprocess
    import platform
    
    try:
        # 根据操作系统选择ping命令
        param = '-n' if platform.system().lower() == 'windows' else '-c'
        command = ['ping', param, '1', '8.8.8.8']
        
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            logging.info("网络连接正常")
            return True
        else:
            logging.warning("网络连接异常")
            return False
            
    except Exception as e:
        logging.error(f"网络检查失败: {e}")
        return False

# ==================== 使用示例 ====================

def example_basic_usage():
    """基本使用示例"""
    print("=== 基本使用示例 ===")
    
    # 创建调度器
    scheduler = TaskScheduler()
    
    # 1. 创建脚本任务
    script_task = ScriptTask(
        task_id="example_script",
        name="示例脚本任务",
        script_path="client/updata.py",
        description="执行数据上传脚本"
    )
    
    # 每10秒执行一次
    script_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=10)
    scheduler.add_task(script_task, script_schedule)
    
    # 2. 创建函数任务
    function_task = FunctionTask(
        task_id="network_check",
        name="网络检查任务",
        func=check_network_connectivity,
        description="检查网络连接状态"
    )
    
    # 每30秒执行一次
    function_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=30)
    scheduler.add_task(function_task, function_schedule)
    
    # 3. 创建自定义任务
    monitor_task = SystemMonitorTask("system_monitor")
    monitor_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=60)
    scheduler.add_task(monitor_task, monitor_schedule)
    
    # 启动调度器
    scheduler.start()
    
    try:
        # 运行30秒后停止
        time.sleep(30)
    finally:
        scheduler.stop()

def example_advanced_usage():
    """高级使用示例"""
    print("=== 高级使用示例 ===")
    
    scheduler = TaskScheduler("advanced_config.json")
    
    # 1. 一次性任务
    one_time_task = FunctionTask(
        task_id="startup_check",
        name="启动检查任务",
        func=lambda: print("系统启动检查完成"),
        description="系统启动时执行一次的检查任务"
    )
    
    # 5秒后执行一次
    one_time_schedule = ScheduleRule(
        ScheduleType.ONCE, 
        run_at=datetime.now() + timedelta(seconds=5)
    )
    scheduler.add_task(one_time_task, one_time_schedule)
    
    # 2. 数据库备份任务
    backup_task = DatabaseBackupTask(
        task_id="db_backup",
        db_config={"host": "localhost", "port": 3306}
    )
    
    # 每小时备份一次
    backup_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=3600)
    scheduler.add_task(backup_task, backup_schedule)
    
    # 3. 日报任务
    report_task = FunctionTask(
        task_id="daily_report",
        name="日报任务",
        func=send_daily_report,
        description="每天发送系统运行报告"
    )
    
    # 每24小时执行一次
    report_schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=86400)
    scheduler.add_task(report_task, report_schedule)
    
    scheduler.start()
    
    # 演示任务管理
    print("\n=== 任务状态监控 ===")
    for i in range(3):
        time.sleep(10)
        status = scheduler.get_task_status()
        print(f"\n第{i+1}次检查 - 运行中的任务: {status['running_tasks']}")
        
        for task_id, task_info in status['tasks'].items():
            print(f"  {task_info['name']}: {task_info['status']}")
    
    scheduler.stop()

def example_task_management():
    """任务管理示例"""
    print("=== 任务管理示例 ===")
    
    scheduler = TaskScheduler()
    
    # 添加多个任务
    tasks = [
        (FunctionTask("task1", "任务1", lambda: print("执行任务1")), 
         ScheduleRule(ScheduleType.INTERVAL, seconds=5)),
        (FunctionTask("task2", "任务2", lambda: print("执行任务2")), 
         ScheduleRule(ScheduleType.INTERVAL, seconds=8)),
        (FunctionTask("task3", "任务3", lambda: print("执行任务3")), 
         ScheduleRule(ScheduleType.INTERVAL, seconds=12))
    ]
    
    for task, schedule in tasks:
        scheduler.add_task(task, schedule)
    
    scheduler.start()
    
    try:
        # 运行15秒
        time.sleep(15)
        
        # 移除一个任务
        print("\n移除任务2...")
        scheduler.remove_task("task2")
        
        # 继续运行15秒
        time.sleep(15)
        
        # 查看最终状态
        print("\n=== 最终任务状态 ===")
        status = scheduler.get_task_status()
        for task_id, task_info in status['tasks'].items():
            print(f"{task_info['name']}: 执行{task_info['run_count']}次, 成功率{task_info['success_rate']}")
            
    finally:
        scheduler.stop()

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("任务调度器使用示例")
    print("1. 基本使用")
    print("2. 高级功能")
    print("3. 任务管理")
    
    choice = input("请选择示例 (1-3): ").strip()
    
    if choice == "1":
        example_basic_usage()
    elif choice == "2":
        example_advanced_usage()
    elif choice == "3":
        example_task_management()
    else:
        print("无效选择，运行基本示例...")
        example_basic_usage()