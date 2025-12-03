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
    create_data_upload_task,
)

from src.tasks.sensor_data_task import SensorDataTask
from src.tasks.sensor_data_stream_task import SensorDataStreamTask
from src.services.sensor_data_service import SensorDataService
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
    
    # 1) 传感器数据采集服务任务
    sensor_sample_interval = config.get("sensors.sample_interval_seconds", 600)
    sensor_service = SensorDataService(sample_interval_seconds=sensor_sample_interval)
    sensor_task = SensorDataTask(service=sensor_service)
    health_check_interval = config.get("tasks.sensor_health_check_interval_seconds", 60)
    scheduler.add_task(sensor_task, ScheduleRule(ScheduleType.INTERVAL, seconds=health_check_interval))

    # 2) 数据上传任务（批量上传）
    upload_task = create_data_upload_task()
    batch_upload_interval = config.get("upload.batch_upload_interval_seconds", 600)
    scheduler.add_task(upload_task, ScheduleRule(ScheduleType.INTERVAL, seconds=batch_upload_interval))

    # 3) 持续传感器数据流式上传任务：启动一次，后台线程按固定频率推送
    stream_task = SensorDataStreamTask(
        service=sensor_service,
        interval_seconds=config.get("upload.stream_interval_seconds", 600),
    )
    # ONCE 任务需指定 run_at：设为当前时间+延迟，确保立即触发
    start_delay = config.get("tasks.sensor_stream_start_delay_seconds", 1)
    run_time = (datetime.now() + timedelta(seconds=start_delay)).isoformat()
    scheduler.add_task(stream_task, ScheduleRule(ScheduleType.ONCE, run_at=run_time))

    # 4) 喂食机状态上报任务
    feeder_config = config.get_feeder_config()
    status_interval = feeder_config.get("status_check_interval_seconds", 600)
    feed_status_task = FeedDeviceStatusTask()
    scheduler.add_task(feed_status_task, ScheduleRule(ScheduleType.INTERVAL, seconds=status_interval))

    # 5) 喂食机定时投喂任务
    schedule_check_interval = feeder_config.get("schedule_check_interval_seconds", 60)
    schedule = feeder_config.get("schedule", [])
    
    for idx, schedule_item in enumerate(schedule):
        feed_task = FeedDeviceScheduleTask()
        feed_task.task_id = f"feed_device_schedule_{idx}"
        feed_task.feed_count = schedule_item.get("feed_count", 1)
        feed_task.times = schedule_item.get("times", [])
        scheduler.add_task(feed_task, ScheduleRule(ScheduleType.INTERVAL, seconds=schedule_check_interval))

    # 6) 摄像头键盘控制服务：一次性任务启动持续后台线程
    cam_task = CameraControllerTask()
    cam_start_delay = config.get("tasks.camera_service_start_delay_seconds", 1)
    run_time_cam = (datetime.now() + timedelta(seconds=cam_start_delay)).isoformat()
    scheduler.add_task(cam_task, ScheduleRule(ScheduleType.ONCE, run_at=run_time_cam))


def main():
    # 简单日志设置（调度器内部也会初始化日志）
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

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
