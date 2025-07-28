import threading
import time
import pandas as pd
from datetime import datetime
from pymodbus.client.serial import ModbusSerialClient as ModbusClient
from pymodbus.payload import BinaryPayloadDecoder
from pymodbus.constants import Endian
import os
import struct
import requests
# 共享数据字典，存储各传感器最新数据
sensor_data = {
    'dissolved_oxygen': None,
    'liquid_level': None,
    'ph': None,
    'turbidity': None
}
data_lock = threading.Lock()

csv_file = "./output/sensor/data_collection.csv"
file_exists = os.path.exists(csv_file)

def read_dissolved_oxygen():
    client = ModbusClient(port='COM21', baudrate=4800, stopbits=1, bytesize=8, parity='N', timeout=1)
    if not client.connect():
        print("溶解氧串口连接失败")
        return
    while True:
        rr = client.read_holding_registers(0x0002, count=2, slave=0x01)
        if not rr.isError():
            registers = rr.registers
            raw = (registers[0] << 16) | registers[1]
            # oxygen_saturation = struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0]     
            oxygen_saturation = round(struct.unpack('>f', raw.to_bytes(4, byteorder='big'))[0], 5)
       
            with data_lock:
                sensor_data['dissolved_oxygen'] = oxygen_saturation
        else:
            print("溶解氧读取失败:", rr)
        time.sleep(10)

def read_liquid_level():
    client = ModbusClient(port='COM3', baudrate=4800, stopbits=1, bytesize=8, parity='N', timeout=1)
    if not client.connect():
        print("液位串口连接失败")
        return
    while True:
        rr = client.read_holding_registers(address=0x0004, count=1, slave=0x01)
        if not rr.isError():
            level_raw = rr.registers[0]
            with data_lock:
                sensor_data['liquid_level'] = level_raw
        else:
            print("液位读取失败:", rr)
        time.sleep(10)

def read_ph():
    client = ModbusClient(port='COM5', baudrate=4800, stopbits=1, bytesize=8, parity='N', timeout=1)
    if not client.connect():
        print("pH串口连接失败")
        return
    while True:
        rr = client.read_holding_registers(0x0000, count=2, slave=0x01)
        if not rr.isError():
            PH_raw = rr.registers[0]
            temperature_raw = rr.registers[1]
            PH = PH_raw / 100.0
            temperature = temperature_raw / 10.0
            with data_lock:
                sensor_data['ph'] = PH
                sensor_data['ph_temperature'] = temperature
        else:
            print("pH读取失败:", rr)
        time.sleep(10)

def read_turbidity():
    client = ModbusClient(port='COM6', baudrate=4800, stopbits=1, bytesize=8, parity='N', timeout=1)
    if not client.connect():
        print("浊度串口连接失败")
        return
    while True:
        rr = client.read_holding_registers(0x0000, count=2, slave=0x01)
        if not rr.isError():
            turbidity_raw = rr.registers[0]
            temperature_raw = rr.registers[1]
            turbidity = turbidity_raw / 10.0
            temperature = temperature_raw / 10.0
            with data_lock:
                sensor_data['turbidity'] = turbidity
                sensor_data['turbidity_temperature'] = temperature
        else:
            print("浊度读取失败:", rr)
        time.sleep(10)

def main():
    threads = []
    threads.append(threading.Thread(target=read_dissolved_oxygen, daemon=True))
    threads.append(threading.Thread(target=read_liquid_level, daemon=True))
    threads.append(threading.Thread(target=read_ph, daemon=True))
    threads.append(threading.Thread(target=read_turbidity, daemon=True))

    for t in threads:
        t.start()

    global file_exists
    print("开始采集数据，按 Ctrl+C 停止...")

    try:
        while True:
            with data_lock:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                do_val = sensor_data.get('dissolved_oxygen')
                level_val = sensor_data.get('liquid_level')
                ph_val = sensor_data.get('ph')
                ph_temp = sensor_data.get('ph_temperature')
                turbidity_val = sensor_data.get('turbidity')
                turbidity_temp = sensor_data.get('turbidity_temperature')

            # 跳过所有传感器数据为空的轮次
            if all(val is None for val in [do_val, level_val, ph_val, ph_temp, turbidity_val, turbidity_temp]):
                time.sleep(5)
                continue


            # 打印当前采集数据
            print(f"[{timestamp}] 溶解氧饱和度: {do_val if do_val is not None else 'N/A'}  "
                  f"液位: {level_val if level_val is not None else 'N/A'} mm  "
                  f"pH: {ph_val if ph_val is not None else 'N/A'}  温度(pH): {ph_temp if ph_temp is not None else 'N/A'} °C  "
                  f"浊度: {turbidity_val if turbidity_val is not None else 'N/A'} NTU  温度(浊度): {turbidity_temp if turbidity_temp is not None else 'N/A'} °C")

            # 记录数据到 CSV
            df = pd.DataFrame([[
                timestamp, do_val, level_val, ph_val, ph_temp, turbidity_val, turbidity_temp
            ]], columns=[
                "时间", "溶解氧饱和度", "液位(mm)", "PH", "PH温度(°C)", "浊度(NTU)", "浊度温度(°C)"
            ])
            df.to_csv(csv_file, mode='a', header=not file_exists, index=False)
            file_exists = True


            # 构造发送数据
            send_data = {
                "type": "传感器数据",
                "content": {
                    "时间": timestamp,
                    "溶解氧饱和度": do_val,
                    "液位(mm)": level_val,
                    "PH": ph_val,
                    "PH温度(°C)": ph_temp,
                    "浊度(NTU)": turbidity_val,
                    "浊度温度(°C)": turbidity_temp
                }
            }

            try:
                response = requests.post("http://8.216.33.92:5000/api/transfer_data", json=send_data)
                if response.status_code == 200:
                    print(f"数据已成功发送到接口:{response.content}")
                else:
                    print(f"发送失败，状态码: {response.status_code}")
            except Exception as e:
                print("发送数据异常:", e)


            time.sleep(5)

    except KeyboardInterrupt:
        print("\n采集结束，退出程序。")

if __name__ == "__main__":
    main()
