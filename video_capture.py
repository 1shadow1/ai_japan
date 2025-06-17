import cv2
import time
import os
from datetime import datetime
import subprocess

# 设置录制参数
duration_seconds = 10  # 录制时长（秒）
output_dir = os.path.join('.', 'output', 'origin_video')  # 保存目录

# 创建保存目录（如果不存在）
os.makedirs(output_dir, exist_ok=True)

# 获取当前日期作为文件名的一部分
date_str = datetime.now().strftime('%Y%m%d%H%m%S')
filename = f"{date_str}_{duration_seconds}.avi"
output_path = os.path.join(output_dir, filename)

# 打开摄像头
cap = cv2.VideoCapture(0)
if not cap.isOpened():
    print("无法打开摄像头")
    exit()

# 获取画面尺寸
frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

# 视频编码器与输出设置
fourcc = cv2.VideoWriter_fourcc(*'MJPG')
fps = cap.get(cv2.CAP_PROP_FPS)
if fps == 0 or fps is None:
    fps = 15.0  # 默认帧率

out = cv2.VideoWriter(output_path, fourcc, fps, (frame_width, frame_height))

# 检查 VideoWriter 是否成功打开
if not out.isOpened():
    print("无法打开 VideoWriter，检查编码器或文件路径")
    cap.release()
    cv2.destroyAllWindows()
    exit()

# 开灯命令
open_light_command = r'.\light\TestApp\CommandApp_USBRelay.exe HURTM open 01'

# 关灯命令
close_light_command = r'.\light\TestApp\CommandApp_USBRelay.exe HURTM close 01'

# 开灯
try:
    result = subprocess.run(open_light_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("命令执行成功：", result.stdout.decode('gbk'))  # ✅ GBK 解码
except subprocess.CalledProcessError as e:
    print("命令执行失败：", e.stderr.decode('gbk'))  # ✅ GBK 解码


print(f"开始录制，输出路径：{output_path}")

start_time = time.time()
while True:
    ret, frame = cap.read()
    if not ret:
        print("无法读取画面")
        break

    out.write(frame)
    cv2.imshow('Camera Recording', frame)

    if time.time() - start_time > duration_seconds or cv2.waitKey(1) & 0xFF == ord('q'):
        break

# 释放资源
cap.release()
out.release()
cv2.destroyAllWindows()
# 关灯
try:
    result = subprocess.run(close_light_command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("命令执行成功：", result.stdout.decode('gbk'))  # ✅ GBK 解码
except subprocess.CalledProcessError as e:
    print("命令执行失败：", e.stderr.decode('gbk'))  # ✅ GBK 解码


print("录制完成 ✅")
print(f"视频已保存为：{output_path}")
