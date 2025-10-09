"""
SensorDataTask
封装传感器数据采集服务的启动/停止与状态查询，供调度器管理。
"""

from typing import Dict, Any
from datetime import datetime
import logging

from src.scheduler.task_scheduler import BaseTask
from src.services.sensor_data_service import SensorDataService


class SensorDataTask(BaseTask):
    """传感器数据服务任务
    - 第一次执行时启动服务（后台线程）
    - 后续定期执行以进行健康检查
    - 可在需要时调用 stop() 停止服务
    """

    def __init__(self, service: SensorDataService | None = None):
        super().__init__(
            task_id="sensor_service",
            name="传感器数据采集服务",
            description="管理传感器服务的启动/健康检查/停止"
        )
        self.logger = logging.getLogger("SensorDataTask")
        self.service = service or SensorDataService()

    def execute(self) -> bool:
        """启动或健康检查
        - 未运行则启动服务
        - 已运行则进行健康检查并返回True
        """
        try:
            if not self.service.is_running():
                self.logger.info("传感器服务未运行，正在启动...")
                self.service.start()
                self.logger.info("传感器服务启动完成")
            else:
                # 简单健康检查：读取一次当前数据并记录
                data = self.service.get_current_data()
                self.logger.info(f"传感器服务健康检查，当前数据: {data}")
            return True
        except Exception as e:
            self.logger.error(f"SensorDataTask 执行异常: {e}")
            self.last_error = str(e)
            return False
        finally:
            self.run_count += 1
            self.last_run = datetime.now()
            self.updated_at = datetime.now()

    def stop_service(self):
        """停止服务"""
        try:
            if self.service.is_running():
                self.logger.info("正在停止传感器服务...")
                self.service.stop()
                self.logger.info("传感器服务已停止")
                return True
            return True
        except Exception as e:
            self.logger.error(f"停止传感器服务异常: {e}")
            self.last_error = str(e)
            return False

    def get_task_info(self) -> Dict[str, Any]:
        """扩展任务信息"""
        base = super().get_status_info()
        base.update({
            "service_running": self.service.is_running(),
        })
        return base