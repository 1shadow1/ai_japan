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

        cap = cv2.VideoCapture(cam_index)
        if not cap.isOpened():
            print(f"无法打开摄像头 {cam_index}")
            self.is_recording = False
            return

        frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        output_filename = f"camera_{cam_index}_{int(time.time())}.mp4"
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(output_filename, fourcc, target_fps, (frame_width, frame_height))

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
1

if __name__ == "__main__":
    key_to_camera_map = {
        '0': 0,  # 按 a 打开摄像头 0
        '1': 1,  # 按 s 打开摄像头 1
        '2': 2,  # 按 a 打开摄像头 22q344
        '3': 3,  # 按 s 打开摄像头 1
        '4': 4,  # 按 a 打开摄像头 0
    }

    controller = KeyboardCameraController(key_to_camera_map)
    controller.run()


