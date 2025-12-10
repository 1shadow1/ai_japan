"""
HTTP请求发送任务
每小时向指定端口发送传感器数据的系统告警信息
"""

import sys
import os
import json
import requests
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional
import logging

# 导入调度器相关模块（已迁移到 src/scheduler）
from src.scheduler.task_scheduler import BaseTask, TaskStatus
# 注释掉sensor_data_service导入，避免pandas依赖问题
# from sensor_data_service import SensorDataService

class HttpRequestTask(BaseTask):
    """HTTP请求发送任务 - 每小时执行一次"""
    
    def __init__(self, 
                 target_url: str = "http://localhost:5002/api/messages/",
                 sensor_service = None):  # 移除类型注解避免导入问题
        super().__init__(
            task_id="hourly_http_request",
            name="每小时HTTP请求发送",
            description="每小时向指定端口发送传感器数据的系统告警信息"
        )
        
        self.target_url = target_url
        self.sensor_service = sensor_service
        self.request_timeout = 30  # 30秒超时
        self.max_retries = 3       # 最大重试次数
        
        # 设置日志
        self.logger = logging.getLogger('HttpRequestTask')
    
    def _get_current_sensor_data(self) -> Dict[str, Any]:
        """获取当前传感器数据"""
        if self.sensor_service:
            return self.sensor_service.get_current_data()
        else:
            # 如果没有传感器服务，返回模拟数据
            return {
                'dissolved_oxygen': 7.33947,
                'liquid_level': 983,
                'ph': 7.38,
                'ph_temperature': 27.0,
                'turbidity': 0.0,
                'turbidity_temperature': 26.7
            }
    
    def _format_sensor_content(self, sensor_data: Dict[str, Any]) -> str:
        """格式化传感器数据为内容字符串"""
        do_val = sensor_data.get('dissolved_oxygen', 'N/A')
        level_val = sensor_data.get('liquid_level', 'N/A')
        ph_val = sensor_data.get('ph', 'N/A')
        ph_temp = sensor_data.get('ph_temperature', 'N/A')
        turbidity_val = sensor_data.get('turbidity', 'N/A')
        turbidity_temp = sensor_data.get('turbidity_temperature', 'N/A')
        
-        return f" 溶解氧饱和度: {do_val}  液位: {level_val} mm  pH: {ph_val}  温度(pH): {ph_temp} °C  浊度: {turbidity_val} NTU  温度(浊度): {turbidity_temp} °C"
+        return f" 溶解氧饱和度: {do_val}  液位: {level_val} mm  pH: {ph_val}  温度(pH): {ph_temp} °C  浊度: {turbidity_val} NTU"
    
    def _determine_alert_level(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """根据传感器数据确定告警级别和类型"""
        do_val = sensor_data.get('dissolved_oxygen')
        ph_val = sensor_data.get('ph')
        turbidity_val = sensor_data.get('turbidity')
        
        # 默认告警信息
        alert_info = {
            "alert_type": "routine_monitoring",
            "priority": "normal",
            "severity": "low",
            "recommended_actions": ["定期监控", "数据记录"]
        }
        
        # 溶解氧告警判断
        if do_val is not None:
            if do_val < 5.0:
                alert_info.update({
                    "alert_type": "critical_oxygen_level",
                    "priority": "urgent",
                    "severity": "high",
                    "recommended_actions": [
                        "启动增氧设备",
                        "检查水质过滤系统",
                        "减少投饲量",
                        "监控鱼类行为"
                    ]
                })
            elif do_val < 6.0:
                alert_info.update({
                    "alert_type": "low_oxygen_level",
                    "priority": "high",
                    "severity": "medium",
                    "recommended_actions": [
                        "准备增氧设备",
                        "检查水质状况",
                        "调整投饲计划"
                    ]
                })
        
        # pH值告警判断
        if ph_val is not None:
            if ph_val < 6.5 or ph_val > 8.5:
                alert_info.update({
                    "alert_type": "ph_abnormal",
                    "priority": "high",
                    "severity": "medium",
                    "recommended_actions": [
                        "调节水质pH值",
                        "检查水源质量",
                        "暂停投饲",
                        "监控鱼类状态"
                    ]
                })
        
        # 浊度告警判断
        if turbidity_val is not None and turbidity_val > 10.0:
            alert_info.update({
                "alert_type": "high_turbidity",
                "priority": "medium",
                "severity": "medium",
                "recommended_actions": [
                    "清理过滤系统",
                    "检查水质来源",
                    "减少投饲量"
                ]
            })
        
        return alert_info
    
    def _build_request_payload(self, sensor_data: Dict[str, Any]) -> Dict[str, Any]:
        """构建HTTP请求的载荷数据"""
        
        # 格式化传感器数据内容
        content = self._format_sensor_content(sensor_data)
        
        # 确定告警级别
        alert_info = self._determine_alert_level(sensor_data)
        
        # 当前时间戳
        current_time = datetime.now(timezone.utc)
        expires_time = current_time.replace(hour=current_time.hour + 4)  # 4小时后过期
        
        # 构建请求载荷
        payload = {
            "message_type": "system_alert",
            "content": content,
            "priority": alert_info["priority"],
            "metadata": {
                "alert_type": alert_info["alert_type"],
                "pond_id": "pond_001",  # 可配置的池塘ID
                "current_values": {
                    "dissolved_oxygen": sensor_data.get('dissolved_oxygen'),
                    "liquid_level": sensor_data.get('liquid_level'),
                    "ph": sensor_data.get('ph'),
                    "ph_temperature": sensor_data.get('ph_temperature'),
                    "turbidity": sensor_data.get('turbidity'),
-                    "turbidity_temperature": sensor_data.get('turbidity_temperature')
                },
                "recommended_actions": alert_info["recommended_actions"],
                "severity": alert_info["severity"],
                "auto_response_enabled": True,
                "notification_sent": True,
                "timestamp": current_time.isoformat()
            },
            "expires_at": expires_time.isoformat()
        }
        
        return payload
    
    def _send_http_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """发送HTTP请求"""
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "AI-Japan-Sensor-System/1.0"
        }
        
        for attempt in range(self.max_retries):
            try:
                self.logger.info(f"发送HTTP请求到 {self.target_url} (尝试 {attempt + 1}/{self.max_retries})")
                
                response = requests.post(
                    self.target_url,
                    json=payload,
                    headers=headers,
                    timeout=self.request_timeout
                )
                
                # 记录响应信息
                self.logger.info(f"HTTP响应状态码: {response.status_code}")
                
                if response.status_code == 200 or response.status_code == 201:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "response_text": response.text,
                        "attempt": attempt + 1
                    }
                else:
                    self.logger.warning(f"HTTP请求失败，状态码: {response.status_code}, 响应: {response.text}")
                    
                    if attempt == self.max_retries - 1:  # 最后一次尝试
                        return {
                            "success": False,
                            "status_code": response.status_code,
                            "response_text": response.text,
                            "error": f"HTTP请求失败，状态码: {response.status_code}",
                            "attempt": attempt + 1
                        }
                    
                    # 等待后重试
                    time.sleep(2 ** attempt)  # 指数退避
                    
            except requests.exceptions.Timeout:
                self.logger.error(f"HTTP请求超时 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    return {
                        "success": False,
                        "error": "HTTP请求超时",
                        "timeout": self.request_timeout,
                        "attempt": attempt + 1
                    }
                time.sleep(2 ** attempt)
                
            except requests.exceptions.ConnectionError:
                self.logger.error(f"HTTP连接失败 (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    return {
                        "success": False,
                        "error": "HTTP连接失败",
                        "target_url": self.target_url,
                        "attempt": attempt + 1
                    }
                time.sleep(2 ** attempt)
                
            except Exception as e:
                self.logger.error(f"HTTP请求异常: {str(e)} (尝试 {attempt + 1}/{self.max_retries})")
                if attempt == self.max_retries - 1:
                    return {
                        "success": False,
                        "error": f"HTTP请求异常: {str(e)}",
                        "attempt": attempt + 1
                    }
                time.sleep(2 ** attempt)
        
        return {
            "success": False,
            "error": "所有重试尝试均失败",
            "max_retries": self.max_retries
        }
    
    def execute(self) -> bool:
        """执行HTTP请求发送任务"""
        try:
            start_time = datetime.now()
            
            # 获取传感器数据
            sensor_data = self._get_current_sensor_data()
            self.logger.info(f"获取传感器数据: {sensor_data}")
            
            # 构建请求载荷
            payload = self._build_request_payload(sensor_data)
            
            # 发送HTTP请求
            result = self._send_http_request(payload)
            
            end_time = datetime.now()
            execution_time = (end_time - start_time).total_seconds()
            
            if result["success"]:
                self.success_count += 1
                self.logger.info(f"HTTP请求任务执行成功，耗时: {execution_time:.2f}秒")
                return True
            else:
                self.failure_count += 1
                self.last_error = result.get('error', '未知错误')
                self.logger.error(f"HTTP请求任务执行失败: {result.get('error', '未知错误')}")
                return False
            
        except Exception as e:
            self.failure_count += 1
            self.last_error = str(e)
            self.logger.error(f"HTTP请求任务执行异常: {str(e)}")
            return False
        finally:
            self.run_count += 1
            self.last_run = datetime.now()
            self.updated_at = datetime.now()
    
    def set_target_url(self, url: str):
        """设置目标URL"""
        self.target_url = url
        self.logger.info(f"目标URL已更新为: {url}")
    
    def set_sensor_service(self, sensor_service):
        """设置传感器服务"""
        self.sensor_service = sensor_service
        self.logger.info("传感器服务已关联")
    
    def get_task_info(self) -> Dict[str, Any]:
        """获取任务信息"""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "description": self.description,
            "target_url": self.target_url,
            "timeout": self.request_timeout,
            "max_retries": self.max_retries,
            "has_sensor_service": self.sensor_service is not None
        }

def main():
    """测试HTTP请求任务"""
    print("=" * 60)
    print("HTTP请求任务测试")
    print("=" * 60)
    
    # 创建HTTP请求任务
    http_task = HttpRequestTask()
    
    # 执行任务
    result = http_task.execute()
    
    print("执行结果:")
    print(result)

if __name__ == "__main__":
    main()