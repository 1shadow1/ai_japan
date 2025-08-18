import cv2
from typing import List
import os


class Cameras:
    """
    摄像头管理类
    - 支持列出可用的摄像头索引
    - 支持打开并显示指定摄像头的画面
    """

    def __init__(self, cam_index: int = 0) -> None:
        """
        初始化摄像头对象

        Args:
            cam_index (int): 摄像头索引，默认为 0（通常是内置摄像头）
        """
        self.cam_index: int = cam_index
        self.cap: cv2.VideoCapture = cv2.VideoCapture(self.cam_index)

    @staticmethod
    def list_cameras(max_tested: int = 10) -> List[int]:
        """
        列出可用的摄像头索引

        Args:
            max_tested (int): 最大测试的摄像头索引范围（默认测试 0-9）

        Returns:
            List[int]: 可用摄像头索引列表
        """
        index_list: List[int] = []
        for i in range(max_tested):
            cap = cv2.VideoCapture(i)
            if cap.isOpened():
                index_list.append(i)
                cap.release()
        return index_list

    def show_camera(self) -> None:
        """
        打开并显示摄像头画面
        """
        if not self.cap.isOpened():
            print(f"无法打开摄像头 {self.cam_index}")
            return

        while True:
            # 读取一帧画面
            ret, frame = self.cap.read()
            if not ret:
                print("无法读取摄像头画面")
                break

            # 显示摄像头窗口
            cv2.imshow(f"Camera {self.cam_index}", frame)

            # 按 ESC 键退出
            if cv2.waitKey(1) & 0xFF == 27:
                break

        # 释放摄像头与窗口资源
        self.cap.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    # 列出可用摄像头
    print("可用摄像头索引:", Cameras.list_cameras())

    # 打开索引为 0 的摄像头并显示
    cam = Cameras(cam_index=0)
    cam.show_camera()
