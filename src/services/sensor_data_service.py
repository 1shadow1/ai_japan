"""
传感器数据采集服务
基于原sensor_data_collection.py改造，支持优雅启动/停止和错误恢复
"""

import threading
import time
from datetime import datetime
import os
import struct
import logging
from typing import Dict, Optional
import signal
import sys
import random
import csv

class SensorDataService:
    """传感器数据采集服务类"""
    
    def __init__(
        self,
        output_dir: str = "./output/sensor",
        simulate: Optional[bool] = None,
        register_signals: bool = False,
        sample_interval_seconds: Optional[int] = None,
        logging_interval_seconds: Optional[int] = None,
    ):
        self.output_dir = output_dir
        self.csv_file = os.path.join(output_dir, "data_collection.csv")
        self.running = False
        self.threads = []
        self.data_lock = threading.Lock()
        # 模拟模式：无硬件环境下生成模拟数据
        if simulate is None:
            env_val = os.getenv("AIJ_SENSOR_SIMULATE", "0").lower()
            self.simulate = env_val in ("1", "true", "yes")
        else:
            self.simulate = simulate
        
        # 采样/记录频率配置
        try:
            env_sample = os.getenv("AIJ_SENSOR_SAMPLE_INTERVAL", "").strip()
            self.sample_interval_seconds = int(sample_interval_seconds or (int(env_sample) if env_sample else 10))
        except Exception:
            self.sample_interval_seconds = 10

        try:
            env_log = os.getenv("AIJ_SENSOR_LOG_INTERVAL", "").strip()
            self.logging_interval_seconds = int(logging_interval_seconds or (int(env_log) if env_log else max(5, self.sample_interval_seconds)))
        except Exception:
            self.logging_interval_seconds = max(5, self.sample_interval_seconds)

        # 传感器配置
        self.sensor_configs = {
            'dissolved_oxygen': {
                'port': 'COM18',
                'baudrate': 4800,
                'address': 0x0002,
                'count': 2,
                'slave': 0x01,
                'process_func': self._process_dissolved_oxygen
            },
            'liquid_level': {
                'port': 'COM25', 
                'baudrate': 4800,
                'address': 0x0004,
                'count': 1,
                'slave': 0x01,
                'process_func': self._process_liquid_level
            },
            'ph': {
                'port': 'COM4',
                'baudrate': 4800, 
                'address': 0x0000,
                'count': 2,
                'slave': 0x01,
                'process_func': self._process_ph
            },
            'turbidity': {
                'port': 'COM5',
                'baudrate': 4800,
                'address': 0x0000, 
                'count': 2,
                'slave': 0x01,
                'process_func': self._process_turbidity
            }
        }
        
        # 共享数据存储
        self.sensor_data = {
            'dissolved_oxygen': None,
            'liquid_level': None,
            'ph': None,
            'ph_temperature': None,
            'turbidity': None,
            'turbidity_temperature': None
        }
        
        # 确保输出目录存在
        os.makedirs(output_dir, exist_ok=True)

        # 检查CSV文件是否存在
        self.file_exists = os.path.exists(self.csv_file)

        # 设置日志
        self._setup_logging()

        # 条件导入第三方库（避免在模拟模式或未安装依赖时失败）
        self.pd = None
        self.ModbusClient = None
        if not self.simulate:
            try:
                import pandas as pd  # 延迟导入
                self.pd = pd
            except ImportError:
                self.logger.warning("未检测到pandas，将使用csv模块写入文件")
            try:
                from pymodbus.client.serial import ModbusSerialClient as _ModbusClient
                self.ModbusClient = _ModbusClient
            except ImportError:
                self.logger.warning("未检测到pymodbus，自动切换到模拟模式")
                self.simulate = True

        # 注册信号处理（默认不注册，避免覆盖应用层的SIGINT/SIGTERM处理）
        if register_signals:
            signal.signal(signal.SIGINT, self._signal_handler)
            signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _setup_logging(self):
        """设置日志系统"""
        log_dir = os.path.join(os.path.dirname(__file__), 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('SensorDataService')
    
    def _signal_handler(self, signum, frame):
        """信号处理器，用于优雅关闭"""
        self.logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            self.logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            self.logger.error(f"液位数据处理失败: {e}")
            return {'liquid_level': None}
    
    def _process_ph(self, registers: list) -> Dict[str, Optional[float]]:
        """处理pH数据"""
        try:
            ph_raw = registers[0]
            temperature_raw = registers[1]
            ph = ph_raw / 100.0
            temperature = temperature_raw / 10.0
            return {'ph': ph, 'ph_temperature': temperature}
        except Exception as e:
            self.logger.error(f"pH数据处理失败: {e}")
            return {'ph': None, 'ph_temperature': None}
    
    def _process_turbidity(self, registers: list) -> Dict[str, Optional[float]]:
        """处理浊度数据"""
        try:
            turbidity_raw = registers[0]
            temperature_raw = registers[1]
            turbidity = turbidity_raw / 10.0
            temperature = temperature_raw / 10.0
            return {'turbidity': turbidity, 'turbidity_temperature': temperature}
        except Exception as e:
            self.logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _read_sensor_data(self, sensor_name: str):
        """读取单个传感器数据的线程函数"""
        config = self.sensor_configs[sensor_name]
        
        # 在模拟模式下不创建Modbus客户端，直接生成数据
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                # 依赖缺失已在__init__中切换到模拟模式，这里双重保护
                self.logger.warning(f"{sensor_name}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                port=config['port'],
                baudrate=config['baudrate'],
                stopbits=1,
                bytesize=8,
                parity='N',
                timeout=1
                )
        
        connection_retry_count = 0
        max_connection_retries = 5
        
        while self.running:
            try:
                if self.simulate:
                    # 模拟数据生成
                    while self.running:
                        try:
                            if sensor_name == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_name == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_name == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_name == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            # 更新共享数据
                            with self.data_lock:
                                self.sensor_data.update(processed_data)
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            self.logger.error(f"{sensor_name}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    # 尝试连接
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            self.logger.warning(f"{sensor_name}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            self.logger.error(f"{sensor_name}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    # 重置重试计数
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=config['address'],
                                count=config['count'],
                                slave=config['slave']
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = config['process_func'](rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    self.sensor_data.update(processed_data)
                            else:
                                self.logger.warning(f"{sensor_name}读取失败: {rr}")
                            
                            time.sleep(self.sample_interval_seconds)  # 采样间隔
                            
                        except Exception as e:
                            self.logger.error(f"{sensor_name}数据读取异常: {e}")
                            time.sleep(5)  # 异常后等待5秒再重试
                        
            except Exception as e:
                self.logger.error(f"{sensor_name}传感器线程异常: {e}")
                time.sleep(10)  # 等待10秒后重试连接
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        self.logger.info(f"{sensor_name}传感器线程已停止")
    
    def _data_logging_thread(self):
        """数据记录线程"""
        self.logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    do_val = self.sensor_data.get('dissolved_oxygen')
                    level_val = self.sensor_data.get('liquid_level')
                    ph_val = self.sensor_data.get('ph')
                    ph_temp = self.sensor_data.get('ph_temperature')
                    turbidity_val = self.sensor_data.get('turbidity')
                    turbidity_temp = self.sensor_data.get('turbidity_temperature')
                
                # 模拟模式下不跳过空数据，以便持续输出
                if not self.simulate:
                    # 跳过所有传感器数据为空的轮次
                    if all(val is None for val in [do_val, level_val, ph_val, ph_temp, turbidity_val, turbidity_temp]):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                self.logger.info(f"[{timestamp}] 溶解氧: {do_val if do_val is not None else 'N/A'} | "
                               f"液位: {level_val if level_val is not None else 'N/A'}mm | "
                               f"pH: {ph_val if ph_val is not None else 'N/A'} | "
                               f"pH温度: {ph_temp if ph_temp is not None else 'N/A'}°C | "
                               f"浊度: {turbidity_val if turbidity_val is not None else 'N/A'}NTU | "
                               f"浊度温度: {turbidity_temp if turbidity_temp is not None else 'N/A'}°C")
                
                # 记录数据到CSV（优先使用pandas，缺失时使用csv模块）
                row = [timestamp, do_val, level_val, ph_val, ph_temp, turbidity_val, turbidity_temp]
                headers = ["时间", "溶解氧饱和度", "液位(mm)", "PH", "PH温度(°C)", "浊度(NTU)", "浊度温度(°C)"]
                try:
                    if self.pd is not None:
                        df = self.pd.DataFrame([row], columns=headers)
                        df.to_csv(self.csv_file, mode='a', header=not self.file_exists, index=False)
                        self.file_exists = True
                    else:
                        write_header = not self.file_exists
                        with open(self.csv_file, mode='a', newline='', encoding='utf-8') as f:
                            writer = csv.writer(f)
                            if write_header:
                                writer.writerow(headers)
                            writer.writerow(row)
                        self.file_exists = True
                except Exception as e:
                    self.logger.error(f"写入CSV异常: {e}")

                time.sleep(self.logging_interval_seconds)  # 记录间隔
                
            except Exception as e:
                self.logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        self.logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            self.logger.warning("传感器服务已在运行中")
            return
        
        self.logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for sensor_name in self.sensor_configs.keys():
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(sensor_name,),
                daemon=True,
                name=f"Sensor-{sensor_name}"
            )
            thread.start()
            self.threads.append(thread)
        
        # 启动数据记录线程
        logging_thread = threading.Thread(
            target=self._data_logging_thread,
            daemon=True,
            name="DataLogging"
        )
        logging_thread.start()
        self.threads.append(logging_thread)
        
        mode = "模拟模式" if self.simulate else "硬件模式"
        self.logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        self.logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        self.logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[str, Optional[float]]:
        """获取当前传感器数据"""
        with self.data_lock:
            return self.sensor_data.copy()

def main():
    """主函数，用于独立运行传感器服务"""
    service = SensorDataService()
    
    try:
        service.start()
        print("传感器数据采集服务已启动，按 Ctrl+C 停止...")
        
        # 保持主线程运行
        while service.is_running():
            time.sleep(1)
            
    except KeyboardInterrupt:
        print("\n接收到中断信号，正在停止服务...")
    finally:
        service.stop()
        print("服务已停止")

if __name__ == "__main__":
    main()