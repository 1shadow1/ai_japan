#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块
统一读取和管理客户端配置
"""

import os
import json
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ConfigManager:
    """配置管理器，单例模式"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Optional[Dict[str, Any]] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._config is None:
            self._load_config()
    
    def _load_config(self):
        """加载配置文件"""
        # 获取配置文件路径
        config_path = os.getenv(
            'AIJ_CONFIG_PATH',
            os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'config', 'client_config.json')
        )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info(f"配置文件加载成功: {config_path}")
        except FileNotFoundError:
            logger.error(f"配置文件不存在: {config_path}")
            self._config = self._get_default_config()
        except json.JSONDecodeError as e:
            logger.error(f"配置文件格式错误: {e}")
            self._config = self._get_default_config()
        except Exception as e:
            logger.error(f"加载配置文件失败: {e}")
            self._config = self._get_default_config()
    
    def _get_default_config(self) -> Dict[str, Any]:
        """获取默认配置"""
        return {
            "version": "1.0.0",
            "site": {
                "pool_id": "4",
                "batch_id": 2,
                "location": "日本陆上养殖实验室",
                "timezone": "Asia/Tokyo"
            },
            "sensors": {
                "sample_interval_seconds": 600,
                "logging_interval_seconds": 600,
                "devices": []
            },
            "cameras": {
                "devices": [],
                "record_duration_seconds": 60,
                "target_fps": 30,
                "extract_interval_seconds": 1
            },
            "feeders": {
                "device_id": "AI",
                "device_name": "AI",
                "pool_id": "4",
                "batch_id": 2,
                "schedule": [],
                "status_check_interval_seconds": 600,
                "schedule_check_interval_seconds": 60
            },
            "api": {
                "base_url": "http://8.216.33.92:5002",
                "endpoints": {
                    "sensor_data": "/api/data/sensors",
                    "feeder_data": "/api/data/feeders",
                    "operation_data": "/api/data/operations",
                    "camera_data": "/api/data/cameras",
                    "camera_status": "/api/camera_device_status"
                },
                "timeout": 15,
                "retry_attempts": 3,
                "retry_delay_seconds": 2
            },
            "upload": {
                "stream_interval_seconds": 600,
                "batch_upload_interval_seconds": 600,
                "last_interval_days": 61
            },
            "tasks": {
                "sensor_health_check_interval_seconds": 60,
                "sensor_stream_start_delay_seconds": 1,
                "camera_service_start_delay_seconds": 1
            },
            "paths": {
                "output_dir": "./output",
                "sensor_data_dir": "./output/sensor",
                "camera_video_dir": "./logs/videos",
                "camera_extract_dir": "./output",
                "log_dir": "./logs",
                "upload_data_dir": "./data"
            },
            "simulation": {
                "sensor_simulate": False,
                "upload_dry_run": False,
                "camera_upload_dry_run": False
            }
        }
    
    def get(self, key_path: str, default: Any = None) -> Any:
        """
        获取配置值（支持点号分隔的路径）
        
        Args:
            key_path: 配置路径，如 'site.pool_id' 或 'api.base_url'
            default: 默认值
            
        Returns:
            配置值
        """
        if self._config is None:
            return default
        
        keys = key_path.split('.')
        value = self._config
        
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default
        
        return value
    
    def get_site_config(self) -> Dict[str, Any]:
        """获取站点配置"""
        return self.get('site', {})
    
    def get_pool_id(self) -> str:
        """获取池号"""
        return str(self.get('site.pool_id', '4'))
    
    def get_batch_id(self) -> int:
        """获取批次ID"""
        return int(self.get('site.batch_id', 2))
    
    def get_timezone(self) -> str:
        """获取时区"""
        return self.get('site.timezone', 'Asia/Tokyo')
    
    def get_sensor_config(self) -> Dict[str, Any]:
        """获取传感器配置"""
        return self.get('sensors', {})
    
    def get_sensor_devices(self) -> List[Dict[str, Any]]:
        """获取传感器设备列表"""
        return self.get('sensors.devices', [])
    
    def get_camera_config(self) -> Dict[str, Any]:
        """获取摄像头配置"""
        return self.get('cameras', {})
    
    def get_camera_devices(self) -> List[Dict[str, Any]]:
        """获取摄像头设备列表"""
        return self.get('cameras.devices', [])
    
    def get_feeder_config(self) -> Dict[str, Any]:
        """获取喂食机配置"""
        return self.get('feeders', {})

    def get_feeder_cloud_config(self) -> Dict[str, Any]:
        """获取喂食机云端接口配置"""
        feeders = self.get('feeders', {})
        if isinstance(feeders, dict):
            return feeders.get('cloud', {}) or {}
        return {}

    def get_feeder_target_dev_id(self) -> Optional[str]:
        """获取喂食机目标设备ID（如果配置了）"""
        feeders = self.get('feeders', {})
        if isinstance(feeders, dict):
            dev_id = feeders.get('target_dev_id')
            return str(dev_id) if dev_id is not None else None
        return None
    
    def get_api_config(self) -> Dict[str, Any]:
        """获取API配置"""
        return self.get('api', {})
    
    def get_api_base_url(self) -> str:
        """获取API基础URL"""
        return self.get('api.base_url', 'http://8.216.33.92:5002')
    
    def get_api_endpoint(self, endpoint_name: str) -> str:
        """获取API端点URL"""
        base_url = self.get_api_base_url()
        endpoint_path = self.get(f'api.endpoints.{endpoint_name}', '')
        # 移除重复的斜杠
        if endpoint_path.startswith('/'):
            return f"{base_url.rstrip('/')}{endpoint_path}"
        return f"{base_url.rstrip('/')}/{endpoint_path}"
    
    def get_api_url(self, endpoint_key: str) -> str:
        """获取完整的API URL（兼容方法）"""
        return self.get_api_endpoint(endpoint_key)
    
    def get_upload_config(self) -> Dict[str, Any]:
        """获取上传配置"""
        return self.get('upload', {})
    
    def get_tasks_config(self) -> Dict[str, Any]:
        """获取任务配置"""
        return self.get('tasks', {})
    
    def get_paths_config(self) -> Dict[str, Any]:
        """获取路径配置"""
        return self.get('paths', {})
    
    def get_path(self, path_key: str, default: str = "") -> str:
        """获取路径配置"""
        return self.get(f"paths.{path_key}", default)
    
    def get_simulation_config(self) -> Dict[str, Any]:
        """获取模拟配置"""
        return self.get('simulation', {})
    
    def is_sensor_simulate(self) -> bool:
        """是否启用传感器模拟模式"""
        env_val = os.getenv('AIJ_SENSOR_SIMULATE', '').lower()
        if env_val in ('1', 'true', 'yes'):
            return True
        return self.get('simulation.sensor_simulate', False)
    
    def is_upload_dry_run(self) -> bool:
        """是否启用上传干运行模式"""
        env_val = os.getenv('AIJ_UPLOAD_DRY_RUN', '').lower()
        if env_val in ('1', 'true', 'yes'):
            return True
        return self.get('simulation.upload_dry_run', False)
    
    def is_camera_upload_dry_run(self) -> bool:
        """是否启用摄像头上传干运行模式"""
        env_val = os.getenv('AIJ_CAMERA_UPLOAD_DRY_RUN', '').lower()
        if env_val in ('1', 'true', 'yes'):
            return True
        return self.get('simulation.camera_upload_dry_run', False)
    
    def is_simulation_mode(self, mode: str = "sensor") -> bool:
        """检查是否为模拟模式"""
        if mode == "sensor":
            return self.is_sensor_simulate()
        elif mode == "upload":
            return self.is_upload_dry_run()
        elif mode == "camera_upload":
            return self.is_camera_upload_dry_run()
        return False
    
    def reload(self):
        """重新加载配置"""
        self._load_config()
    
    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置（用于调试）"""
        return self._config.copy() if self._config else {}


# 全局配置管理器实例
config_manager = ConfigManager()


# 兼容函数（用于向后兼容）
def get_config() -> ConfigManager:
    """获取全局配置管理器实例"""
    return config_manager
