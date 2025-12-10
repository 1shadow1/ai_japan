#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
传感器数据采集服务（重构版）
- 使用配置管理模块
- 补充完整元数据
- 使用标准API接口
"""

import threading
import time
from datetime import datetime, timezone
from typing import Dict, Optional, List
import os
import struct
import logging
import random
import csv

from src.config.config_manager import config_manager
from src.services.api_client import api_client

logger = logging.getLogger(__name__)


class SensorDataServiceV2:
    """传感器数据采集服务类（重构版）"""
    
    def __init__(
        self,
        output_dir: Optional[str] = None,
        simulate: Optional[bool] = None,
        register_signals: bool = False,
    ):
        # 从配置获取参数
        paths_config = config_manager.get_paths_config()
        self.output_dir = output_dir or paths_config.get('sensor_data_dir', './output/sensor')
        self.running = False
        self.threads = []
        self.data_lock = threading.Lock()
        
        # 模拟模式
        if simulate is None:
            self.simulate = config_manager.is_sensor_simulate()
        else:
            self.simulate = simulate
        
        # 从配置获取采样和记录间隔
        sensor_config = config_manager.get_sensor_config()
        self.sample_interval_seconds = sensor_config.get('sample_interval_seconds', 600)
        self.logging_interval_seconds = sensor_config.get('logging_interval_seconds', 600)
        
        # 从配置获取传感器设备列表
        self.sensor_devices = config_manager.get_sensor_devices()
        
        # 共享数据存储（按sensor_id索引）
        self.sensor_data: Dict[int, Dict[str, Optional[float]]] = {}
        
        # 确保输出目录存在
        os.makedirs(self.output_dir, exist_ok=True)
        self.csv_file = os.path.join(self.output_dir, "data_collection.csv")
        self.file_exists = os.path.exists(self.csv_file)
        
        # 设置日志
        self._setup_logging()
        
        # 条件导入第三方库
        self.pd = None
        self.ModbusClient = None
        if not self.simulate:
            try:
                import pandas as pd
                self.pd = pd
            except ImportError:
                logger.warning("未检测到pandas，将使用csv模块写入文件")
            try:
                from pymodbus.client.serial import ModbusSerialClient as _ModbusClient
                self.ModbusClient = _ModbusClient
            except ImportError:
                logger.warning("未检测到pymodbus，自动切换到模拟模式")
                self.simulate = True
        
        # 注册信号处理
        if register_signals:
            import signal
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = config_manager.get_paths_config().get('log_dir', './logs')
        os.makedirs(log_dir, exist_ok=True)
        logger.setLevel(logging.INFO)
        file_handler = logging.FileHandler(os.path.join(log_dir, 'sensor_service_v2.log'), encoding='utf-8')
        stream_handler = logging.StreamHandler()
        fmt = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(fmt)
        stream_handler.setFormatter(fmt)
        # 避免重复添加处理器
        if not logger.handlers:
            logger.addHandler(file_handler)
            logger.addHandler(stream_handler)

    def _signal_handler(self, signum, frame):
        """信号处理：优雅停止服务"""
        logger.info(f"收到停止信号: {signum}, 正在停止服务...")
        self.stop()

    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running

    def start(self):
        """启动服务后台线程"""
        if self.running:
            return
        self.running = True
        worker = threading.Thread(target=self._run_sampling_loop, name="SensorSamplingV2", daemon=True)
        self.threads = [worker]
        worker.start()
        logger.info("SensorDataServiceV2 已启动")

    def stop(self):
        """停止服务并回收线程"""
        if not self.running:
            return
        self.running = False
        for t in self.threads:
            try:
                t.join(timeout=3)
            except Exception:
                pass
        self.threads = []
        logger.info("SensorDataServiceV2 已停止")

    def get_current_data(self) -> Dict[str, Optional[float]]:
        """返回最近一次采样的各指标值（按指标名）"""
        with self.data_lock:
            d = getattr(self, '_current_data', {})
            return dict(d)

    def _run_sampling_loop(self):
        """采样与上传主循环（支持模拟模式）"""
        with self.data_lock:
            self._current_data = {}
        sample_int = self.sample_interval_seconds or 600
        while self.running:
            loop_start_ms = int(time.time() * 1000)
            for device in self.sensor_devices:
                try:
                    value = self._simulate_value(device) if self.simulate else None
                    # TODO: 非模拟模式应通过 Modbus 或对应协议读取设备数据
                    if value is None:
                        value = self._simulate_value(device)
                    timestamp_ms = int(time.time() * 1000)
                    # 上传当前设备数据（内部完成指标/单位映射）
                    self._upload_sensor_data(device, value, timestamp_ms)

                    # 更新共享数据（健康检查使用）
                    metric = device.get('metric')
                    metric_key = 'temperature' if metric == 'ph_temperature' else metric
                    with self.data_lock:
                        self._current_data[metric_key] = value
                        # 兼容别名：同时维护 'do'
                        if metric_key == 'dissolved_oxygen':
                            self._current_data['do'] = value
                except Exception as e:
                    logger.error(f"设备采样/上传异常: {e}")
            # 控制采样间隔
            elapsed_ms = int(time.time() * 1000) - loop_start_ms
            sleep_s = max(1, sample_int - min(sample_int, elapsed_ms // 1000))
            time.sleep(sleep_s)

    def _upload_sensor_data(self, device_config: Dict[str, object], value: float, timestamp_ms: Optional[int] = None):
        """按规则上传单条传感器数据
        - ph_temperature 映射为 metric=temperature, unit=°C
        - ph 映射为 metric=ph, unit=pH
        - turbidity_temperature 不上传（跳过）
        - 其他指标按配置上传
        """
        sensor_id = device_config.get('sensor_id')
        metric = device_config.get('metric') or device_config.get('type')
        unit = device_config.get('unit', '')
        # 使用配置中的 name 作为 type_name；若缺失则回退到 type
        type_name = device_config.get('name') or device_config.get('type')

        if metric == 'ph_temperature':
            upload_metric = 'temperature'
            upload_unit = '°C'
        elif metric == 'ph':
            upload_metric = 'ph'
            upload_unit = 'pH'
        elif metric == 'turbidity_temperature':
            # 不上传浊度温度
            logger.debug("跳过上传 turbidity_temperature")
            return
        else:
            upload_metric = metric
            upload_unit = unit or ''

        ts = timestamp_ms or int(time.time() * 1000)
        try:
            api_client.send_sensor_data(
                sensor_id=sensor_id,
                value=value,
                metric=upload_metric,
                unit=upload_unit,
                timestamp=ts,
                type_name=type_name,
            )
            logger.info(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}, unit={upload_unit}, timestamp={ts}")
        except Exception as e:
            logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")

    def _simulate_value(self, device: Dict[str, object]) -> float:
        """基于设备类型生成模拟值"""
        t = device.get('type')
        m = device.get('metric')
        if t == 'dissolved_oxygen':
            return round(random.uniform(4.0, 10.0), 2)
        elif t == 'ph':
            if m == 'ph_temperature':
                return round(random.uniform(15.0, 30.0), 1)
            return round(random.uniform(6.5, 8.5), 2)
        elif t == 'turbidity':
            if m == 'turbidity_temperature':
                return round(random.uniform(15.0, 30.0), 1)
            return round(random.uniform(0.0, 100.0), 1)
        elif t == 'liquid_level':
            # 液位传感器：参考历史范围，模拟 900-1100 mm
            return round(random.uniform(900.0, 1100.0), 1)
        elif t == 'temperature':
            # 温度传感器：模拟 15-30°C
            return round(random.uniform(15.0, 30.0), 1)
        else:
            return round(random.uniform(0.0, 100.0), 2)


