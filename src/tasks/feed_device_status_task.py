"""
FeedDeviceStatusTask
每隔固定时间（默认10分钟）查询 devName='AI' 的喂食机状态，并发送到服务端。

环境变量：
- AIJ_FEED_STATUS_URL: 状态上报URL（默认 http://8.216.33.92:5000/api/feed_device_status）
- AIJ_FEEDER_DEV_NAME: 设备名（默认 "AI"）
"""

from __future__ import annotations

import os
import logging
from typing import Optional, Dict, Any

try:
    import requests
except Exception:
    requests = None

from src.scheduler.task_scheduler import BaseTask
from src.services.feeder_service import FeederService


class FeedDeviceStatusTask(BaseTask):
    def __init__(self, service: Optional[FeederService] = None):
        super().__init__(
            task_id="feed_device_status",
            name="喂食机状态上报",
            description="定期查询指定喂食机的状态并上报到服务端",
        )
        self.logger = logging.getLogger("FeedDeviceStatusTask")
        self.service = service or FeederService()
        self.target_dev_name = os.getenv("AIJ_FEEDER_DEV_NAME", "AI").strip() or "AI"
        self.status_url = os.getenv("AIJ_FEED_STATUS_URL", "http://8.216.33.92:5000/api/feed_device_status").strip()
        self.last_payload: Optional[Dict[str, Any]] = None

    def execute(self) -> bool:
        try:
            if requests is None:
                raise RuntimeError("requests 未安装，无法上报状态")

            dev_id = self.service.get_ai_device_id(self.target_dev_name)
            if not dev_id:
                self.logger.error(f"未找到设备 devName='{self.target_dev_name}'")
                return False

            status = self.service.get_device_status(dev_id)
            if status is None:
                self.logger.error("获取设备状态失败")
                return False

            payload = FeederService.build_status_payload(dev_id, self.target_dev_name, status)
            self.last_payload = payload

            self.logger.info(f"上报喂食机状态到 {self.status_url}")
            resp = requests.post(self.status_url, json=payload, timeout=15)
            if resp.status_code in (200, 201):
                self.logger.info("✓ 状态上报成功")
                return True
            else:
                self.logger.error(f"✗ 状态上报失败 - 状态码: {resp.status_code}, 响应: {resp.text}")
                return False
        except Exception as e:
            self.logger.error(f"执行异常: {e}")
            self.last_error = str(e)
            return False