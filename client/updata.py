"""
日本养殖项目数据上传客户端
功能：自动上传传感器数据、操作日志和采集图像到远程服务器
作者：AI Assistant
版本：2.0 (优化重构版)
"""

import os
import logging
import time
from datetime import timedelta, date
from functools import wraps
from typing import List, Optional
import requests
import mimetypes

# ==================== 配置管理类 ====================
class UploadConfig:
    """上传配置管理类，统一管理所有配置参数"""
    
    def __init__(self):
        # 数据目录配置
        self.SENSOR_DATA_DIR = r"C:\Users\37897\Desktop\japan_data\sensor_data"
        self.OPERATION_LOGS_DIR = r"C:\Users\37897\Desktop\japan_data\operation_logs"
        self.COLLECTED_IMAGES_DIR = r"C:\Users\37897\Desktop\japan_data\collected_images"
        
        # API配置
        self.API_URL = "http://8.216.33.92:5000/api/updata_file"
        self.REQUEST_TIMEOUT = 15
        
        # 上传配置
        self.LAST_INTERVAL = 61  # 上传最近61天的数据
        self.MAX_RETRY_ATTEMPTS = 3  # 最大重试次数
        self.RETRY_DELAY = 2  # 重试间隔(秒)
        
        # 干运行开关（环境变量控制）：AIJ_UPLOAD_DRY_RUN=1/true/yes 时不实际上传，仅打印与统计
        env_val = os.getenv("AIJ_UPLOAD_DRY_RUN", "0").lower()
        self.DRY_RUN = env_val in ("1", "true", "yes")
        
        # 数据类型映射
        self.DATA_TYPE_CONFIG = {
            "传感器数据": {
                "directory": self.SENSOR_DATA_DIR,
                "filename_pattern": "%Y_%m_%d.csv"
            },
            "操作日志": {
                "directory": self.OPERATION_LOGS_DIR,
                "filename_pattern": "%Y_%m_%d.txt"
            },
            "采集图像": {
                "directory": self.COLLECTED_IMAGES_DIR,
                "filename_pattern": "image_%Y%m%d.csv"
            }
        }
    
    def validate_config(self) -> bool:
        """
        验证配置参数的有效性
        
        Returns:
            bool: 配置是否有效
        """
        try:
            # 检查目录是否存在
            for data_type, config in self.DATA_TYPE_CONFIG.items():
                directory = config["directory"]
                if not os.path.exists(directory):
                    logging.warning(f"目录不存在: {directory} (数据类型: {data_type})")
            
            # 检查API URL格式
            if not self.API_URL.startswith(('http://', 'https://')):
                logging.error(f"无效的API URL格式: {self.API_URL}")
                return False
                
            return True
        except Exception as e:
            logging.error(f"配置验证失败: {e}")
            return False

# ==================== 全局配置实例 ====================
config = UploadConfig()

# ==================== 日志配置 ====================
def setup_logging():
    """配置日志系统，支持文件和控制台输出"""
    log_format = '%(asctime)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s'
    
    # 创建日志目录
    log_dir = os.path.join(os.path.dirname(__file__), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.FileHandler(os.path.join(log_dir, 'upload.log'), encoding='utf-8'),
            logging.StreamHandler()
        ]
    )

# ==================== 重试装饰器 ====================
def retry_on_failure(max_attempts: int = None, delay: float = None):
    """
    重试装饰器，用于网络请求失败时的自动重试
    
    Args:
        max_attempts (int): 最大重试次数，默认使用配置值
        delay (float): 重试间隔秒数，默认使用配置值
    
    Returns:
        装饰器函数
    """
    if max_attempts is None:
        max_attempts = config.MAX_RETRY_ATTEMPTS
    if delay is None:
        delay = config.RETRY_DELAY
    
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
                        logging.warning(f"第{attempt + 1}次尝试失败: {e}, {delay}秒后重试...")
                        time.sleep(delay)
                    else:
                        logging.error(f"所有重试均失败，最终错误: {e}")
            
            raise last_exception
        return wrapper
    return decorator

# ==================== 核心功能函数 ====================
def get_recent_filenames(data_type: str, days: int = None) -> List[str]:
    """
    生成指定数据类型最近几天的文件名列表
    
    Args:
        data_type (str): 数据类型 ("传感器数据", "操作日志", "采集图像")
        days (int): 天数，默认使用配置值
    
    Returns:
        List[str]: 文件名列表
    
    Raises:
        ValueError: 当数据类型不支持时抛出异常
    """
    if days is None:
        days = config.LAST_INTERVAL
    
    if data_type not in config.DATA_TYPE_CONFIG:
        raise ValueError(f"不支持的数据类型: {data_type}")
    
    today = date.today()
    filename_pattern = config.DATA_TYPE_CONFIG[data_type]["filename_pattern"]
    
    filenames = []
    for i in range(days):
        target_date = today - timedelta(days=i)
        filename = target_date.strftime(filename_pattern)
        filenames.append(filename)
    
    logging.info(f"生成{data_type}文件名列表，共{len(filenames)}个文件，时间范围：{days}天")
    return filenames

@retry_on_failure()
def upload_single_file(filepath: str, data_type: str) -> bool:
    """
    上传单个文件到服务器
    
    Args:
        filepath (str): 文件完整路径
        data_type (str): 数据类型标识
    
    Returns:
        bool: 上传是否成功
    
    Raises:
        requests.RequestException: 网络请求异常
        FileNotFoundError: 文件不存在异常
    """
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"文件不存在: {filepath}")
    
    filename = os.path.basename(filepath)
    file_size = os.path.getsize(filepath)
    mime_type, _ = mimetypes.guess_type(filepath)
    
    logging.info(f"开始上传文件: {filename} (大小: {file_size} bytes, 类型: {data_type})")
    
    # 干运行模式：不实际发起网络请求，直接模拟成功
    if config.DRY_RUN:
        logging.info(f"[DRY-RUN] 模拟上传成功: {filename} -> {config.API_URL}")
        return True
    
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (filename, f, mime_type)}
            data = {'type': data_type}
            
            response = requests.post(
                config.API_URL, 
                files=files, 
                data=data, 
                timeout=config.REQUEST_TIMEOUT
            )
            
            if response.status_code == 200:
                logging.info(f"✓ 文件上传成功: {filename}")
                return True
            else:
                error_msg = f"上传失败 - 状态码: {response.status_code}, 响应: {response.text}"
                logging.error(f"✗ {filename} - {error_msg}")
                raise requests.RequestException(error_msg)
                
    except requests.Timeout:
        error_msg = f"上传超时: {filename}"
        logging.error(f"✗ {error_msg}")
        raise requests.RequestException(error_msg)
    except Exception as e:
        error_msg = f"上传异常: {filename} - {str(e)}"
        logging.error(f"✗ {error_msg}")
        raise

def upload_data_by_type(data_type: str) -> dict:
    """
    按数据类型批量上传文件
    
    Args:
        data_type (str): 数据类型 ("传感器数据", "操作日志", "采集图像")
    
    Returns:
        dict: 上传结果统计 {"success": int, "failed": int, "total": int}
    """
    if data_type not in config.DATA_TYPE_CONFIG:
        raise ValueError(f"不支持的数据类型: {data_type}")
    
    logging.info(f"开始批量上传{data_type}...{' (DRY-RUN)' if config.DRY_RUN else ''}")
    
    # 获取配置信息
    type_config = config.DATA_TYPE_CONFIG[data_type]
    directory = type_config["directory"]
    
    # 生成文件名列表
    filenames = get_recent_filenames(data_type)
    
    # 统计结果
    result = {"success": 0, "failed": 0, "total": len(filenames)}
    
    for filename in filenames:
        filepath = os.path.join(directory, filename)
        
        if not os.path.exists(filepath):
            logging.warning(f"⚠ 文件不存在，跳过: {filename}")
            result["failed"] += 1
            continue
        
        try:
            if upload_single_file(filepath, data_type):
                result["success"] += 1
            else:
                result["failed"] += 1
        except Exception as e:
            logging.error(f"上传文件失败: {filename} - {e}")
            result["failed"] += 1
    
    # 输出统计结果
    logging.info(f"{data_type}上传完成 - 成功: {result['success']}, 失败: {result['failed']}, 总计: {result['total']}")
    return result

# ==================== 具体上传函数 ====================
def upload_sensor_data() -> dict:
    """
    上传传感器数据文件
    
    Returns:
        dict: 上传结果统计
    """
    return upload_data_by_type("传感器数据")

def upload_operation_logs() -> dict:
    """
    上传操作日志文件
    
    Returns:
        dict: 上传结果统计
    """
    return upload_data_by_type("操作日志")

def upload_collected_images() -> dict:
    """
    上传采集图像文件
    
    Returns:
        dict: 上传结果统计
    """
    return upload_data_by_type("采集图像")

# ==================== 主执行函数 ====================
def main():
    """
    主执行函数，协调所有上传任务
    """
    # 初始化日志系统
    setup_logging()
    logging.info("=" * 50)
    logging.info("日本养殖项目数据上传任务开始")
    if config.DRY_RUN:
        logging.info("当前为干运行模式（不会实际上传，仅打印与统计）。可通过环境变量 AIJ_UPLOAD_DRY_RUN=0 关闭")
    logging.info("=" * 50)
    
    # 验证配置
    if not config.validate_config():
        logging.error("配置验证失败，程序退出")
        return
    
    # 执行上传任务
    total_results = {"success": 0, "failed": 0, "total": 0}
    
    upload_tasks = [
        ("传感器数据", upload_sensor_data),
        ("操作日志", upload_operation_logs),
        ("采集图像", upload_collected_images)
    ]
    
    for task_name, upload_func in upload_tasks:
        try:
            logging.info(f"开始执行{task_name}上传任务...")
            result = upload_func()
            
            # 累计统计结果
            total_results["success"] += result["success"]
            total_results["failed"] += result["failed"]
            total_results["total"] += result["total"]
            
        except Exception as e:
            logging.error(f"{task_name}上传任务执行失败: {e}")
    
    # 输出最终统计
    logging.info("=" * 50)
    logging.info("所有上传任务完成")
    logging.info(f"总体统计 - 成功: {total_results['success']}, 失败: {total_results['failed']}, 总计: {total_results['total']}")
    success_rate = (total_results['success'] / total_results['total'] * 100) if total_results['total'] > 0 else 0
    logging.info(f"成功率: {success_rate:.1f}%")
    logging.info("=" * 50)

# ==================== 程序入口 ====================
if __name__ == "__main__":
    main()
