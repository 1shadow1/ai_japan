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
import time
from typing import Optional, Dict, Any

from src.scheduler.task_scheduler import BaseTask
from src.services.feeder_service import FeederService
from src.config.config_manager import config_manager
from src.services.api_client import api_client


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
            dev_id = self.service.get_ai_device_id(self.target_dev_name)
            if not dev_id:
                self.logger.error(f"未找到设备 devName='{self.target_dev_name}'")
                return False

            status = self.service.get_device_status(dev_id)
            if status is None:
                self.logger.error("获取设备状态失败")
                return False

            # 使用新的API客户端上传状态数据
            feeder_config = config_manager.get_feeder_config()
            feeder_id = feeder_config.get('device_id', dev_id)
            
            # 从状态中提取信息
            feed_amount_g = status.get('feedAmount', 0) if isinstance(status.get('feedAmount'), (int, float)) else None
            leftover_estimate_g = status.get('leftover', 0) if isinstance(status.get('leftover'), (int, float)) else None
            
            # 确定状态
            device_status = "ok"
            if isinstance(status.get('status'), str):
                device_status = status.get('status', 'ok')
            elif isinstance(status.get('online'), bool) and not status.get('online'):
                device_status = "error"
            
            timestamp_ms = int(time.time() * 1000)
            
            try:
                api_client.send_feeder_data(
                    feeder_id=feeder_id,
                    feed_amount_g=feed_amount_g,
                    leftover_estimate_g=leftover_estimate_g,
                    status=device_status,
                    notes=f"状态查询 - {self.target_dev_name}",
                    timestamp=timestamp_ms
                )
                self.logger.info("✓ 状态上报成功")
                return True
            except Exception as e:
                self.logger.error(f"✗ 状态上报失败: {e}")
                return False
                
        except Exception as e:
            self.logger.error(f"执行异常: {e}")
            self.last_error = str(e)
            return False