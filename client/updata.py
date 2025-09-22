import os
from  datetime import timedelta, date
import requests
import mimetypes

# 配置路径与接口
SENSOR_DATA_DIR = r"C:\Users\37897\Desktop\japan_data\sensor_data"
OPREATION_LOGS_DIR = r"C:\Users\37897\Desktop\japan_data\operation_logs"
COLLECTED_IMAGES_DIR = r"C:\Users\37897\Desktop\japan_data\collected_images"
API_URL = "http://8.216.33.92:5000/api/updata_file"  
last_interval = 61

# 生成最近7天的日期列表
def get_last_data(data_type,last_interval):
    today = date.today()
    if data_type == "传感器数据":
        return [(today - timedelta(days=i)).strftime("%Y_%m_%d.csv") for i in range(last_interval)]
    today = date.today()
    if data_type == "操作日志":
        return [(today - timedelta(days=i)).strftime("%Y_%m_%d.txt") for i in range(last_interval)]
    today = date.today()
    if data_type == "采集图像":
        return [(today - timedelta(days=i)).strftime("image_%Y%m%d.csv") for i in range(last_interval)]

# 发送单个文件
def send_file_with_type(filepath, data_type):
    filename = os.path.basename(filepath)
    mime_type, _ = mimetypes.guess_type(filepath)
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (filename, f, mime_type)}
            data = {'type': data_type}
            response = requests.post(API_URL, files=files, data=data, timeout=15)
            
            if response.status_code == 200:
                print(f"✓ 成功上传文件: {filename}")
            else:
                print(f"✗ 上传失败: 状态码 {response.status_code}, 信息: {response.text}")
    except Exception as e:
        print(f"✗ 上传文件异常: {e}")

def send_sensor_data():
    data_type = "传感器数据"
    filenames = get_last_data(data_type,last_interval)
    for filename in filenames:
        filepath = os.path.join(SENSOR_DATA_DIR, filename)
        if os.path.exists(filepath):
            send_file_with_type(filepath, "传感器数据")
        else:
            print(f"⚠ 文件不存在: {filename}")

def send_operation_log_data():
    data_type = "操作日志"
    filenames = get_last_data(data_type,last_interval)
    for filename in filenames:
        filepath = os.path.join(OPREATION_LOGS_DIR, filename)
        if os.path.exists(filepath):
            send_file_with_type(filepath, "操作日志")
        else:
            print(f"⚠ 文件不存在: {filename}")

if __name__ == "__main__":
    send_sensor_data()
    send_operation_log_data()
