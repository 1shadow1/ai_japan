# ⚠️运行前安装依赖
# pip install pymodbus pandas

import pandas as pd
from pymodbus.client.serial import ModbusSerialClient as ModbusClient
import time
from datetime import datetime
import os

# 串口配置
client = ModbusClient(
    port='COM8',         
    baudrate=4800,
    stopbits=1,
    bytesize=8,
    parity='N',
    timeout=1
)

# 日志文件路径
csv_file = "liquid_level_log.csv"

# 检查文件是否存在，用于写入表头
file_exists = os.path.exists(csv_file)

# 连接串口
if not client.connect():
    print("串口连接失败，请检查设备和端口配置！")
    exit()

print("开始采集液位数据，按 Ctrl+C 停止...")

try:
    while True:
        # 液位输出值寄存器地址为 0x0004，读取1个寄存器
        rr = client.read_holding_registers(address=0x0004, count=1, slave=0x01)

        if not rr.isError():
            level_raw = rr.registers[0]
            # 直接读取单位为 mm（默认设置）
            liquid_level = level_raw
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 打印当前读数
            print(f"[{timestamp}] 液位: {liquid_level} mm")

            # 写入CSV
            df = pd.DataFrame([[timestamp, liquid_level]],
                              columns=["时间", "液位(mm)"])
            df.to_csv(csv_file, mode='a', header=not file_exists, index=False)
            file_exists = True
        else:
            print("读取失败：", rr)

        time.sleep(10)  # 每10秒采集一次

except KeyboardInterrupt:
    print("\n采集结束，串口关闭。")

finally:
    client.close()
