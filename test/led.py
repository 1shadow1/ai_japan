import serial
import time

# 连接到 ESP32-C3
ser = serial.Serial("COM26", 115200, timeout=1)

time.sleep(2)  # 等待板子复位

# while True:
ser.write(b"LED_ON\n")
print("Send: LED_ON")
time.sleep(1)

ser.write(b"LED_OFF\n")
print("Send: LED_OFF")
time.sleep(1)
