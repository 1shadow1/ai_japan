"""
SensorDataStreamTask
一次启动、持续运行：按固定频率获取传感器数据并向服务端发送（表结构格式）。

特性：
- 通过 ScheduleType.ONCE 启动一次，内部线程持续运行
- 支持环境变量控制：
  - AIJ_UPLOAD_DRY_RUN=1 进行干运行（不实际请求，仅日志）
  - AIJ_STREAM_API_URL 指定服务端接收URL（默认: http://8.216.33.92:5000/api/updata_sensor_data）
  - AIJ_STREAM_INTERVAL 指定推送间隔秒数（默认: 10）
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import threading

from src.scheduler.task_scheduler import BaseTask
from src.services.sensor_data_service import SensorDataService

try:
    import requests
except Exception:
    requests = None  # 允许在干运行模式或无依赖时加载


class SensorDataStreamTask(BaseTask):
    """持续推送传感器数据到服务端的任务（后台线程）。"""

    def __init__(
        self,
        service: Optional[SensorDataService] = None,
        target_url: Optional[str] = None,
        interval_seconds: Optional[int] = None,
    ):
        super().__init__(
            task_id="sensor_data_stream",
            name="传感器数据流式上传",
            description="持续按固定频率采集并上传传感器数据（表结构格式）",
        )

        self.logger = logging.getLogger("SensorDataStreamTask")
        self.service = service or SensorDataService()

        # 环境变量配置
        env_url = os.getenv("AIJ_STREAM_API_URL", "").strip()
        # 默认对齐到生产接口
        default_url = "http://8.216.33.92:5000/api/updata_sensor_data"
        self.target_url = target_url or env_url or default_url
        self.target_url = self._normalize_url(self.target_url)

        env_interval = os.getenv("AIJ_STREAM_INTERVAL", "").strip()
        try:
            self.interval_seconds = int(interval_seconds or (int(env_interval) if env_interval else 10))
        except Exception:
            self.interval_seconds = 10

        env_dry = os.getenv("AIJ_UPLOAD_DRY_RUN", "0").lower()
        self.dry_run = env_dry in ("1", "true", "yes")

        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    @staticmethod
    def _normalize_url(s: str) -> str:
        """规范化URL，避免出现重复斜杠，如 //api/..."""
        if not s:
            return s
        try:
            parts = s.split("://", 1)
            if len(parts) == 2:
                scheme, rest = parts
                # 压缩连续斜杠
                while "//" in rest:
                    rest = rest.replace("//", "/")
                return f"{scheme}://{rest}"
            else:
                while "//" in s:
                    s = s.replace("//", "/")
                return s
        except Exception:
            return s

    def _format_payload(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """按“数据表结构”构造负载，字段对齐 CSV 标题。"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        payload = {
            "时间": timestamp,
            "溶解氧饱和度": sensor_data.get("dissolved_oxygen"),
            "液位(mm)": sensor_data.get("liquid_level"),
            "PH": sensor_data.get("ph"),
            "PH温度(°C)": sensor_data.get("ph_temperature"),
            "浊度(NTU)": sensor_data.get("turbidity"),
            "浊度温度(°C)": sensor_data.get("turbidity_temperature"),
        }
        return payload

    def _stream_loop(self):
        """后台线程：循环采集并上传。"""
        self.logger.info(
            f"数据流任务开始运行，目标URL={self.target_url}，间隔={self.interval_seconds}s，dry_run={self.dry_run}"
        )
        while not self._stop_event.is_set():
            try:
                # 确保服务运行
                if not self.service.is_running():
                    self.logger.warning("传感器服务未运行，尝试启动...")
                    try:
                        self.service.start()
                        self.logger.info("传感器服务已启动")
                    except Exception as e:
                        self.logger.error(f"传感器服务启动失败: {e}")

                # 获取当前数据并格式化负载
                sensor_data = self.service.get_current_data()
                payload = self._format_payload(sensor_data)

                if self.dry_run:
                    self.logger.info(f"[DRY-RUN] 模拟发送: {json.dumps(payload, ensure_ascii=False)} -> {self.target_url}")
                else:
                    if requests is None:
                        raise RuntimeError("requests 未安装，无法进行真实上传。请安装 requests 或开启干运行模式。")
                    resp = requests.post(self.target_url, json=payload, timeout=15)
                    if resp.status_code == 200:
                        self.logger.info("✓ 数据上传成功")
                    else:
                        self.logger.error(f"✗ 上传失败 - 状态码: {resp.status_code}, 响应: {resp.text}")

            except Exception as e:
                self.logger.error(f"数据流上传异常: {e}")
            finally:
                time.sleep(self.interval_seconds)

        self.logger.info("数据流任务线程已停止")

    def execute(self) -> bool:
        """启动一次后台线程并返回。"""
        try:
            if self._thread and self._thread.is_alive():
                self.logger.info("数据流任务已在运行中")
                return True

            self._stop_event.clear()
            self._thread = threading.Thread(target=self._stream_loop, daemon=True, name="SensorDataStream")
            self._thread.start()
            self.logger.info("数据流任务线程已启动")
            return True
        except Exception as e:
            self.logger.error(f"SensorDataStreamTask 启动异常: {e}")
            self.last_error = str(e)
            return False
        finally:
            self.run_count += 1
            self.last_run = datetime.now()
            self.updated_at = datetime.now()

    def stop_stream(self):
        """停止后台线程。"""
        try:
            self._stop_event.set()
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=5)
            return True
        except Exception as e:
            self.logger.error(f"停止数据流任务异常: {e}")
            self.last_error = str(e)
            return False