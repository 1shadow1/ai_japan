"""
FeedDeviceScheduleTask
按照配置文件中的时间列表（feeders.schedule[*].times）在每天的这些时间点触发一次喂食（feeders.schedule[*].feed_count）。

实现方式：使用间隔任务（例如每60秒执行一次），在 execute() 中判断当前时间是否命中指定时间点，
并通过去重机制（同一天同一时间点只执行一次）避免重复。

配置：
- feeders.device_name: 设备名（默认 "AI"）
- feeders.schedule[*].times: 时间列表
- feeders.schedule[*].feed_count: 每次喂食的份数
- feeders.schedule_check_interval_seconds: 检查间隔（默认 60s）
- feeders.force_feed_once: 设置为 true 时，忽略时间列表，立即触发一次（当天去重）
"""

from __future__ import annotations

import os
import logging
from datetime import datetime
from typing import Optional, Dict, Set, List

from src.scheduler.task_scheduler import BaseTask
from src.services.feeder_service import FeederService
from src.config.config_manager import config_manager


class FeedDeviceScheduleTask(BaseTask):
    def __init__(self, service: Optional[FeederService] = None):
        super().__init__(
            task_id="feed_device_schedule",
            name="喂食机定时投喂",
            description="按时间列表触发喂食（每天固定时间点）",
        )
        self.logger = logging.getLogger("FeedDeviceScheduleTask")
        self.service = service or FeederService()
        feeder_cfg = config_manager.get_feeder_config() or {}
        self.target_dev_name = str(feeder_cfg.get("device_name", "AI")).strip() or "AI"
        # 默认从配置 schedule 的上下文里，由 main.py 在注册时覆盖 feed_count/times；此处作为兜底：
        default_schedule = feeder_cfg.get("schedule", [])
        default_times = default_schedule[0].get("times", ["04:00","10:00","16:00","22:00"]) if default_schedule else ["04:00","10:00","16:00","22:00"]
        default_count = default_schedule[0].get("feed_count", 1) if default_schedule else 1
        self.feed_count = default_count
        self.times = default_times
        # 记录当天已触发的时间点
        self._triggered: Set[str] = set()
        # 一次性强制触发消费标志，避免重复触发
        self._force_consumed: bool = False
        self.logger.info(f"定时投喂任务初始化（配置驱动）：target_dev_name={self.target_dev_name}, feed_count={self.feed_count}, times={self.times}")

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

    def _force_trigger_key(self) -> Optional[str]:
        # 从配置读取一次性强制触发标志（例如 feeders.force_feed_once=true）
        force_once = config_manager.get('feeders.force_feed_once', False)
        if bool(force_once) and not self._force_consumed:
            now = datetime.now()
            key = f"{now.strftime('%Y-%m-%d')}|{now.strftime('%H:%M')}"
            # 标记已消费，避免每分钟重复触发
            self._force_consumed = True
            return key
        return None

    def _should_trigger_now(self) -> Optional[str]:
        now = datetime.now()
        now_time = now.strftime('%H:%M')
        key = f"{now.strftime('%Y-%m-%d')}|{now_time}"
        # 调试日志：当前时间、列表与去重情况
        self.logger.debug(f"时间判断：now={now.isoformat()}, now_time={now_time}, times={self.times}, already_triggered={key in self._triggered}")
        # 若当前时间点在列表内，且尚未在今天触发
        if now_time in self.times and key not in self._triggered:
            return key
        # 每天重置：移除不是今天的记录
        today_prefix = now.strftime('%Y-%m-%d') + "|"
        old_keys = [k for k in self._triggered if not k.startswith(today_prefix)]
        for k in old_keys:
            self.logger.debug(f"清理历史触发记录：{k}")
            self._triggered.discard(k)
        return None

    def execute(self) -> bool:
        try:
            # 先按时间列表判断
            key = self._should_trigger_now()
            # 若未命中时间列表，判断是否强制触发
            if not key:
                forced_key = self._force_trigger_key()
                if forced_key and forced_key not in self._triggered:
                    self.logger.info("检测到配置 feeders.force_feed_once=开启，执行一次立即投喂（当天去重）")
                    key = forced_key
                else:
                    # 未触发，打印调试信息后返回
                    self.logger.debug("未命中投喂时间点，且未启用强制触发或已触发过")
                    return True

            dev_id = self.service.get_ai_device_id(self.target_dev_name)
            self.logger.debug(f"设备查找：target_dev_name={self.target_dev_name}, dev_id={dev_id}")
            if not dev_id:
                self.logger.error(f"未找到设备 devName='{self.target_dev_name}'")
                return False

            # 实际喂食操作
            self.logger.info(f"准备执行喂食：key={key}, feed_count={self.feed_count}")
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