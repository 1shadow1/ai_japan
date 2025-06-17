# ⚠️运行前安装依赖
# pip install pymodbus pandas


import pandas as pd
from pymodbus.client.serial import ModbusSerialClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
import struct
import time
from datetime import datetime
import os

# 串口配置
client = ModbusClient(
    port='COM9',         #替换为你电脑的串口号，如 COM4 或 /dev/ttyUSB0
    baudrate=4800,
    stopbits=1,
    bytesize=8,
    parity='N',
    timeout=1
)

# 日志文件路径
csv_file = "dissolved_oxygen_log.csv"

# 检查文件是否存在，用于写入表头
file_exists = os.path.exists(csv_file)

# 连接串口
if not client.connect():
    print("串口连接失败，请检查设备和端口配置！")
    exit()

print("开始采集数据，按 Ctrl+C 停止...")

try:
    while True:
        rr = client.read_holding_registers(0x0002, count=2, slave=0x03)

        if not rr.isError():
            # decoder = BinaryPayloadDecoder.fromRegisters(rr.registers, byteorder=Endian.BIG, wordorder=Endian.BIG)
            # oxygen_saturation = decoder.decode_32bit_float()


            registers = rr.registers
            raw = (registers[0] << 16) | registers[1]
            # oxygen_saturation = struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0]
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)



            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            # 打印当前读数
            print(f"[{timestamp}] 溶解氧饱和度: {oxygen_saturation:.2f}  ")
            # print(f"[{timestamp}] 溶解氧饱和度: {Dissolved_oxygen_saturation:.2f}  , 温度: {temperature:.2f} °C")

            # 写入CSV
            df = pd.DataFrame([[timestamp, oxygen_saturation]],
                              columns=["时间", "溶解氧饱和度"])
            # df = pd.DataFrame([[timestamp, Dissolved_oxygen_saturation, temperature]],
            #                   columns=["时间", "溶解氧饱和度 ", "温度(°C)"])
            df.to_csv(csv_file, mode='a', header=not file_exists, index=False)
            file_exists = True
        else:
            print("读取失败：", rr)

        time.sleep(10)  # 每10秒采集一次

except KeyboardInterrupt:
    print("\n采集结束，串口关闭。")

finally:
    client.close()
