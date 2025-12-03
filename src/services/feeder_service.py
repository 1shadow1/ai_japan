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
        self.user_id = user_id or os.getenv("AIJ_FEEDER_USER", "").strip()
        self.password = password or os.getenv("AIJ_FEEDER_PASS", "").strip()
        self.base_url = (base_url or os.getenv("AIJ_FEEDER_BASE_URL", "").strip() or self.DEFAULT_BASE_URL)

        env_verify = os.getenv("AIJ_FEEDER_VERIFY", "1").lower().strip()
        self.verify = True if env_verify in ("1", "true", "yes", "on", "") else False if env_verify in ("0", "false", "no", "off") else (verify if verify is not None else True)
        try:
            self.timeout = int(timeout or int(os.getenv("AIJ_FEEDER_TIMEOUT", "15")))
        except Exception:
            self.timeout = 15

        self.authkey: Optional[str] = None
        self._session: Optional[requests.Session] = requests.Session() if requests else None

        if not self.user_id or not self.password:
            self.logger.warning("FeederService: 未提供用户凭证（AIJ_FEEDER_USER/AIJ_FEEDER_PASS），后续调用可能失败")

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
        self.logger.warning(f"[获取状态失败] {data}")
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
                self.logger.warning(f"上传喂食记录失败: {e}")
            
            return True
        self.logger.error(f"[喂食失败] {data}")
        return False
    
    def _upload_feed_record(self, dev_id: str, feed_count: int):
        """上传喂食记录到服务器"""
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
        target_name = os.getenv("AIJ_FEEDER_DEV_NAME", dev_name_env_default).strip() or dev_name_env_default
        dev = self.find_device_by_name(target_name)
        if dev and isinstance(dev, dict):
            return dev.get("devID")
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