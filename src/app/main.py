"""
应用入口：统一注册并启动任务调度器

任务包括：
- 传感器数据采集服务（后台线程，按固定间隔进行健康检查）
- 数据上传任务（脚本任务，执行 client/updata.py）
- 每小时HTTP告警任务（HttpRequestTask）
"""

import os
import sys
import logging
from datetime import datetime

from src.scheduler.task_scheduler import (
    TaskScheduler,
    ScheduleRule,
    ScheduleType,
    create_data_upload_task,
)

from src.tasks.sensor_data_task import SensorDataTask
from src.tasks.http_request_task import HttpRequestTask
from src.services.sensor_data_service import SensorDataService


def setup_scheduler() -> TaskScheduler:
    """创建并配置调度器实例"""
    # 使用 src/scheduler/scheduler_config.json 作为配置文件
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(project_root, "src", "scheduler", "scheduler_config.json")
    scheduler = TaskScheduler(config_file=config_path)
    return scheduler


def register_tasks(scheduler: TaskScheduler):
    """注册各类任务到调度器"""
    # 1) 传感器数据采集服务任务：每30秒进行一次健康检查（若未运行则启动）
    sensor_service = SensorDataService()
    sensor_task = SensorDataTask(service=sensor_service)
    scheduler.add_task(sensor_task, ScheduleRule(ScheduleType.INTERVAL, seconds=30))

    # 2) 数据上传任务：每10分钟执行一次（后续可在配置文件或环境变量中调整）
    upload_task = create_data_upload_task()
    scheduler.add_task(upload_task, ScheduleRule(ScheduleType.INTERVAL, seconds=600))

    # 3) 每小时HTTP请求告警任务
    http_task = HttpRequestTask(target_url="http://localhost:5002/api/messages/", sensor_service=sensor_service)
    scheduler.add_task(http_task, ScheduleRule(ScheduleType.INTERVAL, seconds=3600))


def main():
    # 简单日志设置（调度器内部也会初始化日志）
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    scheduler = setup_scheduler()
    register_tasks(scheduler)

    logging.info("任务已注册，准备启动调度器...")
    scheduler.start()

    # 主线程保持运行直到收到停止信号
    try:
        while True:
            # 可选：每60秒打印一次任务状态
            status = scheduler.get_task_status()
            logging.debug(f"调度器状态: {status}")
            import time
            time.sleep(60)
    except KeyboardInterrupt:
        logging.info("接收到中断信号，正在停止调度器...")
    finally:
        scheduler.stop()
        logging.info("调度器已停止")


if __name__ == "__main__":
    main()