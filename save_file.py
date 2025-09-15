import os
from  datetime import timedelta, date
import requests

# 配置保存文件路径
SENSOR_DATA_DIR = r"C:\Users\37897\Desktop\japan_data\sensor_data"      

# 生成最近7天的日期列表
def make_date():
    today = date.today()
    return today
    # return [(today - timedelta(days=i)).strftime("sensor_%Y%m%d.csv") for i in range(7)]

# 发送单个文件
def save_file_to_local(filepath):
    filename = os.path.basename(filepath)
    try:
        with open(filepath, 'rb') as f:
            files = {'file': (filename, f, 'text/csv')}
            response = requests.post(API_URL, files=files, timeout=15)
            if response.status_code == 200:
                print(f"✓ 成功发送文件: {filename}")
            else:
                print(f"✗ 发送失败: {filename}，状态码: {response.status_code}")
    except Exception as e:
        print(f"✗ 发送文件异常: {filename}，错误: {e}")

# 主执行逻辑
def send_last_7_days_files():
    filenames = get_last_7_days()
    for filename in filenames:
        filepath = os.path.join(SENSOR_DATA_DIR, filename)
        if os.path.exists(filepath):
            send_file(filepath)
        else:
            print(f"⚠ 文件不存在: {filename}")

if __name__ == "__main__":
    send_last_7_days_files()
