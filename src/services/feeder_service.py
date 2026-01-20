"""
FeederService
封装养殖池 IoT 自动喂食机云端接口：登录、设备查询、状态查询、下发喂食指令。

接口说明（通过统一网关 BASE_URL 调用）：
- msgType=1000 登录，返回 authkey
- msgType=1401 获取设备列表
- msgType=2000 查询设备状态
- msgType=2001 下发喂食指令

环境变量支持：
- AIJ_FEEDER_USER: 用户ID（区号+手机号）
- AIJ_FEEDER_PASS: 密码/密钥
- AIJ_FEEDER_BASE_URL: 覆盖默认 BASE_URL
- AIJ_FEEDER_VERIFY: 证书校验（默认启用，设置为 "0"/"false"/"no" 关闭）
- AIJ_FEEDER_TIMEOUT: 请求超时秒数（默认15）
- AIJ_FEEDER_DEV_NAME: 目标设备名称（默认 "AI"）
"""

from __future__ import annotations

import os
import logging
import time
import warnings
from typing import Any, Dict, List, Optional

try:
    import requests
except Exception:
    requests = None

from src.config.config_manager import config_manager
from src.services.api_client import api_client  # 允许在无 requests 依赖时加载模块


class FeederService:
    """云端喂食机接口封装"""

    DEFAULT_BASE_URL = "https://ffish.huaeran.cn:8081/commonRequest"

    def __init__(
        self,
        user_id: Optional[str] = None,
        password: Optional[str] = None,
        base_url: Optional[str] = None,
        verify: Optional[bool] = None,
        timeout: Optional[int] = None,
    ):
        self.logger = logging.getLogger("FeederService")
        # 从配置文件读取云端接口配置（不再从环境变量读取）
        cloud_cfg = config_manager.get_feeder_cloud_config()
        self.user_id = user_id or str(cloud_cfg.get("user_id", "")).strip()
        self.password = password or str(cloud_cfg.get("password", "")).strip()
        self.base_url = (base_url or str(cloud_cfg.get("base_url", self.DEFAULT_BASE_URL)).strip() or self.DEFAULT_BASE_URL)
        self.verify = True if (verify if verify is not None else cloud_cfg.get("verify", True)) else False
        try:
            self.timeout = int(timeout or int(cloud_cfg.get("timeout_seconds", 15)))
        except Exception:
            self.timeout = 15

        self.authkey: Optional[str] = None
        self._session: Optional[requests.Session] = requests.Session() if requests else None

        # 当明确禁用证书校验时，关闭 urllib3 的 InsecureRequestWarning 告警
        if self.verify is False:
            try:
                import urllib3
                from urllib3.exceptions import InsecureRequestWarning
                urllib3.disable_warnings(InsecureRequestWarning)
                warnings.simplefilter('ignore', InsecureRequestWarning)
            except Exception:
                pass

        if not self.user_id or not self.password:
            self.logger.warning("FeederService: 配置文件 feeders.cloud 未提供用户凭证，后续调用可能失败")

    # ------------------------ 基础请求方法 ------------------------
    def _post(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if not requests or not self._session:
            return {"success": False, "error": "requests 未安装"}
        try:
            resp = self._session.post(self.base_url, json=payload, verify=self.verify, timeout=self.timeout)
            data = resp.json() if resp.headers.get("Content-Type", "").startswith("application/json") else {"status_code": resp.status_code, "text": resp.text}
            return {"success": True, "status_code": resp.status_code, "data": data}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ------------------------ 业务接口封装 ------------------------
    def login(self) -> bool:
        payload = {
            "msgType": 1000,
            "userID": self.user_id,
            "password": self.password,
        }
        result = self._post(payload)
        if not result.get("success"):
            self.logger.error(f"登录请求失败: {result.get('error')}")
            return False
        data = result.get("data", {})
        if isinstance(data, dict) and data.get("status") == 1:
            try:
                self.authkey = data["data"][0]["authkey"]
            except Exception:
                self.authkey = None
            self.logger.info("[登录成功] 已获取 authkey")
            return True
        else:
            self.logger.error(f"[登录失败] {data}")
            return False

    def get_devices(self, page_index: int = 0, page_size: int = 50) -> List[Dict[str, Any]]:
        if not self.authkey:
            if not self.login():
                return []
        payload = {
            "msgType": 1401,
            "authkey": self.authkey,
            "userID": self.user_id,
            "pageIndex": page_index,
            "pageSize": page_size,
        }
        result = self._post(payload)
        if not result.get("success"):
            self.logger.error(f"获取设备列表失败: {result.get('error')}")
            return []
        data = result.get("data", {})
        if isinstance(data, dict) and data.get("status") == 1:
            devices = data.get("data", [])
            return devices if isinstance(devices, list) else []
        self.logger.warning(f"[获取设备失败] {data}")
        return []

    def find_device_by_name(self, dev_name: str = "AI") -> Optional[Dict[str, Any]]:
        devices = self.get_devices()
        for dev in devices:
            if str(dev.get("devName", "")).strip() == dev_name:
                return dev
        return None

    def get_device_status(self, dev_id: str) -> Optional[Dict[str, Any]]:
        if not self.authkey:
            if not self.login():
                return None
        payload = {
            "msgType": 2000,
            "authkey": self.authkey,
            "userID": self.user_id,
            "devID": dev_id,
        }
        result = self._post(payload)
        if not result.get("success"):
            self.logger.error(f"查询设备状态失败: {result.get('error')}")
            return None
        data = result.get("data", {})
        if isinstance(data, dict) and data.get("status") == 1:
            try:
                return data.get("data", [None])[0]
            except Exception:
                return None
        # 首次失败，若可能为鉴权问题（例如状态码=6），尝试重新登录并重试一次
        self.logger.warning(f"[获取状态失败] {data}")
        if isinstance(data, dict) and data.get("status") in (2, 6):
            self.logger.info("尝试重新登录后重试设备状态查询...")
            if self.login():
                result = self._post(payload)
                data = result.get("data", {}) if result.get("success") else {}
                if isinstance(data, dict) and data.get("status") == 1:
                    try:
                        return data.get("data", [None])[0]
                    except Exception:
                        return None
                self.logger.warning(f"[重试状态查询失败] {data}")
        return None

    def feed(self, dev_id: str, count: int = 1) -> bool:
        """执行喂食操作并记录数据"""
        if not self.authkey:
            if not self.login():
                return False
        payload = {
            "msgType": 2001,
            "authkey": self.authkey,
            "userID": self.user_id,
            "devID": dev_id,
            "feedCount": count,
        }
        result = self._post(payload)
        if not result.get("success"):
            self.logger.error(f"喂食请求失败: {result.get('error')}")
            return False
        data = result.get("data", {})
        if isinstance(data, dict) and data.get("status") == 1:
            self.logger.info(f"[喂食成功] 已发送 {count} 份喂食指令")
            
            # 上传喂食记录到服务器
            try:
                self._upload_feed_record(dev_id, count)
            except Exception as e:
                self.logger.warning(f"上传feed记录失败: {e}")
            
            return True
        # 首次失败，若可能为鉴权问题（例如状态码=6），尝试重新登录并重试一次
        self.logger.error(f"[喂食失败] {data}")
        if isinstance(data, dict) and data.get("status") in (2, 6):
            self.logger.info("尝试重新登录后重试喂食...")
            if self.login():
                result = self._post(payload)
                data = result.get("data", {}) if result.get("success") else {}
                if isinstance(data, dict) and data.get("status") == 1:
                    self.logger.info(f"[喂食成功-重试] 已发送 {count} 份喂食指令")
                    try:
                        self._upload_feed_record(dev_id, count)
                    except Exception as e:
                        self.logger.warning(f"上传feed记录失败: {e}")
                    return True
                self.logger.error(f"[喂食重试失败] {data}")
        return False
    
    def _upload_feed_record(self, dev_id: str, feed_count: int):
        """上传feed记录到服务器"""
        # 从配置获取喂食机信息
        feeder_config = config_manager.get_feeder_config()
        feeder_id = feeder_config.get('device_id', dev_id)
        
        # 估算投喂量（根据配置，每份约17g）
        feed_amount_g = feed_count * 17.0  # 可以根据实际情况调整
        
        # 估算运行时间（假设每份需要约30秒）
        run_time_s = feed_count * 30
        
        timestamp_ms = int(time.time() * 1000)
        
        api_client.send_feeder_data(
            feeder_id=feeder_id,
            feed_amount_g=feed_amount_g,
            run_time_s=run_time_s,
            status="ok",
            notes=f"定时投喂 {feed_count} 份",
            timestamp=timestamp_ms
        )

    # ------------------------ 辅助方法 ------------------------
    def get_ai_device_id(self, dev_name_env_default: str = "AI") -> Optional[str]:
        # 仅从配置读取：优先使用 target_dev_id，其次使用 device_name 进行查找
        cfg_dev_id = config_manager.get_feeder_target_dev_id()
        if cfg_dev_id:
            self.logger.info(f"使用配置的 target_dev_id={cfg_dev_id}")
            return str(cfg_dev_id).strip()
        feeder_cfg = config_manager.get_feeder_config() or {}
        target_name = str(feeder_cfg.get("device_name", dev_name_env_default)).strip() or dev_name_env_default
        self.logger.info(f"按设备名查找喂食机：{target_name}")
        dev = self.find_device_by_name(target_name)
        if dev and isinstance(dev, dict):
            dev_id = dev.get("devID")
            self.logger.info(f"已找到设备 {target_name}，devID={dev_id}")
            return dev_id
        self.logger.error(f"设备未找到：{target_name}")
        return None

    @staticmethod
    def build_status_payload(dev_id: str, dev_name: str, status: Dict[str, Any]) -> Dict[str, Any]:
        from datetime import datetime
        return {
            "device_id": dev_id,
            "device_name": dev_name,
            "status": status,
            "timestamp": datetime.now().isoformat(),
        }