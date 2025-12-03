"""
SensorDataStreamTask
一次启动、持续运行：按固定频率获取传感器数据并向服务端发送（标准接口格式）。

特性：
- 通过 ScheduleType.ONCE 启动一次，内部线程持续运行
- 使用统一配置管理
- 支持环境变量控制
- 使用服务端标准接口 /api/data/sensors
"""

import os
import time
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
import threading
import pytz
import hashlib

from src.scheduler.task_scheduler import BaseTask
from src.services.sensor_data_service import SensorDataService
from src.config.config_manager import config_manager
from src.services.api_client import api_client


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
            description="持续按固定频率采集并上传传感器数据（标准接口格式）",
        )

        self.logger = logging.getLogger("SensorDataStreamTask")
        self.config = config_manager
        self.service = service or SensorDataService()

        # 获取API配置
        api_config = self.config.get_api_config()
        if target_url is None:
            target_url = self.config.get_api_endpoint("sensor_data")
        self.target_url = self._normalize_url(target_url)

        if interval_seconds is None:
            self.interval_seconds = self.config.get("upload.stream_interval_seconds", 10)
        else:
            self.interval_seconds = interval_seconds

        self.dry_run = self.config.is_simulation_mode("upload")
        self.timeout = api_config.get("timeout_seconds", 15)

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

    def _generate_checksum(self, data: Dict) -> str:
        """生成数据校验和"""
        data_str = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.md5(data_str.encode('utf-8')).hexdigest()

    def _format_payload(self, sensor_data: Dict[str, Any], sensor_config: Dict) -> Dict[str, Any]:
        """按服务端标准接口格式构造负载（已废弃，改用 api_client）"""
        # 获取时间戳
        now = datetime.now()
        utc_tz = pytz.UTC
        japan_tz = pytz.timezone(self.config.get("site.timezone", "Asia/Tokyo"))
        utc_now = now.astimezone(utc_tz)
        local_now = now.astimezone(japan_tz)
        
        # 获取站点配置
        site_config = self.config.get_site_config()
        
        # 构建标准格式的负载
        payload = {
            "sensor_id": sensor_config.get('sensor_id'),
            "batch_id": site_config.get('batch_id'),
            "pool_id": site_config.get('pool_id'),
            "value": sensor_data.get(sensor_config.get('metric')),
            "metric": sensor_config.get('metric'),
            "unit": sensor_config.get('unit'),
            "timestamp": int(utc_now.timestamp() * 1000),  # Unix时间戳（毫秒）
            "type_name": sensor_config.get('name'),
            "description": f"{site_config.get('pool_id')}号池 - {sensor_config.get('metric')}"
        }
        
        return payload

    def _upload_sensor_data(self, sensor_data: Dict, sensor_configs: Dict) -> bool:
        """上传单个传感器的数据（使用 api_client）"""
        success_count = 0
        total_count = 0
        
        for sensor_type, config in sensor_configs.items():
            metric = config.get('metric')
            if metric not in sensor_data or sensor_data[metric] is None:
                continue
            
            total_count += 1
            sensor_id = config.get('sensor_id')
            value = sensor_data[metric]
            unit = config.get('unit', '')
            type_name = config.get('name', '')
            
            # 优化 description 生成
            pool_id = config.get('pool_id', self.config.get_pool_id())
            batch_id = config.get('batch_id', self.config.get_batch_id())
            description = f"{pool_id}号池 - {metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                # 使用 api_client 发送数据（自动处理重试、元数据补充等）
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=metric,
                    unit=unit,
                    type_name=type_name,
                    description=description,
                    dry_run_override=self.dry_run
                )
                self.logger.debug(f"✓ 传感器数据上传成功: sensor_id={sensor_id}, metric={metric}, value={value}")
                success_count += 1
            except Exception as e:
                self.logger.error(f"✗ 传感器数据上传失败: sensor_id={sensor_id}, metric={metric}, error={e}")
        
        if total_count > 0:
            self.logger.info(f"传感器数据上传完成: {success_count}/{total_count} 成功")
            return success_count == total_count
        return True

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

                # 获取当前数据
                sensor_data = self.service.get_current_data()
                sensor_configs = self.service.sensor_configs
                
                # 上传每个传感器的数据
                self._upload_sensor_data(sensor_data, sensor_configs)

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
