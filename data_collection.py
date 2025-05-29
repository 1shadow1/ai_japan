# ⚠️运行前安装依赖
# pip install pymodbus pandas


import pandas as pd
from pymodbus.client.serial import ModbusSerialClient as ModbusClient
import time
from datetime import datetime
import os

# 串口配置
client = ModbusClient(
    method='rtu',
    port='COM3',         #替换为你电脑的串口号，如 COM4 或 /dev/ttyUSB0
    baudrate=4800,
    stopbits=1,
    bytesize=8,
    parity='N',
    timeout=1
)

# 日志文件路径
csv_file = "turbidity_log.csv"

# 检查文件是否存在，用于写入表头
file_exists = os.path.exists(csv_file)

# 连接串口
if not client.connect():
    print("串口连接失败，请检查设备和端口配置！")
    exit()

print("开始采集数据，按 Ctrl+C 停止...")

try:
    while True:
        rr = client.read_holding_registers(0x0000, 2, unit=0x01)

        if not rr.isError():
            turbidity_raw = rr.registers[0]
            temperature_raw = rr.registers[1]

            # 数值解析（放大10倍或100倍视量程而定，此处以10倍为例）
            turbidity = turbidity_raw / 10.0
            temperature = temperature_raw / 10.0
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 打印当前读数
            print(f"[{timestamp}] 浊度: {turbidity:.2f} NTU, 温度: {temperature:.2f} °C")

            # 写入CSV
            df = pd.DataFrame([[timestamp, turbidity, temperature]],
                              columns=["时间", "浊度(NTU)", "温度(°C)"])
            df.to_csv(csv_file, mode='a', header=not file_exists, index=False)
            file_exists = True
        else:
            print("读取失败：", rr)

        time.sleep(10)  # 每10秒采集一次

except KeyboardInterrupt:
    print("\n采集结束，串口关闭。")

finally:
    client.close()
