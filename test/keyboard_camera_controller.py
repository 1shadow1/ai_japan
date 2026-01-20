# keyboard_camera_controller.py

import keyboard
import cv2
import time
import numpy as np
from typing import Dict


class KeyboardCameraController:
    """
    键盘控制摄像头显示并录制固定时长视频（严格保证时长）
    """
    def __init__(self, key_to_camera: Dict[str, int]):
        self.key_to_camera = key_to_camera
        self.is_recording = False  # 防重复触发标记

    def record_camera(self, cam_index: int, duration: int = 60, target_fps: int = 30) -> None:
        """
        打开摄像头并录制指定时长视频（严格保证时长）
        """
        self.is_recording = True  

        # 优先使用 DirectShow 后端（Windows）以提高分辨率设置的成功率
        cap = cv2.VideoCapture(cam_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            print(f"无法打开摄像头 {cam_index}")
            self.is_recording = False
            return

        # 强制设置为 1080P 分辨率
        target_width, target_height = 1920, 1080
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, target_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, target_height)
        # 在采集环节尝试设置 MJPG，有助于部分摄像头打开高分辨率
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        # 读取实际生效的分辨率（有些设备可能不支持 1080P，会回退）
        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or target_width
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or target_height
        if frame_width != target_width or frame_height != target_height:
            print(f"警告: 摄像头未能切换到 1080P，实际分辨率为 {frame_width}x{frame_height}")

        output_filename = f"camera_{cam_index}_{int(time.time())}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_filename, fourcc, target_fps, (target_width, target_height))

        print(f"开始录制摄像头 {cam_index}，严格时长 {duration} 秒，保存为 {output_filename}")

        total_frames = duration * target_fps
        last_frame = None

        for i in range(total_frames):
            ret, frame = cap.read()
            if ret:
                last_frame = frame
            elif last_frame is not None:
                frame = last_frame
            else:
                # 如果一开始就没有帧，用黑屏填充
                frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)

            # 若采集分辨率与目标分辨率不一致，统一缩放到 1080P 后再写入
            if frame.shape[1] != target_width or frame.shape[0] != target_height:
                frame = cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_LINEAR)
            out.write(frame)
            cv2.imshow(f"Camera {cam_index}", frame)

            # 按 q 提前结束
            if cv2.waitKey(1) & 0xFF == ord('q'):
                print("提前结束录制")
                break

            # 控制录制节奏
            time.sleep(1 / target_fps)

        cap.release()
        out.release()
        cv2.destroyAllWindows()
        self.is_recording = False  

        print(f"录制完成，文件时长严格为 {duration} 秒，帧率 {target_fps}fps")

    def run(self) -> None:
        """
        持续监听键盘按键，根据映射打开对应摄像头并录制固定时长视频
        """
        print("键盘监听已启动，按对应按键打开摄像头并录制一分钟，按 ESC 退出程序")

        while True:
            if not self.is_recording:  # 只有在非录制状态下才允许触发
                for key, cam_index in self.key_to_camera.items():
                    if keyboard.is_pressed(key):
                        print(f"按键 {key} 被按下，打开摄像头 {cam_index}")
                        self.record_camera(cam_index, duration=30, target_fps=30)

            if keyboard.is_pressed('esc'):
                print("退出程序")
                break


if __name__ == "__main__":
    key_to_camera_map = {
        '0': 0,  # 按 0 打开摄像头 0
        '1': 1,  # 按 1 打开摄像头 1
        '2': 2,  # 按 2 打开摄像头 2
        '3': 3,  # 按 3 打开摄像头 3
        '4': 4,  # 按 4 打开摄像头 4
    }

    controller = KeyboardCameraController(key_to_camera_map)
    controller.run()


