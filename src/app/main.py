"""
应用入口：统一注册并启动任务调度器
使用统一配置管理
"""

import os
import sys
import logging
from datetime import datetime, timedelta

from src.scheduler.task_scheduler import (
    TaskScheduler,
    ScheduleRule,
    ScheduleType,
)

from src.tasks.sensor_data_task import SensorDataTask
from src.services.sensor_data_service_v2 import SensorDataServiceV2
from src.tasks.feed_device_status_task import FeedDeviceStatusTask
from src.tasks.feed_device_schedule_task import FeedDeviceScheduleTask
from src.tasks.camera_controller_task import CameraControllerTask
from src.config.config_manager import config_manager


def setup_scheduler() -> TaskScheduler:
    """创建并配置调度器实例"""
    # 使用 src/scheduler/scheduler_config.json 作为配置文件
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.join(project_root, "src", "scheduler", "scheduler_config.json")
    scheduler = TaskScheduler(config_file=config_path)
    return scheduler


def register_tasks(scheduler: TaskScheduler):
    """注册各类任务到调度器"""
    config = config_manager
    
    # 1) 传感器数据采集服务任务（使用V2服务）
    sensor_service = SensorDataServiceV2(simulate=True)
    sensor_task = SensorDataTask(service=sensor_service)
    health_check_interval = config.get("tasks.sensor_health_check_interval_seconds", 60)
    scheduler.add_task(sensor_task, ScheduleRule(ScheduleType.INTERVAL, seconds=health_check_interval))

    # 4) 喂食机状态上报任务
    feeder_config = config.get_feeder_config()
    status_interval = feeder_config.get("status_check_interval_seconds", 600)
    feed_status_task = FeedDeviceStatusTask()
    scheduler.add_task(feed_status_task, ScheduleRule(ScheduleType.INTERVAL, seconds=status_interval))
    logging.info(f"已注册喂食机状态上报任务：interval={status_interval}s")

    # 5) 喂食机定时投喂任务
    schedule_check_interval = feeder_config.get("schedule_check_interval_seconds", 60)
    schedule = feeder_config.get("schedule", [])
    logging.info(f"喂食机定时投喂注册：schedule_check_interval={schedule_check_interval}s, items={len(schedule)}")
    
    for idx, schedule_item in enumerate(schedule):
        feed_task = FeedDeviceScheduleTask()
        feed_task.task_id = f"feed_device_schedule_{idx}"
        feed_task.feed_count = schedule_item.get("feed_count", 1)
        feed_task.times = schedule_item.get("times", [])
        logging.info(f"注册投喂计划[{idx}]：times={feed_task.times}, feed_count={feed_task.feed_count}")
        scheduler.add_task(feed_task, ScheduleRule(ScheduleType.INTERVAL, seconds=schedule_check_interval))

    # 6) 摄像头键盘控制服务：一次性任务启动持续后台线程
    cam_task = CameraControllerTask()
    cam_start_delay = config.get("tasks.camera_service_start_delay_seconds", 1)
    run_time_cam = (datetime.now() + timedelta(seconds=cam_start_delay)).isoformat()
    scheduler.add_task(cam_task, ScheduleRule(ScheduleType.ONCE, run_at=run_time_cam))
    logging.info(f"已注册摄像头控制任务：start_delay={cam_start_delay}s")


def main():
    # 日志由 TaskScheduler 统一配置，这里不再调用 basicConfig 以避免重复输出
    # 如需调整日志级别/格式，请修改 src/scheduler/task_scheduler.py 的 _setup_logging
    scheduler = setup_scheduler()
    register_tasks(scheduler)

    logging.info("任务已注册，准备启动调度器...")
    scheduler.start()

    # 主线程保持运行直到收到停止信号
    try:
        import time
        counter = 0
        # 当调度器处于运行状态时保持主线程活跃；SIGINT 信号将由调度器处理并置 running=False
        while scheduler.running:
            time.sleep(1)
            counter += 1
            # 每60秒打印一次任务状态
            if counter % 60 == 0:
                status = scheduler.get_task_status()
                logging.debug(f"调度器状态: {status}")
    except KeyboardInterrupt:
        # 如果未覆盖 SIGINT，仍可优雅退出
        logging.info("接收到中断信号，正在停止调度器...")
    finally:
        scheduler.stop()
        logging.info("调度器已停止")


if __name__ == "__main__":
    main()
