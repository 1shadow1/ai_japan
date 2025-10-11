"""
CameraControllerTask
一次性任务：启动后台摄像头控制服务（键盘监听 + 录制 + 状态上报 + 抽帧上传）。

该任务在 ONCE 调度下执行一次后，服务线程将持续运行直到调度器停止。
"""

from __future__ import annotations

import logging
from src.scheduler.task_scheduler import BaseTask
from src.services.camera_controller_service import CameraControllerService


class CameraControllerTask(BaseTask):
    def __init__(self):
        super().__init__(
            task_id="camera_controller",
            name="摄像头键盘控制服务",
            description="键盘监听、摄像头录制、状态上报、抽帧上传的持续后台服务",
        )
        self.logger = logging.getLogger("CameraControllerTask")
        self.service = CameraControllerService()

    def execute(self) -> bool:
        try:
            if not self.service.is_running():
                self.service.start()
                self.logger.info("摄像头控制服务已启动")
            else:
                self.logger.debug("摄像头控制服务已在运行，跳过重复启动")
            return True
        except Exception as e:
            self.logger.error(f"启动摄像头控制服务异常: {e}")
            self.last_error = str(e)
            return False