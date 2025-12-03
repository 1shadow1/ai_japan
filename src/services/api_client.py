#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API客户端模块
统一处理与服务端的HTTP请求
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = None, delay: float = None):
    """重试装饰器"""
    if max_attempts is None:
        max_attempts = config_manager.get('api.retry_attempts', 3)
    if delay is None:
        delay = config_manager.get('api.retry_delay_seconds', 2)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试均失败，最终错误: {e}")
            raise last_exception
        return wrapper
    return decorator


class APIClient:
    """API客户端类"""
    
    def __init__(self):
        self.base_url = config_manager.get_api_base_url()
        self.timeout = config_manager.get('api.timeout_seconds', 15)
        self.dry_run = config_manager.is_upload_dry_run()
        
        if requests is None:
            logger.warning("requests 库未安装，API调用将失败")
        else:
            self.session = requests.Session()
    
    def _post_json(self, endpoint: str, data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST JSON请求
        
        Args:
            endpoint: 端点路径（如 '/api/data/sensors'）
            data: 请求数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} - {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    def _post_multipart(self, endpoint: str, files: Dict[str, Any], data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST multipart请求（用于文件上传）
        
        Args:
            endpoint: 端点路径
            files: 文件字典
            data: 表单数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} (multipart) - files: {list(files.keys())}, data: {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    @retry_on_failure()
    def send_sensor_data(self, sensor_id: int, value: float, metric: str, unit: str, 
                        timestamp: Optional[int] = None, type_name: Optional[str] = None,
                        description: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送传感器数据
        
        Args:
            sensor_id: 传感器ID
            value: 数值
            metric: 指标名称
            unit: 单位
            timestamp: Unix时间戳（毫秒），可选
            type_name: 传感器类型名称，可选
            description: 描述，可选
            dry_run_override: 是否覆盖干运行设置，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('sensor_data')
        
        # 从配置获取默认值
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "sensor_id": sensor_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "value": value,
            "metric": metric,
            "unit": unit,
        }
        
        if timestamp:
            payload["timestamp"] = timestamp
        if type_name:
            payload["type_name"] = type_name
        if description:
            payload["description"] = description
        
        return self._post_json(endpoint, payload, dry_run_override)
    
    @retry_on_failure()
    def send_feeder_data(self, feeder_id: str, feed_amount_g: Optional[float] = None,
                        run_time_s: Optional[int] = None, status: str = "ok",
                        leftover_estimate_g: Optional[float] = None, notes: Optional[str] = None,
                        timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送喂食机数据
        
        Args:
            feeder_id: 喂食机ID
            feed_amount_g: 投喂量（克）
            run_time_s: 运行时长（秒）
            status: 状态（ok/warning/error）
            leftover_estimate_g: 剩余饵料估计（克）
            notes: 备注
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('feeder_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "feeder_id": feeder_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "status": status,
        }
        
        if feed_amount_g is not None:
            payload["feed_amount_g"] = feed_amount_g
        if run_time_s is not None:
            payload["run_time_s"] = run_time_s
        if leftover_estimate_g is not None:
            payload["leftover_estimate_g"] = leftover_estimate_g
        if notes:
            payload["notes"] = notes
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_operation_data(self, operator_id: str, action_type: str, remarks: Optional[str] = None,
                           attachment_uri: Optional[str] = None, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送操作日志数据
        
        Args:
            operator_id: 操作人ID
            action_type: 操作类型
            remarks: 备注
            attachment_uri: 附件URI
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('operation_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "operator_id": operator_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "action_type": action_type,
        }
        
        if remarks:
            payload["remarks"] = remarks
        if attachment_uri:
            payload["attachment_uri"] = attachment_uri
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_camera_image(self, camera_id: int, image_path: str, timestamp: Optional[int] = None,
                         width_px: Optional[int] = None, height_px: Optional[int] = None,
                         format: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送摄像头图像
        
        Args:
            camera_id: 摄像头ID
            image_path: 图像文件路径
            timestamp: Unix时间戳（毫秒），可选
            width_px: 图像宽度（像素），可选
            height_px: 图像高度（像素），可选
            format: 图像格式（jpg/png），可选
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 准备文件
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            data = {
                'camera_id': str(camera_id),
                'batch_id': str(batch_id),
                'pool_id': pool_id,
            }
            
            if timestamp:
                data['timestamp'] = str(timestamp)
            if width_px:
                data['width_px'] = str(width_px)
            if height_px:
                data['height_px'] = str(height_px)
            if format:
                data['format'] = format
            
            return self._post_multipart(endpoint, files, data, dry_run_override)
    
    def send_camera_status(self, camera_index: int, event: str, duration: Optional[int] = None,
                          fps: Optional[int] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        发送摄像头状态
        
        Args:
            camera_index: 摄像头索引
            event: 事件类型（start_recording/finish_recording）
            duration: 录制时长（秒），可选
            fps: 帧率，可选
            filename: 文件名，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_status')
        
        from datetime import datetime
        
        payload = {
            "camera_index": camera_index,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        
        if duration is not None:
            payload["duration"] = duration
        if fps is not None:
            payload["fps"] = fps
        if filename:
            payload["filename"] = filename
        
        return self._post_json(endpoint, payload)


# 全局API客户端实例
api_client = APIClient()



# -*- coding: utf-8 -*-
"""
API客户端模块
统一处理与服务端的HTTP请求
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = None, delay: float = None):
    """重试装饰器"""
    if max_attempts is None:
        max_attempts = config_manager.get('api.retry_attempts', 3)
    if delay is None:
        delay = config_manager.get('api.retry_delay_seconds', 2)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试均失败，最终错误: {e}")
            raise last_exception
        return wrapper
    return decorator


class APIClient:
    """API客户端类"""
    
    def __init__(self):
        self.base_url = config_manager.get_api_base_url()
        self.timeout = config_manager.get('api.timeout_seconds', 15)
        self.dry_run = config_manager.is_upload_dry_run()
        
        if requests is None:
            logger.warning("requests 库未安装，API调用将失败")
        else:
            self.session = requests.Session()
    
    def _post_json(self, endpoint: str, data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST JSON请求
        
        Args:
            endpoint: 端点路径（如 '/api/data/sensors'）
            data: 请求数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} - {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    def _post_multipart(self, endpoint: str, files: Dict[str, Any], data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST multipart请求（用于文件上传）
        
        Args:
            endpoint: 端点路径
            files: 文件字典
            data: 表单数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} (multipart) - files: {list(files.keys())}, data: {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    @retry_on_failure()
    def send_sensor_data(self, sensor_id: int, value: float, metric: str, unit: str, 
                        timestamp: Optional[int] = None, type_name: Optional[str] = None,
                        description: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送传感器数据
        
        Args:
            sensor_id: 传感器ID
            value: 数值
            metric: 指标名称
            unit: 单位
            timestamp: Unix时间戳（毫秒），可选
            type_name: 传感器类型名称，可选
            description: 描述，可选
            dry_run_override: 是否覆盖干运行设置，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('sensor_data')
        
        # 从配置获取默认值
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "sensor_id": sensor_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "value": value,
            "metric": metric,
            "unit": unit,
        }
        
        if timestamp:
            payload["timestamp"] = timestamp
        if type_name:
            payload["type_name"] = type_name
        if description:
            payload["description"] = description
        
        return self._post_json(endpoint, payload, dry_run_override)
    
    @retry_on_failure()
    def send_feeder_data(self, feeder_id: str, feed_amount_g: Optional[float] = None,
                        run_time_s: Optional[int] = None, status: str = "ok",
                        leftover_estimate_g: Optional[float] = None, notes: Optional[str] = None,
                        timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送喂食机数据
        
        Args:
            feeder_id: 喂食机ID
            feed_amount_g: 投喂量（克）
            run_time_s: 运行时长（秒）
            status: 状态（ok/warning/error）
            leftover_estimate_g: 剩余饵料估计（克）
            notes: 备注
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('feeder_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "feeder_id": feeder_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "status": status,
        }
        
        if feed_amount_g is not None:
            payload["feed_amount_g"] = feed_amount_g
        if run_time_s is not None:
            payload["run_time_s"] = run_time_s
        if leftover_estimate_g is not None:
            payload["leftover_estimate_g"] = leftover_estimate_g
        if notes:
            payload["notes"] = notes
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_operation_data(self, operator_id: str, action_type: str, remarks: Optional[str] = None,
                           attachment_uri: Optional[str] = None, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送操作日志数据
        
        Args:
            operator_id: 操作人ID
            action_type: 操作类型
            remarks: 备注
            attachment_uri: 附件URI
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('operation_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "operator_id": operator_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "action_type": action_type,
        }
        
        if remarks:
            payload["remarks"] = remarks
        if attachment_uri:
            payload["attachment_uri"] = attachment_uri
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_camera_image(self, camera_id: int, image_path: str, timestamp: Optional[int] = None,
                         width_px: Optional[int] = None, height_px: Optional[int] = None,
                         format: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送摄像头图像
        
        Args:
            camera_id: 摄像头ID
            image_path: 图像文件路径
            timestamp: Unix时间戳（毫秒），可选
            width_px: 图像宽度（像素），可选
            height_px: 图像高度（像素），可选
            format: 图像格式（jpg/png），可选
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 准备文件
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            data = {
                'camera_id': str(camera_id),
                'batch_id': str(batch_id),
                'pool_id': pool_id,
            }
            
            if timestamp:
                data['timestamp'] = str(timestamp)
            if width_px:
                data['width_px'] = str(width_px)
            if height_px:
                data['height_px'] = str(height_px)
            if format:
                data['format'] = format
            
            return self._post_multipart(endpoint, files, data, dry_run_override)
    
    def send_camera_status(self, camera_index: int, event: str, duration: Optional[int] = None,
                          fps: Optional[int] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        发送摄像头状态
        
        Args:
            camera_index: 摄像头索引
            event: 事件类型（start_recording/finish_recording）
            duration: 录制时长（秒），可选
            fps: 帧率，可选
            filename: 文件名，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_status')
        
        from datetime import datetime
        
        payload = {
            "camera_index": camera_index,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        
        if duration is not None:
            payload["duration"] = duration
        if fps is not None:
            payload["fps"] = fps
        if filename:
            payload["filename"] = filename
        
        return self._post_json(endpoint, payload)


# 全局API客户端实例
api_client = APIClient()


# -*- coding: utf-8 -*-
"""
API客户端模块
统一处理与服务端的HTTP请求
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = None, delay: float = None):
    """重试装饰器"""
    if max_attempts is None:
        max_attempts = config_manager.get('api.retry_attempts', 3)
    if delay is None:
        delay = config_manager.get('api.retry_delay_seconds', 2)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试均失败，最终错误: {e}")
            raise last_exception
        return wrapper
    return decorator


class APIClient:
    """API客户端类"""
    
    def __init__(self):
        self.base_url = config_manager.get_api_base_url()
        self.timeout = config_manager.get('api.timeout_seconds', 15)
        self.dry_run = config_manager.is_upload_dry_run()
        
        if requests is None:
            logger.warning("requests 库未安装，API调用将失败")
        else:
            self.session = requests.Session()
    
    def _post_json(self, endpoint: str, data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST JSON请求
        
        Args:
            endpoint: 端点路径（如 '/api/data/sensors'）
            data: 请求数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} - {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    def _post_multipart(self, endpoint: str, files: Dict[str, Any], data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST multipart请求（用于文件上传）
        
        Args:
            endpoint: 端点路径
            files: 文件字典
            data: 表单数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} (multipart) - files: {list(files.keys())}, data: {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    @retry_on_failure()
    def send_sensor_data(self, sensor_id: int, value: float, metric: str, unit: str, 
                        timestamp: Optional[int] = None, type_name: Optional[str] = None,
                        description: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送传感器数据
        
        Args:
            sensor_id: 传感器ID
            value: 数值
            metric: 指标名称
            unit: 单位
            timestamp: Unix时间戳（毫秒），可选
            type_name: 传感器类型名称，可选
            description: 描述，可选
            dry_run_override: 是否覆盖干运行设置，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('sensor_data')
        
        # 从配置获取默认值
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "sensor_id": sensor_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "value": value,
            "metric": metric,
            "unit": unit,
        }
        
        if timestamp:
            payload["timestamp"] = timestamp
        if type_name:
            payload["type_name"] = type_name
        if description:
            payload["description"] = description
        
        return self._post_json(endpoint, payload, dry_run_override)
    
    @retry_on_failure()
    def send_feeder_data(self, feeder_id: str, feed_amount_g: Optional[float] = None,
                        run_time_s: Optional[int] = None, status: str = "ok",
                        leftover_estimate_g: Optional[float] = None, notes: Optional[str] = None,
                        timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送喂食机数据
        
        Args:
            feeder_id: 喂食机ID
            feed_amount_g: 投喂量（克）
            run_time_s: 运行时长（秒）
            status: 状态（ok/warning/error）
            leftover_estimate_g: 剩余饵料估计（克）
            notes: 备注
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('feeder_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "feeder_id": feeder_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "status": status,
        }
        
        if feed_amount_g is not None:
            payload["feed_amount_g"] = feed_amount_g
        if run_time_s is not None:
            payload["run_time_s"] = run_time_s
        if leftover_estimate_g is not None:
            payload["leftover_estimate_g"] = leftover_estimate_g
        if notes:
            payload["notes"] = notes
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_operation_data(self, operator_id: str, action_type: str, remarks: Optional[str] = None,
                           attachment_uri: Optional[str] = None, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送操作日志数据
        
        Args:
            operator_id: 操作人ID
            action_type: 操作类型
            remarks: 备注
            attachment_uri: 附件URI
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('operation_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "operator_id": operator_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "action_type": action_type,
        }
        
        if remarks:
            payload["remarks"] = remarks
        if attachment_uri:
            payload["attachment_uri"] = attachment_uri
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_camera_image(self, camera_id: int, image_path: str, timestamp: Optional[int] = None,
                         width_px: Optional[int] = None, height_px: Optional[int] = None,
                         format: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送摄像头图像
        
        Args:
            camera_id: 摄像头ID
            image_path: 图像文件路径
            timestamp: Unix时间戳（毫秒），可选
            width_px: 图像宽度（像素），可选
            height_px: 图像高度（像素），可选
            format: 图像格式（jpg/png），可选
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 准备文件
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            data = {
                'camera_id': str(camera_id),
                'batch_id': str(batch_id),
                'pool_id': pool_id,
            }
            
            if timestamp:
                data['timestamp'] = str(timestamp)
            if width_px:
                data['width_px'] = str(width_px)
            if height_px:
                data['height_px'] = str(height_px)
            if format:
                data['format'] = format
            
            return self._post_multipart(endpoint, files, data, dry_run_override)
    
    def send_camera_status(self, camera_index: int, event: str, duration: Optional[int] = None,
                          fps: Optional[int] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        发送摄像头状态
        
        Args:
            camera_index: 摄像头索引
            event: 事件类型（start_recording/finish_recording）
            duration: 录制时长（秒），可选
            fps: 帧率，可选
            filename: 文件名，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_status')
        
        from datetime import datetime
        
        payload = {
            "camera_index": camera_index,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        
        if duration is not None:
            payload["duration"] = duration
        if fps is not None:
            payload["fps"] = fps
        if filename:
            payload["filename"] = filename
        
        return self._post_json(endpoint, payload)


# 全局API客户端实例
api_client = APIClient()



# -*- coding: utf-8 -*-
"""
API客户端模块
统一处理与服务端的HTTP请求
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = None, delay: float = None):
    """重试装饰器"""
    if max_attempts is None:
        max_attempts = config_manager.get('api.retry_attempts', 3)
    if delay is None:
        delay = config_manager.get('api.retry_delay_seconds', 2)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试均失败，最终错误: {e}")
            raise last_exception
        return wrapper
    return decorator


class APIClient:
    """API客户端类"""
    
    def __init__(self):
        self.base_url = config_manager.get_api_base_url()
        self.timeout = config_manager.get('api.timeout_seconds', 15)
        self.dry_run = config_manager.is_upload_dry_run()
        
        if requests is None:
            logger.warning("requests 库未安装，API调用将失败")
        else:
            self.session = requests.Session()
    
    def _post_json(self, endpoint: str, data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST JSON请求
        
        Args:
            endpoint: 端点路径（如 '/api/data/sensors'）
            data: 请求数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} - {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    def _post_multipart(self, endpoint: str, files: Dict[str, Any], data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST multipart请求（用于文件上传）
        
        Args:
            endpoint: 端点路径
            files: 文件字典
            data: 表单数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} (multipart) - files: {list(files.keys())}, data: {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    @retry_on_failure()
    def send_sensor_data(self, sensor_id: int, value: float, metric: str, unit: str, 
                        timestamp: Optional[int] = None, type_name: Optional[str] = None,
                        description: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送传感器数据
        
        Args:
            sensor_id: 传感器ID
            value: 数值
            metric: 指标名称
            unit: 单位
            timestamp: Unix时间戳（毫秒），可选
            type_name: 传感器类型名称，可选
            description: 描述，可选
            dry_run_override: 是否覆盖干运行设置，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('sensor_data')
        
        # 从配置获取默认值
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "sensor_id": sensor_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "value": value,
            "metric": metric,
            "unit": unit,
        }
        
        if timestamp:
            payload["timestamp"] = timestamp
        if type_name:
            payload["type_name"] = type_name
        if description:
            payload["description"] = description
        
        return self._post_json(endpoint, payload, dry_run_override)
    
    @retry_on_failure()
    def send_feeder_data(self, feeder_id: str, feed_amount_g: Optional[float] = None,
                        run_time_s: Optional[int] = None, status: str = "ok",
                        leftover_estimate_g: Optional[float] = None, notes: Optional[str] = None,
                        timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送喂食机数据
        
        Args:
            feeder_id: 喂食机ID
            feed_amount_g: 投喂量（克）
            run_time_s: 运行时长（秒）
            status: 状态（ok/warning/error）
            leftover_estimate_g: 剩余饵料估计（克）
            notes: 备注
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('feeder_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "feeder_id": feeder_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "status": status,
        }
        
        if feed_amount_g is not None:
            payload["feed_amount_g"] = feed_amount_g
        if run_time_s is not None:
            payload["run_time_s"] = run_time_s
        if leftover_estimate_g is not None:
            payload["leftover_estimate_g"] = leftover_estimate_g
        if notes:
            payload["notes"] = notes
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_operation_data(self, operator_id: str, action_type: str, remarks: Optional[str] = None,
                           attachment_uri: Optional[str] = None, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送操作日志数据
        
        Args:
            operator_id: 操作人ID
            action_type: 操作类型
            remarks: 备注
            attachment_uri: 附件URI
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('operation_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "operator_id": operator_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "action_type": action_type,
        }
        
        if remarks:
            payload["remarks"] = remarks
        if attachment_uri:
            payload["attachment_uri"] = attachment_uri
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_camera_image(self, camera_id: int, image_path: str, timestamp: Optional[int] = None,
                         width_px: Optional[int] = None, height_px: Optional[int] = None,
                         format: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送摄像头图像
        
        Args:
            camera_id: 摄像头ID
            image_path: 图像文件路径
            timestamp: Unix时间戳（毫秒），可选
            width_px: 图像宽度（像素），可选
            height_px: 图像高度（像素），可选
            format: 图像格式（jpg/png），可选
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 准备文件
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            data = {
                'camera_id': str(camera_id),
                'batch_id': str(batch_id),
                'pool_id': pool_id,
            }
            
            if timestamp:
                data['timestamp'] = str(timestamp)
            if width_px:
                data['width_px'] = str(width_px)
            if height_px:
                data['height_px'] = str(height_px)
            if format:
                data['format'] = format
            
            return self._post_multipart(endpoint, files, data, dry_run_override)
    
    def send_camera_status(self, camera_index: int, event: str, duration: Optional[int] = None,
                          fps: Optional[int] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        发送摄像头状态
        
        Args:
            camera_index: 摄像头索引
            event: 事件类型（start_recording/finish_recording）
            duration: 录制时长（秒），可选
            fps: 帧率，可选
            filename: 文件名，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_status')
        
        from datetime import datetime
        
        payload = {
            "camera_index": camera_index,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        
        if duration is not None:
            payload["duration"] = duration
        if fps is not None:
            payload["fps"] = fps
        if filename:
            payload["filename"] = filename
        
        return self._post_json(endpoint, payload)


# 全局API客户端实例
api_client = APIClient()


# -*- coding: utf-8 -*-
"""
API客户端模块
统一处理与服务端的HTTP请求
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = None, delay: float = None):
    """重试装饰器"""
    if max_attempts is None:
        max_attempts = config_manager.get('api.retry_attempts', 3)
    if delay is None:
        delay = config_manager.get('api.retry_delay_seconds', 2)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试均失败，最终错误: {e}")
            raise last_exception
        return wrapper
    return decorator


class APIClient:
    """API客户端类"""
    
    def __init__(self):
        self.base_url = config_manager.get_api_base_url()
        self.timeout = config_manager.get('api.timeout_seconds', 15)
        self.dry_run = config_manager.is_upload_dry_run()
        
        if requests is None:
            logger.warning("requests 库未安装，API调用将失败")
        else:
            self.session = requests.Session()
    
    def _post_json(self, endpoint: str, data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST JSON请求
        
        Args:
            endpoint: 端点路径（如 '/api/data/sensors'）
            data: 请求数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} - {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    def _post_multipart(self, endpoint: str, files: Dict[str, Any], data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST multipart请求（用于文件上传）
        
        Args:
            endpoint: 端点路径
            files: 文件字典
            data: 表单数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} (multipart) - files: {list(files.keys())}, data: {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    @retry_on_failure()
    def send_sensor_data(self, sensor_id: int, value: float, metric: str, unit: str, 
                        timestamp: Optional[int] = None, type_name: Optional[str] = None,
                        description: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送传感器数据
        
        Args:
            sensor_id: 传感器ID
            value: 数值
            metric: 指标名称
            unit: 单位
            timestamp: Unix时间戳（毫秒），可选
            type_name: 传感器类型名称，可选
            description: 描述，可选
            dry_run_override: 是否覆盖干运行设置，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('sensor_data')
        
        # 从配置获取默认值
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "sensor_id": sensor_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "value": value,
            "metric": metric,
            "unit": unit,
        }
        
        if timestamp:
            payload["timestamp"] = timestamp
        if type_name:
            payload["type_name"] = type_name
        if description:
            payload["description"] = description
        
        return self._post_json(endpoint, payload, dry_run_override)
    
    @retry_on_failure()
    def send_feeder_data(self, feeder_id: str, feed_amount_g: Optional[float] = None,
                        run_time_s: Optional[int] = None, status: str = "ok",
                        leftover_estimate_g: Optional[float] = None, notes: Optional[str] = None,
                        timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送喂食机数据
        
        Args:
            feeder_id: 喂食机ID
            feed_amount_g: 投喂量（克）
            run_time_s: 运行时长（秒）
            status: 状态（ok/warning/error）
            leftover_estimate_g: 剩余饵料估计（克）
            notes: 备注
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('feeder_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "feeder_id": feeder_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "status": status,
        }
        
        if feed_amount_g is not None:
            payload["feed_amount_g"] = feed_amount_g
        if run_time_s is not None:
            payload["run_time_s"] = run_time_s
        if leftover_estimate_g is not None:
            payload["leftover_estimate_g"] = leftover_estimate_g
        if notes:
            payload["notes"] = notes
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_operation_data(self, operator_id: str, action_type: str, remarks: Optional[str] = None,
                           attachment_uri: Optional[str] = None, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送操作日志数据
        
        Args:
            operator_id: 操作人ID
            action_type: 操作类型
            remarks: 备注
            attachment_uri: 附件URI
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('operation_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "operator_id": operator_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "action_type": action_type,
        }
        
        if remarks:
            payload["remarks"] = remarks
        if attachment_uri:
            payload["attachment_uri"] = attachment_uri
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_camera_image(self, camera_id: int, image_path: str, timestamp: Optional[int] = None,
                         width_px: Optional[int] = None, height_px: Optional[int] = None,
                         format: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送摄像头图像
        
        Args:
            camera_id: 摄像头ID
            image_path: 图像文件路径
            timestamp: Unix时间戳（毫秒），可选
            width_px: 图像宽度（像素），可选
            height_px: 图像高度（像素），可选
            format: 图像格式（jpg/png），可选
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 准备文件
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            data = {
                'camera_id': str(camera_id),
                'batch_id': str(batch_id),
                'pool_id': pool_id,
            }
            
            if timestamp:
                data['timestamp'] = str(timestamp)
            if width_px:
                data['width_px'] = str(width_px)
            if height_px:
                data['height_px'] = str(height_px)
            if format:
                data['format'] = format
            
            return self._post_multipart(endpoint, files, data, dry_run_override)
    
    def send_camera_status(self, camera_index: int, event: str, duration: Optional[int] = None,
                          fps: Optional[int] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        发送摄像头状态
        
        Args:
            camera_index: 摄像头索引
            event: 事件类型（start_recording/finish_recording）
            duration: 录制时长（秒），可选
            fps: 帧率，可选
            filename: 文件名，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_status')
        
        from datetime import datetime
        
        payload = {
            "camera_index": camera_index,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        
        if duration is not None:
            payload["duration"] = duration
        if fps is not None:
            payload["fps"] = fps
        if filename:
            payload["filename"] = filename
        
        return self._post_json(endpoint, payload)


# 全局API客户端实例
api_client = APIClient()



# -*- coding: utf-8 -*-
"""
API客户端模块
统一处理与服务端的HTTP请求
"""

import os
import time
import logging
from typing import Dict, Any, Optional
from functools import wraps

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager

logger = logging.getLogger(__name__)


def retry_on_failure(max_attempts: int = None, delay: float = None):
    """重试装饰器"""
    if max_attempts is None:
        max_attempts = config_manager.get('api.retry_attempts', 3)
    if delay is None:
        delay = config_manager.get('api.retry_delay_seconds', 2)
    
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        logger.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logger.error(f"所有重试均失败，最终错误: {e}")
            raise last_exception
        return wrapper
    return decorator


class APIClient:
    """API客户端类"""
    
    def __init__(self):
        self.base_url = config_manager.get_api_base_url()
        self.timeout = config_manager.get('api.timeout_seconds', 15)
        self.dry_run = config_manager.is_upload_dry_run()
        
        if requests is None:
            logger.warning("requests 库未安装，API调用将失败")
        else:
            self.session = requests.Session()
    
    def _post_json(self, endpoint: str, data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST JSON请求
        
        Args:
            endpoint: 端点路径（如 '/api/data/sensors'）
            data: 请求数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} - {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                json=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    def _post_multipart(self, endpoint: str, files: Dict[str, Any], data: Dict[str, Any], dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送POST multipart请求（用于文件上传）
        
        Args:
            endpoint: 端点路径
            files: 文件字典
            data: 表单数据
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据字典
        """
        dry_run = dry_run_override if dry_run_override is not None else self.dry_run
        
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        if dry_run:
            logger.info(f"[DRY-RUN] POST {url} (multipart) - files: {list(files.keys())}, data: {data}")
            return {
                "success": True,
                "dry_run": True,
                "data": {"id": 0, "simulated": True}
            }
        
        if requests is None or not hasattr(self, 'session'):
            raise RuntimeError("requests 库未安装，无法发送请求")
        
        try:
            response = self.session.post(
                url,
                files=files,
                data=data,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"API请求失败: {url} - {e}")
            raise
    
    @retry_on_failure()
    def send_sensor_data(self, sensor_id: int, value: float, metric: str, unit: str, 
                        timestamp: Optional[int] = None, type_name: Optional[str] = None,
                        description: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送传感器数据
        
        Args:
            sensor_id: 传感器ID
            value: 数值
            metric: 指标名称
            unit: 单位
            timestamp: Unix时间戳（毫秒），可选
            type_name: 传感器类型名称，可选
            description: 描述，可选
            dry_run_override: 是否覆盖干运行设置，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('sensor_data')
        
        # 从配置获取默认值
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "sensor_id": sensor_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "value": value,
            "metric": metric,
            "unit": unit,
        }
        
        if timestamp:
            payload["timestamp"] = timestamp
        if type_name:
            payload["type_name"] = type_name
        if description:
            payload["description"] = description
        
        return self._post_json(endpoint, payload, dry_run_override)
    
    @retry_on_failure()
    def send_feeder_data(self, feeder_id: str, feed_amount_g: Optional[float] = None,
                        run_time_s: Optional[int] = None, status: str = "ok",
                        leftover_estimate_g: Optional[float] = None, notes: Optional[str] = None,
                        timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送喂食机数据
        
        Args:
            feeder_id: 喂食机ID
            feed_amount_g: 投喂量（克）
            run_time_s: 运行时长（秒）
            status: 状态（ok/warning/error）
            leftover_estimate_g: 剩余饵料估计（克）
            notes: 备注
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('feeder_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "feeder_id": feeder_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "status": status,
        }
        
        if feed_amount_g is not None:
            payload["feed_amount_g"] = feed_amount_g
        if run_time_s is not None:
            payload["run_time_s"] = run_time_s
        if leftover_estimate_g is not None:
            payload["leftover_estimate_g"] = leftover_estimate_g
        if notes:
            payload["notes"] = notes
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_operation_data(self, operator_id: str, action_type: str, remarks: Optional[str] = None,
                           attachment_uri: Optional[str] = None, timestamp: Optional[int] = None) -> Dict[str, Any]:
        """
        发送操作日志数据
        
        Args:
            operator_id: 操作人ID
            action_type: 操作类型
            remarks: 备注
            attachment_uri: 附件URI
            timestamp: Unix时间戳（毫秒），可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('operation_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        payload = {
            "operator_id": operator_id,
            "batch_id": batch_id,
            "pool_id": pool_id,
            "action_type": action_type,
        }
        
        if remarks:
            payload["remarks"] = remarks
        if attachment_uri:
            payload["attachment_uri"] = attachment_uri
        if timestamp:
            payload["timestamp"] = timestamp
        
        return self._post_json(endpoint, payload)
    
    @retry_on_failure()
    def send_camera_image(self, camera_id: int, image_path: str, timestamp: Optional[int] = None,
                         width_px: Optional[int] = None, height_px: Optional[int] = None,
                         format: Optional[str] = None, dry_run_override: Optional[bool] = None) -> Dict[str, Any]:
        """
        发送摄像头图像
        
        Args:
            camera_id: 摄像头ID
            image_path: 图像文件路径
            timestamp: Unix时间戳（毫秒），可选
            width_px: 图像宽度（像素），可选
            height_px: 图像高度（像素），可选
            format: 图像格式（jpg/png），可选
            dry_run_override: 是否覆盖干运行设置
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_data')
        
        batch_id = config_manager.get_batch_id()
        pool_id = config_manager.get_pool_id()
        
        if not os.path.exists(image_path):
            raise FileNotFoundError(f"图像文件不存在: {image_path}")
        
        # 准备文件
        with open(image_path, 'rb') as f:
            files = {
                'file': (os.path.basename(image_path), f, 'image/jpeg')
            }
            
            data = {
                'camera_id': str(camera_id),
                'batch_id': str(batch_id),
                'pool_id': pool_id,
            }
            
            if timestamp:
                data['timestamp'] = str(timestamp)
            if width_px:
                data['width_px'] = str(width_px)
            if height_px:
                data['height_px'] = str(height_px)
            if format:
                data['format'] = format
            
            return self._post_multipart(endpoint, files, data, dry_run_override)
    
    def send_camera_status(self, camera_index: int, event: str, duration: Optional[int] = None,
                          fps: Optional[int] = None, filename: Optional[str] = None) -> Dict[str, Any]:
        """
        发送摄像头状态
        
        Args:
            camera_index: 摄像头索引
            event: 事件类型（start_recording/finish_recording）
            duration: 录制时长（秒），可选
            fps: 帧率，可选
            filename: 文件名，可选
            
        Returns:
            响应数据
        """
        endpoint = config_manager.get_api_endpoint('camera_status')
        
        from datetime import datetime
        
        payload = {
            "camera_index": camera_index,
            "event": event,
            "timestamp": datetime.now().isoformat(),
        }
        
        if duration is not None:
            payload["duration"] = duration
        if fps is not None:
            payload["fps"] = fps
        if filename:
            payload["filename"] = filename
        
        return self._post_json(endpoint, payload)


# 全局API客户端实例
api_client = APIClient()


