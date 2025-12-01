"""
FeedDeviceScheduleTask
按照指定时间列表（默认 04:00、10:00、16:00、22:00）在每天的这些时间点触发一次喂食（1 份）。

实现方式：使用间隔任务（例如每60秒执行一次），在 execute() 中判断当前时间是否命中指定时间点，
并通过去重机制（同一天同一时间点只执行一次）避免重复。

环境变量：
- AIJ_FEED_TIMES: 时间列表，逗号分隔，例如 "04:00,10:00,16:00,22:00"
- AIJ_FEED_COUNT: 每次喂食的份数（默认 1）
- AIJ_FEEDER_DEV_NAME: 设备名（默认 "AI"）
"""

from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Set, List

from src.scheduler.task_scheduler import BaseTask
from src.services.feeder_service import FeederService


class FeedDeviceScheduleTask(BaseTask):
    def __init__(self, service: Optional[FeederService] = None):
        super().__init__(
            task_id="feed_device_schedule",
            name="喂食机定时投喂",
            description="按时间列表触发喂食（每天固定时间点）",
        )
        self.logger = logging.getLogger("FeedDeviceScheduleTask")
        self.service = service or FeederService()
        self.target_dev_name = os.getenv("AIJ_FEEDER_DEV_NAME", "AI").strip() or "AI"
        self.feed_count = self._get_int_env("AIJ_FEED_COUNT", 1)
        self.times: List[str] = self._parse_times(os.getenv("AIJ_FEED_TIMES", "04:00,10:00,16:00,22:00"))
        # 记录当天已触发的时间点，例如 {"2025-01-01|04:00", "2025-01-01|10:00"}
        self._triggered: Set[str] = set()

    @staticmethod
    def _get_int_env(key: str, default_val: int) -> int:
        try:
            val = int(os.getenv(key, str(default_val)))
            return val
        except Exception:
            return default_val

    @staticmethod
    def _parse_times(value: str) -> List[str]:
        times = []
        for t in (value or "").split(','):
            tt = t.strip()
            if not tt:
                continue
            # 规范化为 HH:MM
            try:
                parts = tt.split(':')
                hh = int(parts[0])
                mm = int(parts[1]) if len(parts) > 1 else 0
                times.append(f"{hh:02d}:{mm:02d}")
            except Exception:
                # 跳过非法时间字符串
                pass
        return times

    def _should_trigger_now(self) -> Optional[str]:
        now = datetime.now()
        key = f"{now.strftime('%Y-%m-%d')}|{now.strftime('%H:%M')}"
        # 若当前时间点在列表内，且尚未在今天触发
        if now.strftime('%H:%M') in self.times and key not in self._triggered:
            return key
        # 每天重置：移除不是今天的记录
        today_prefix = now.strftime('%Y-%m-%d') + "|"
        old_keys = [k for k in self._triggered if not k.startswith(today_prefix)]
        for k in old_keys:
            self._triggered.discard(k)
        return None

    def execute(self) -> bool:
        try:
            key = self._should_trigger_now()
            if not key:
                return True  # 未到指定时间点，正常返回 True

            dev_id = self.service.get_ai_device_id(self.target_dev_name)
            if not dev_id:
                self.logger.error(f"未找到设备 devName='{self.target_dev_name}'")
                return False

            # 实际喂食操作暂时注释
            ok = self.service.feed(dev_id, self.feed_count)   
            if ok:
                self.logger.info(f"✓ {key} 喂食成功（{self.feed_count} 份）")
                self._triggered.add(key)
                return True
            else:
                self.logger.error(f"✗ {key} 喂食失败")
                return False
        except Exception as e:
            self.logger.error(f"执行异常: {e}")
            self.last_error = str(e)
            return False