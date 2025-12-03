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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            logger.error(f"液位数据处理失败: {e}")
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
            logger.error(f"pH数据处理失败: {e}")
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
            logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _get_process_func(self, sensor_type: str):
        """获取传感器处理函数"""
        process_funcs = {
            'dissolved_oxygen': self._process_dissolved_oxygen,
            'liquid_level': self._process_liquid_level,
            'ph': self._process_ph,
            'turbidity': self._process_turbidity,
        }
        return process_funcs.get(sensor_type)
    
    def _read_sensor_data(self, device_config: Dict):
        """读取单个传感器数据的线程函数"""
        sensor_id = device_config['sensor_id']
        sensor_type = device_config['type']
        port = device_config['port']
        baudrate = device_config['baudrate']
        address = device_config['address']
        count = device_config['count']
        slave = device_config['slave']
        metric = device_config.get('metric', sensor_type)
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        process_func = self._get_process_func(sensor_type)
        if not process_func:
            logger.error(f"未知的传感器类型: {sensor_type}")
            return
        
        # 在模拟模式下不创建Modbus客户端
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                logger.warning(f"传感器{sensor_id}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                    port=port,
                    baudrate=baudrate,
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
                            if sensor_type == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_type == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_type == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_type == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            
                            # 更新共享数据
                            with self.data_lock:
                                if sensor_id not in self.sensor_data:
                                    self.sensor_data[sensor_id] = {}
                                self.sensor_data[sensor_id].update(processed_data)
                            
                            # 上传数据到服务端
                            self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            logger.warning(f"传感器{sensor_id}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error(f"传感器{sensor_id}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=address,
                                count=count,
                                slave=slave
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = process_func(rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    if sensor_id not in self.sensor_data:
                                        self.sensor_data[sensor_id] = {}
                                    self.sensor_data[sensor_id].update(processed_data)
                                
                                # 上传数据到服务端
                                self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                            
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}数据读取异常: {e}")
                            time.sleep(5)
                        
            except Exception as e:
                logger.error(f"传感器{sensor_id}线程异常: {e}")
                time.sleep(10)
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        logger.info(f"传感器{sensor_id}线程已停止")
    
    def _upload_sensor_data(self, device_config: Dict, processed_data: Dict[str, Optional[float]]):
        """上传传感器数据到服务端"""
        sensor_id = device_config['sensor_id']
        metric = device_config.get('metric', device_config['type'])
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        # 获取当前时间戳（毫秒）
        timestamp_ms = int(time.time() * 1000)
        
        # 上传每个指标值
        for key, value in processed_data.items():
            if value is None:
                continue
            
            # 确定指标名称和单位
            if key == 'dissolved_oxygen':
                upload_metric = 'do'
                upload_unit = 'mg/L' if not unit else unit
            elif key == 'liquid_level':
                upload_metric = 'water_level'
                upload_unit = 'mm' if not unit else unit
            elif key == 'ph':
                upload_metric = 'ph'
                upload_unit = 'pH' if not unit else unit
            elif key == 'ph_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            elif key == 'turbidity':
                upload_metric = 'turbidity'
                upload_unit = 'NTU' if not unit else unit
            elif key == 'turbidity_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            else:
                upload_metric = key
                upload_unit = unit
            
            # 生成描述信息（包含池号和批次信息，避免与type_name重复）
            pool_id = device_config.get('pool_id', config_manager.get_pool_id())
            batch_id = device_config.get('batch_id', config_manager.get_batch_id())
            description = f"{pool_id}号池 - {upload_metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=upload_metric,
                    unit=upload_unit,
                    timestamp=timestamp_ms,
                    type_name=type_name,
                    description=description
                )
                logger.debug(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}")
            except Exception as e:
                logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")
    
    def _data_logging_thread(self):
        """数据记录线程（记录到CSV）"""
        logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 收集所有传感器的数据
                    row_data = {'时间': timestamp}
                    for sensor_id, data in self.sensor_data.items():
                        for key, value in data.items():
                            row_data[key] = value
                
                # 如果所有数据都为空，跳过
                if not self.simulate:
                    if all(v is None for v in row_data.values() if v != timestamp):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                data_str = ' | '.join([f"{k}: {v if v is not None else 'N/A'}" for k, v in row_data.items()])
                logger.info(f"[{timestamp}] {data_str}")
                
                # 记录数据到CSV
                headers = ["时间"] + sorted([k for k in row_data.keys() if k != '时间'])
                row = [row_data.get(h, None) for h in headers]
                
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
                    logger.error(f"写入CSV异常: {e}")
                
                time.sleep(self.logging_interval_seconds)
                
            except Exception as e:
                logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            logger.warning("传感器服务已在运行中")
            return
        
        logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for device_config in self.sensor_devices:
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(device_config,),
                daemon=True,
                name=f"Sensor-{device_config['sensor_id']}"
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
        logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[int, Dict[str, Optional[float]]]:
        """获取当前传感器数据（按sensor_id索引）"""
        with self.data_lock:
            return {k: v.copy() for k, v in self.sensor_data.items()}



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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            logger.error(f"液位数据处理失败: {e}")
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
            logger.error(f"pH数据处理失败: {e}")
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
            logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _get_process_func(self, sensor_type: str):
        """获取传感器处理函数"""
        process_funcs = {
            'dissolved_oxygen': self._process_dissolved_oxygen,
            'liquid_level': self._process_liquid_level,
            'ph': self._process_ph,
            'turbidity': self._process_turbidity,
        }
        return process_funcs.get(sensor_type)
    
    def _read_sensor_data(self, device_config: Dict):
        """读取单个传感器数据的线程函数"""
        sensor_id = device_config['sensor_id']
        sensor_type = device_config['type']
        port = device_config['port']
        baudrate = device_config['baudrate']
        address = device_config['address']
        count = device_config['count']
        slave = device_config['slave']
        metric = device_config.get('metric', sensor_type)
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        process_func = self._get_process_func(sensor_type)
        if not process_func:
            logger.error(f"未知的传感器类型: {sensor_type}")
            return
        
        # 在模拟模式下不创建Modbus客户端
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                logger.warning(f"传感器{sensor_id}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                    port=port,
                    baudrate=baudrate,
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
                            if sensor_type == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_type == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_type == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_type == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            
                            # 更新共享数据
                            with self.data_lock:
                                if sensor_id not in self.sensor_data:
                                    self.sensor_data[sensor_id] = {}
                                self.sensor_data[sensor_id].update(processed_data)
                            
                            # 上传数据到服务端
                            self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            logger.warning(f"传感器{sensor_id}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error(f"传感器{sensor_id}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=address,
                                count=count,
                                slave=slave
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = process_func(rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    if sensor_id not in self.sensor_data:
                                        self.sensor_data[sensor_id] = {}
                                    self.sensor_data[sensor_id].update(processed_data)
                                
                                # 上传数据到服务端
                                self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                            
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}数据读取异常: {e}")
                            time.sleep(5)
                        
            except Exception as e:
                logger.error(f"传感器{sensor_id}线程异常: {e}")
                time.sleep(10)
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        logger.info(f"传感器{sensor_id}线程已停止")
    
    def _upload_sensor_data(self, device_config: Dict, processed_data: Dict[str, Optional[float]]):
        """上传传感器数据到服务端"""
        sensor_id = device_config['sensor_id']
        metric = device_config.get('metric', device_config['type'])
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        # 获取当前时间戳（毫秒）
        timestamp_ms = int(time.time() * 1000)
        
        # 上传每个指标值
        for key, value in processed_data.items():
            if value is None:
                continue
            
            # 确定指标名称和单位
            if key == 'dissolved_oxygen':
                upload_metric = 'do'
                upload_unit = 'mg/L' if not unit else unit
            elif key == 'liquid_level':
                upload_metric = 'water_level'
                upload_unit = 'mm' if not unit else unit
            elif key == 'ph':
                upload_metric = 'ph'
                upload_unit = 'pH' if not unit else unit
            elif key == 'ph_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            elif key == 'turbidity':
                upload_metric = 'turbidity'
                upload_unit = 'NTU' if not unit else unit
            elif key == 'turbidity_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            else:
                upload_metric = key
                upload_unit = unit
            
            # 生成描述信息（包含池号和批次信息，避免与type_name重复）
            pool_id = device_config.get('pool_id', config_manager.get_pool_id())
            batch_id = device_config.get('batch_id', config_manager.get_batch_id())
            description = f"{pool_id}号池 - {upload_metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=upload_metric,
                    unit=upload_unit,
                    timestamp=timestamp_ms,
                    type_name=type_name,
                    description=description
                )
                logger.debug(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}")
            except Exception as e:
                logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")
    
    def _data_logging_thread(self):
        """数据记录线程（记录到CSV）"""
        logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 收集所有传感器的数据
                    row_data = {'时间': timestamp}
                    for sensor_id, data in self.sensor_data.items():
                        for key, value in data.items():
                            row_data[key] = value
                
                # 如果所有数据都为空，跳过
                if not self.simulate:
                    if all(v is None for v in row_data.values() if v != timestamp):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                data_str = ' | '.join([f"{k}: {v if v is not None else 'N/A'}" for k, v in row_data.items()])
                logger.info(f"[{timestamp}] {data_str}")
                
                # 记录数据到CSV
                headers = ["时间"] + sorted([k for k in row_data.keys() if k != '时间'])
                row = [row_data.get(h, None) for h in headers]
                
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
                    logger.error(f"写入CSV异常: {e}")
                
                time.sleep(self.logging_interval_seconds)
                
            except Exception as e:
                logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            logger.warning("传感器服务已在运行中")
            return
        
        logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for device_config in self.sensor_devices:
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(device_config,),
                daemon=True,
                name=f"Sensor-{device_config['sensor_id']}"
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
        logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[int, Dict[str, Optional[float]]]:
        """获取当前传感器数据（按sensor_id索引）"""
        with self.data_lock:
            return {k: v.copy() for k, v in self.sensor_data.items()}


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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            logger.error(f"液位数据处理失败: {e}")
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
            logger.error(f"pH数据处理失败: {e}")
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
            logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _get_process_func(self, sensor_type: str):
        """获取传感器处理函数"""
        process_funcs = {
            'dissolved_oxygen': self._process_dissolved_oxygen,
            'liquid_level': self._process_liquid_level,
            'ph': self._process_ph,
            'turbidity': self._process_turbidity,
        }
        return process_funcs.get(sensor_type)
    
    def _read_sensor_data(self, device_config: Dict):
        """读取单个传感器数据的线程函数"""
        sensor_id = device_config['sensor_id']
        sensor_type = device_config['type']
        port = device_config['port']
        baudrate = device_config['baudrate']
        address = device_config['address']
        count = device_config['count']
        slave = device_config['slave']
        metric = device_config.get('metric', sensor_type)
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        process_func = self._get_process_func(sensor_type)
        if not process_func:
            logger.error(f"未知的传感器类型: {sensor_type}")
            return
        
        # 在模拟模式下不创建Modbus客户端
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                logger.warning(f"传感器{sensor_id}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                    port=port,
                    baudrate=baudrate,
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
                            if sensor_type == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_type == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_type == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_type == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            
                            # 更新共享数据
                            with self.data_lock:
                                if sensor_id not in self.sensor_data:
                                    self.sensor_data[sensor_id] = {}
                                self.sensor_data[sensor_id].update(processed_data)
                            
                            # 上传数据到服务端
                            self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            logger.warning(f"传感器{sensor_id}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error(f"传感器{sensor_id}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=address,
                                count=count,
                                slave=slave
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = process_func(rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    if sensor_id not in self.sensor_data:
                                        self.sensor_data[sensor_id] = {}
                                    self.sensor_data[sensor_id].update(processed_data)
                                
                                # 上传数据到服务端
                                self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                            
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}数据读取异常: {e}")
                            time.sleep(5)
                        
            except Exception as e:
                logger.error(f"传感器{sensor_id}线程异常: {e}")
                time.sleep(10)
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        logger.info(f"传感器{sensor_id}线程已停止")
    
    def _upload_sensor_data(self, device_config: Dict, processed_data: Dict[str, Optional[float]]):
        """上传传感器数据到服务端"""
        sensor_id = device_config['sensor_id']
        metric = device_config.get('metric', device_config['type'])
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        # 获取当前时间戳（毫秒）
        timestamp_ms = int(time.time() * 1000)
        
        # 上传每个指标值
        for key, value in processed_data.items():
            if value is None:
                continue
            
            # 确定指标名称和单位
            if key == 'dissolved_oxygen':
                upload_metric = 'do'
                upload_unit = 'mg/L' if not unit else unit
            elif key == 'liquid_level':
                upload_metric = 'water_level'
                upload_unit = 'mm' if not unit else unit
            elif key == 'ph':
                upload_metric = 'ph'
                upload_unit = 'pH' if not unit else unit
            elif key == 'ph_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            elif key == 'turbidity':
                upload_metric = 'turbidity'
                upload_unit = 'NTU' if not unit else unit
            elif key == 'turbidity_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            else:
                upload_metric = key
                upload_unit = unit
            
            # 生成描述信息（包含池号和批次信息，避免与type_name重复）
            pool_id = device_config.get('pool_id', config_manager.get_pool_id())
            batch_id = device_config.get('batch_id', config_manager.get_batch_id())
            description = f"{pool_id}号池 - {upload_metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=upload_metric,
                    unit=upload_unit,
                    timestamp=timestamp_ms,
                    type_name=type_name,
                    description=description
                )
                logger.debug(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}")
            except Exception as e:
                logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")
    
    def _data_logging_thread(self):
        """数据记录线程（记录到CSV）"""
        logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 收集所有传感器的数据
                    row_data = {'时间': timestamp}
                    for sensor_id, data in self.sensor_data.items():
                        for key, value in data.items():
                            row_data[key] = value
                
                # 如果所有数据都为空，跳过
                if not self.simulate:
                    if all(v is None for v in row_data.values() if v != timestamp):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                data_str = ' | '.join([f"{k}: {v if v is not None else 'N/A'}" for k, v in row_data.items()])
                logger.info(f"[{timestamp}] {data_str}")
                
                # 记录数据到CSV
                headers = ["时间"] + sorted([k for k in row_data.keys() if k != '时间'])
                row = [row_data.get(h, None) for h in headers]
                
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
                    logger.error(f"写入CSV异常: {e}")
                
                time.sleep(self.logging_interval_seconds)
                
            except Exception as e:
                logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            logger.warning("传感器服务已在运行中")
            return
        
        logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for device_config in self.sensor_devices:
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(device_config,),
                daemon=True,
                name=f"Sensor-{device_config['sensor_id']}"
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
        logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[int, Dict[str, Optional[float]]]:
        """获取当前传感器数据（按sensor_id索引）"""
        with self.data_lock:
            return {k: v.copy() for k, v in self.sensor_data.items()}



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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            logger.error(f"液位数据处理失败: {e}")
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
            logger.error(f"pH数据处理失败: {e}")
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
            logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _get_process_func(self, sensor_type: str):
        """获取传感器处理函数"""
        process_funcs = {
            'dissolved_oxygen': self._process_dissolved_oxygen,
            'liquid_level': self._process_liquid_level,
            'ph': self._process_ph,
            'turbidity': self._process_turbidity,
        }
        return process_funcs.get(sensor_type)
    
    def _read_sensor_data(self, device_config: Dict):
        """读取单个传感器数据的线程函数"""
        sensor_id = device_config['sensor_id']
        sensor_type = device_config['type']
        port = device_config['port']
        baudrate = device_config['baudrate']
        address = device_config['address']
        count = device_config['count']
        slave = device_config['slave']
        metric = device_config.get('metric', sensor_type)
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        process_func = self._get_process_func(sensor_type)
        if not process_func:
            logger.error(f"未知的传感器类型: {sensor_type}")
            return
        
        # 在模拟模式下不创建Modbus客户端
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                logger.warning(f"传感器{sensor_id}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                    port=port,
                    baudrate=baudrate,
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
                            if sensor_type == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_type == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_type == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_type == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            
                            # 更新共享数据
                            with self.data_lock:
                                if sensor_id not in self.sensor_data:
                                    self.sensor_data[sensor_id] = {}
                                self.sensor_data[sensor_id].update(processed_data)
                            
                            # 上传数据到服务端
                            self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            logger.warning(f"传感器{sensor_id}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error(f"传感器{sensor_id}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=address,
                                count=count,
                                slave=slave
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = process_func(rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    if sensor_id not in self.sensor_data:
                                        self.sensor_data[sensor_id] = {}
                                    self.sensor_data[sensor_id].update(processed_data)
                                
                                # 上传数据到服务端
                                self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                            
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}数据读取异常: {e}")
                            time.sleep(5)
                        
            except Exception as e:
                logger.error(f"传感器{sensor_id}线程异常: {e}")
                time.sleep(10)
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        logger.info(f"传感器{sensor_id}线程已停止")
    
    def _upload_sensor_data(self, device_config: Dict, processed_data: Dict[str, Optional[float]]):
        """上传传感器数据到服务端"""
        sensor_id = device_config['sensor_id']
        metric = device_config.get('metric', device_config['type'])
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        # 获取当前时间戳（毫秒）
        timestamp_ms = int(time.time() * 1000)
        
        # 上传每个指标值
        for key, value in processed_data.items():
            if value is None:
                continue
            
            # 确定指标名称和单位
            if key == 'dissolved_oxygen':
                upload_metric = 'do'
                upload_unit = 'mg/L' if not unit else unit
            elif key == 'liquid_level':
                upload_metric = 'water_level'
                upload_unit = 'mm' if not unit else unit
            elif key == 'ph':
                upload_metric = 'ph'
                upload_unit = 'pH' if not unit else unit
            elif key == 'ph_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            elif key == 'turbidity':
                upload_metric = 'turbidity'
                upload_unit = 'NTU' if not unit else unit
            elif key == 'turbidity_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            else:
                upload_metric = key
                upload_unit = unit
            
            # 生成描述信息（包含池号和批次信息，避免与type_name重复）
            pool_id = device_config.get('pool_id', config_manager.get_pool_id())
            batch_id = device_config.get('batch_id', config_manager.get_batch_id())
            description = f"{pool_id}号池 - {upload_metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=upload_metric,
                    unit=upload_unit,
                    timestamp=timestamp_ms,
                    type_name=type_name,
                    description=description
                )
                logger.debug(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}")
            except Exception as e:
                logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")
    
    def _data_logging_thread(self):
        """数据记录线程（记录到CSV）"""
        logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 收集所有传感器的数据
                    row_data = {'时间': timestamp}
                    for sensor_id, data in self.sensor_data.items():
                        for key, value in data.items():
                            row_data[key] = value
                
                # 如果所有数据都为空，跳过
                if not self.simulate:
                    if all(v is None for v in row_data.values() if v != timestamp):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                data_str = ' | '.join([f"{k}: {v if v is not None else 'N/A'}" for k, v in row_data.items()])
                logger.info(f"[{timestamp}] {data_str}")
                
                # 记录数据到CSV
                headers = ["时间"] + sorted([k for k in row_data.keys() if k != '时间'])
                row = [row_data.get(h, None) for h in headers]
                
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
                    logger.error(f"写入CSV异常: {e}")
                
                time.sleep(self.logging_interval_seconds)
                
            except Exception as e:
                logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            logger.warning("传感器服务已在运行中")
            return
        
        logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for device_config in self.sensor_devices:
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(device_config,),
                daemon=True,
                name=f"Sensor-{device_config['sensor_id']}"
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
        logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[int, Dict[str, Optional[float]]]:
        """获取当前传感器数据（按sensor_id索引）"""
        with self.data_lock:
            return {k: v.copy() for k, v in self.sensor_data.items()}


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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            logger.error(f"液位数据处理失败: {e}")
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
            logger.error(f"pH数据处理失败: {e}")
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
            logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _get_process_func(self, sensor_type: str):
        """获取传感器处理函数"""
        process_funcs = {
            'dissolved_oxygen': self._process_dissolved_oxygen,
            'liquid_level': self._process_liquid_level,
            'ph': self._process_ph,
            'turbidity': self._process_turbidity,
        }
        return process_funcs.get(sensor_type)
    
    def _read_sensor_data(self, device_config: Dict):
        """读取单个传感器数据的线程函数"""
        sensor_id = device_config['sensor_id']
        sensor_type = device_config['type']
        port = device_config['port']
        baudrate = device_config['baudrate']
        address = device_config['address']
        count = device_config['count']
        slave = device_config['slave']
        metric = device_config.get('metric', sensor_type)
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        process_func = self._get_process_func(sensor_type)
        if not process_func:
            logger.error(f"未知的传感器类型: {sensor_type}")
            return
        
        # 在模拟模式下不创建Modbus客户端
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                logger.warning(f"传感器{sensor_id}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                    port=port,
                    baudrate=baudrate,
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
                            if sensor_type == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_type == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_type == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_type == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            
                            # 更新共享数据
                            with self.data_lock:
                                if sensor_id not in self.sensor_data:
                                    self.sensor_data[sensor_id] = {}
                                self.sensor_data[sensor_id].update(processed_data)
                            
                            # 上传数据到服务端
                            self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            logger.warning(f"传感器{sensor_id}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error(f"传感器{sensor_id}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=address,
                                count=count,
                                slave=slave
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = process_func(rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    if sensor_id not in self.sensor_data:
                                        self.sensor_data[sensor_id] = {}
                                    self.sensor_data[sensor_id].update(processed_data)
                                
                                # 上传数据到服务端
                                self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                            
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}数据读取异常: {e}")
                            time.sleep(5)
                        
            except Exception as e:
                logger.error(f"传感器{sensor_id}线程异常: {e}")
                time.sleep(10)
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        logger.info(f"传感器{sensor_id}线程已停止")
    
    def _upload_sensor_data(self, device_config: Dict, processed_data: Dict[str, Optional[float]]):
        """上传传感器数据到服务端"""
        sensor_id = device_config['sensor_id']
        metric = device_config.get('metric', device_config['type'])
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        # 获取当前时间戳（毫秒）
        timestamp_ms = int(time.time() * 1000)
        
        # 上传每个指标值
        for key, value in processed_data.items():
            if value is None:
                continue
            
            # 确定指标名称和单位
            if key == 'dissolved_oxygen':
                upload_metric = 'do'
                upload_unit = 'mg/L' if not unit else unit
            elif key == 'liquid_level':
                upload_metric = 'water_level'
                upload_unit = 'mm' if not unit else unit
            elif key == 'ph':
                upload_metric = 'ph'
                upload_unit = 'pH' if not unit else unit
            elif key == 'ph_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            elif key == 'turbidity':
                upload_metric = 'turbidity'
                upload_unit = 'NTU' if not unit else unit
            elif key == 'turbidity_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            else:
                upload_metric = key
                upload_unit = unit
            
            # 生成描述信息（包含池号和批次信息，避免与type_name重复）
            pool_id = device_config.get('pool_id', config_manager.get_pool_id())
            batch_id = device_config.get('batch_id', config_manager.get_batch_id())
            description = f"{pool_id}号池 - {upload_metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=upload_metric,
                    unit=upload_unit,
                    timestamp=timestamp_ms,
                    type_name=type_name,
                    description=description
                )
                logger.debug(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}")
            except Exception as e:
                logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")
    
    def _data_logging_thread(self):
        """数据记录线程（记录到CSV）"""
        logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 收集所有传感器的数据
                    row_data = {'时间': timestamp}
                    for sensor_id, data in self.sensor_data.items():
                        for key, value in data.items():
                            row_data[key] = value
                
                # 如果所有数据都为空，跳过
                if not self.simulate:
                    if all(v is None for v in row_data.values() if v != timestamp):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                data_str = ' | '.join([f"{k}: {v if v is not None else 'N/A'}" for k, v in row_data.items()])
                logger.info(f"[{timestamp}] {data_str}")
                
                # 记录数据到CSV
                headers = ["时间"] + sorted([k for k in row_data.keys() if k != '时间'])
                row = [row_data.get(h, None) for h in headers]
                
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
                    logger.error(f"写入CSV异常: {e}")
                
                time.sleep(self.logging_interval_seconds)
                
            except Exception as e:
                logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            logger.warning("传感器服务已在运行中")
            return
        
        logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for device_config in self.sensor_devices:
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(device_config,),
                daemon=True,
                name=f"Sensor-{device_config['sensor_id']}"
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
        logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[int, Dict[str, Optional[float]]]:
        """获取当前传感器数据（按sensor_id索引）"""
        with self.data_lock:
            return {k: v.copy() for k, v in self.sensor_data.items()}



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
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, 'sensor_service.log'), encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
    
    def _signal_handler(self, signum, frame):
        """信号处理器"""
        logger.info(f"接收到信号 {signum}，开始优雅关闭传感器服务...")
        self.stop()
    
    def _process_dissolved_oxygen(self, registers: list) -> Dict[str, Optional[float]]:
        """处理溶解氧数据"""
        try:
            raw = (registers[0] << 16) | registers[1]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
            return {'dissolved_oxygen': oxygen_saturation}
        except Exception as e:
            logger.error(f"溶解氧数据处理失败: {e}")
            return {'dissolved_oxygen': None}
    
    def _process_liquid_level(self, registers: list) -> Dict[str, Optional[float]]:
        """处理液位数据"""
        try:
            level_raw = registers[0]
            return {'liquid_level': level_raw}
        except Exception as e:
            logger.error(f"液位数据处理失败: {e}")
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
            logger.error(f"pH数据处理失败: {e}")
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
            logger.error(f"浊度数据处理失败: {e}")
            return {'turbidity': None, 'turbidity_temperature': None}
    
    def _get_process_func(self, sensor_type: str):
        """获取传感器处理函数"""
        process_funcs = {
            'dissolved_oxygen': self._process_dissolved_oxygen,
            'liquid_level': self._process_liquid_level,
            'ph': self._process_ph,
            'turbidity': self._process_turbidity,
        }
        return process_funcs.get(sensor_type)
    
    def _read_sensor_data(self, device_config: Dict):
        """读取单个传感器数据的线程函数"""
        sensor_id = device_config['sensor_id']
        sensor_type = device_config['type']
        port = device_config['port']
        baudrate = device_config['baudrate']
        address = device_config['address']
        count = device_config['count']
        slave = device_config['slave']
        metric = device_config.get('metric', sensor_type)
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        process_func = self._get_process_func(sensor_type)
        if not process_func:
            logger.error(f"未知的传感器类型: {sensor_type}")
            return
        
        # 在模拟模式下不创建Modbus客户端
        client = None
        if not self.simulate:
            if self.ModbusClient is None:
                logger.warning(f"传感器{sensor_id}未加载Modbus客户端，使用模拟模式")
            else:
                client = self.ModbusClient(
                    port=port,
                    baudrate=baudrate,
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
                            if sensor_type == 'dissolved_oxygen':
                                processed_data = {'dissolved_oxygen': round(random.uniform(6.5, 8.2), 3)}
                            elif sensor_type == 'liquid_level':
                                processed_data = {'liquid_level': random.randint(900, 1100)}
                            elif sensor_type == 'ph':
                                ph = round(random.uniform(6.8, 7.6), 2)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'ph': ph, 'ph_temperature': temp}
                            elif sensor_type == 'turbidity':
                                turbidity = round(random.uniform(0.0, 5.0), 1)
                                temp = round(random.uniform(24.0, 30.0), 1)
                                processed_data = {'turbidity': turbidity, 'turbidity_temperature': temp}
                            else:
                                processed_data = {}
                            
                            # 更新共享数据
                            with self.data_lock:
                                if sensor_id not in self.sensor_data:
                                    self.sensor_data[sensor_id] = {}
                                self.sensor_data[sensor_id].update(processed_data)
                            
                            # 上传数据到服务端
                            self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}模拟数据生成异常: {e}")
                            time.sleep(5)
                else:
                    # 实际设备读取
                    if not client.connect():
                        connection_retry_count += 1
                        if connection_retry_count <= max_connection_retries:
                            logger.warning(f"传感器{sensor_id}串口连接失败，第{connection_retry_count}次重试...")
                            time.sleep(5)
                            continue
                        else:
                            logger.error(f"传感器{sensor_id}串口连接失败，已达最大重试次数，跳过此传感器")
                            break
                    
                    connection_retry_count = 0
                    
                    # 读取数据
                    while self.running:
                        try:
                            rr = client.read_holding_registers(
                                address=address,
                                count=count,
                                slave=slave
                            )
                            
                            if not rr.isError():
                                # 处理数据
                                processed_data = process_func(rr.registers)
                                
                                # 更新共享数据
                                with self.data_lock:
                                    if sensor_id not in self.sensor_data:
                                        self.sensor_data[sensor_id] = {}
                                    self.sensor_data[sensor_id].update(processed_data)
                                
                                # 上传数据到服务端
                                self._upload_sensor_data(device_config, processed_data)
                            
                            time.sleep(self.sample_interval_seconds)
                            
                        except Exception as e:
                            logger.error(f"传感器{sensor_id}数据读取异常: {e}")
                            time.sleep(5)
                        
            except Exception as e:
                logger.error(f"传感器{sensor_id}线程异常: {e}")
                time.sleep(10)
            finally:
                try:
                    if client is not None:
                        client.close()
                except:
                    pass
        
        logger.info(f"传感器{sensor_id}线程已停止")
    
    def _upload_sensor_data(self, device_config: Dict, processed_data: Dict[str, Optional[float]]):
        """上传传感器数据到服务端"""
        sensor_id = device_config['sensor_id']
        metric = device_config.get('metric', device_config['type'])
        unit = device_config.get('unit', '')
        type_name = device_config.get('name', '')
        
        # 获取当前时间戳（毫秒）
        timestamp_ms = int(time.time() * 1000)
        
        # 上传每个指标值
        for key, value in processed_data.items():
            if value is None:
                continue
            
            # 确定指标名称和单位
            if key == 'dissolved_oxygen':
                upload_metric = 'do'
                upload_unit = 'mg/L' if not unit else unit
            elif key == 'liquid_level':
                upload_metric = 'water_level'
                upload_unit = 'mm' if not unit else unit
            elif key == 'ph':
                upload_metric = 'ph'
                upload_unit = 'pH' if not unit else unit
            elif key == 'ph_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            elif key == 'turbidity':
                upload_metric = 'turbidity'
                upload_unit = 'NTU' if not unit else unit
            elif key == 'turbidity_temperature':
                upload_metric = 'temperature'
                upload_unit = '°C' if not unit else unit
            else:
                upload_metric = key
                upload_unit = unit
            
            # 生成描述信息（包含池号和批次信息，避免与type_name重复）
            pool_id = device_config.get('pool_id', config_manager.get_pool_id())
            batch_id = device_config.get('batch_id', config_manager.get_batch_id())
            description = f"{pool_id}号池 - {upload_metric}"
            if batch_id:
                description += f" - 批次{batch_id}"
            
            try:
                api_client.send_sensor_data(
                    sensor_id=sensor_id,
                    value=value,
                    metric=upload_metric,
                    unit=upload_unit,
                    timestamp=timestamp_ms,
                    type_name=type_name,
                    description=description
                )
                logger.debug(f"传感器数据上传成功: sensor_id={sensor_id}, metric={upload_metric}, value={value}")
            except Exception as e:
                logger.error(f"传感器数据上传失败: sensor_id={sensor_id}, metric={upload_metric}, error={e}")
    
    def _data_logging_thread(self):
        """数据记录线程（记录到CSV）"""
        logger.info("数据记录线程启动")
        
        while self.running:
            try:
                with self.data_lock:
                    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                    
                    # 收集所有传感器的数据
                    row_data = {'时间': timestamp}
                    for sensor_id, data in self.sensor_data.items():
                        for key, value in data.items():
                            row_data[key] = value
                
                # 如果所有数据都为空，跳过
                if not self.simulate:
                    if all(v is None for v in row_data.values() if v != timestamp):
                        time.sleep(5)
                        continue
                
                # 打印当前采集数据
                data_str = ' | '.join([f"{k}: {v if v is not None else 'N/A'}" for k, v in row_data.items()])
                logger.info(f"[{timestamp}] {data_str}")
                
                # 记录数据到CSV
                headers = ["时间"] + sorted([k for k in row_data.keys() if k != '时间'])
                row = [row_data.get(h, None) for h in headers]
                
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
                    logger.error(f"写入CSV异常: {e}")
                
                time.sleep(self.logging_interval_seconds)
                
            except Exception as e:
                logger.error(f"数据记录异常: {e}")
                time.sleep(5)
        
        logger.info("数据记录线程已停止")
    
    def start(self):
        """启动传感器数据采集服务"""
        if self.running:
            logger.warning("传感器服务已在运行中")
            return
        
        logger.info("启动传感器数据采集服务...")
        self.running = True
        
        # 启动传感器读取线程
        for device_config in self.sensor_devices:
            thread = threading.Thread(
                target=self._read_sensor_data,
                args=(device_config,),
                daemon=True,
                name=f"Sensor-{device_config['sensor_id']}"
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
        logger.info(f"传感器服务启动成功（{mode}），共启动{len(self.threads)}个线程")
    
    def stop(self):
        """停止传感器数据采集服务"""
        if not self.running:
            return
        
        logger.info("正在停止传感器数据采集服务...")
        self.running = False
        
        # 等待所有线程结束
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)
        
        self.threads.clear()
        logger.info("传感器数据采集服务已停止")
    
    def is_running(self) -> bool:
        """检查服务是否正在运行"""
        return self.running
    
    def get_current_data(self) -> Dict[int, Dict[str, Optional[float]]]:
        """获取当前传感器数据（按sensor_id索引）"""
        with self.data_lock:
            return {k: v.copy() for k, v in self.sensor_data.items()}


