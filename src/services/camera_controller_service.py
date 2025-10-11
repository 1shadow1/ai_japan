"""
CameraControllerService
后台持续运行的摄像头键盘监听与录制服务：
- 监听按键（默认 0~4），打开对应摄像头并录制固定时长视频，保存到指定目录；
- 录制开始/结束会向状态监控URL发送通知；
- 录制完成后按固定间隔抽帧生成图片，并将图片上传到指定URL；

环境变量：
- AIJ_CAMERA_KEYS: 键位到摄像头索引映射，例如 "0:0,1:1,2:2,3:3,4:4"
- AIJ_CAMERA_RECORD_DURATION: 录制时长（秒），默认 60
- AIJ_CAMERA_RECORD_FPS: 目标帧率，默认 30
- AIJ_CAMERA_OUTPUT_DIR: 视频输出目录，默认 logs/videos
- AIJ_CAMERA_STATUS_URL: 状态通知URL，默认 http://8.216.33.92:5000/api/camera_device_status
- AIJ_EXTRACT_INTERVAL_SEC: 抽帧间隔秒，默认 1
- AIJ_EXTRACT_OUTPUT_DIR: 抽帧输出根目录，默认 output
- AIJ_CAMERA_UPLOAD_URL: 图片上传URL，默认 http://8.216.33.92:5000/api/updata_camera_data
- AIJ_CAMERA_UPLOAD_DRY_RUN: 设为 1/true 开启上传干跑（不实际POST）
- AIJ_CAMERA_SHOW: 设为 1/true 显示预览窗口（默认不显示）
"""

from __future__ import annotations

import os
import time
import logging
import threading
from datetime import datetime
from typing import Dict, List, Optional

try:
    import keyboard
except Exception:
    keyboard = None

try:
    import cv2
    import numpy as np
except Exception:
    cv2 = None
    np = None

try:
    import requests
except Exception:
    requests = None


class CameraControllerService:
    def __init__(self):
        self.logger = logging.getLogger("CameraControllerService")
        self.key_map: Dict[str, int] = self._parse_key_map(os.getenv("AIJ_CAMERA_KEYS", "0:0,1:1,2:2,3:3,4:4"))
        self.duration: int = self._get_int_env("AIJ_CAMERA_RECORD_DURATION", 60)
        self.target_fps: int = self._get_int_env("AIJ_CAMERA_RECORD_FPS", 30)
        self.output_dir: str = os.getenv("AIJ_CAMERA_OUTPUT_DIR", os.path.join("logs", "videos")).strip()
        self.status_url: str = os.getenv("AIJ_CAMERA_STATUS_URL", "http://8.216.33.92:5000/api/camera_device_status").strip()
        # 网络超时可配置，便于在退出时避免长时间阻塞
        self.status_timeout: int = self._get_int_env("AIJ_CAMERA_STATUS_TIMEOUT", 10)
        self.extract_interval: int = self._get_int_env("AIJ_EXTRACT_INTERVAL_SEC", 1)
        self.extract_output_root: str = os.getenv("AIJ_EXTRACT_OUTPUT_DIR", "output").strip()
        self.upload_url: str = os.getenv("AIJ_CAMERA_UPLOAD_URL", "http://8.216.33.92:5000/api/updata_camera_data").strip()
        self.upload_timeout: int = self._get_int_env("AIJ_CAMERA_UPLOAD_TIMEOUT", 15)
        self.upload_dry_run: bool = self._get_bool_env("AIJ_CAMERA_UPLOAD_DRY_RUN", False)
        self.show_window: bool = self._get_bool_env("AIJ_CAMERA_SHOW", False)

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.extract_output_root, exist_ok=True)

        self._session = requests.Session() if requests else None
        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._is_recording: bool = False

        if keyboard is None:
            self.logger.error("keyboard 库不可用，无法进行按键监听")
        if cv2 is None:
            self.logger.error("opencv-python 不可用，无法进行摄像头录制与抽帧")

    @staticmethod
    def _get_int_env(key: str, default_val: int) -> int:
        try:
            return int(os.getenv(key, str(default_val)))
        except Exception:
            return default_val

    @staticmethod
    def _get_bool_env(key: str, default_val: bool) -> bool:
        val = os.getenv(key, "" if default_val else "0").strip().lower()
        if val in ("1", "true", "yes", "on"):
            return True
        if val in ("0", "false", "no", "off"):
            return False
        return default_val

    @staticmethod
    def _parse_key_map(value: str) -> Dict[str, int]:
        mapping: Dict[str, int] = {}
        for part in (value or "").split(','):
            part = part.strip()
            if not part:
                continue
            if ':' in part:
                k, v = part.split(':', 1)
                k = k.strip()
                try:
                    mapping[k] = int(v.strip())
                except Exception:
                    pass
        return mapping

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run_loop, name="CameraControllerThread", daemon=True)
        self._thread.start()
        self.logger.info("CameraControllerService 已启动")

    def stop(self):
        # 停止循环
        self._running = False
        # 释放键盘钩子与窗口资源
        try:
            if keyboard:
                try:
                    keyboard.unhook_all_hotkeys()
                except Exception:
                    pass
                try:
                    keyboard.unhook_all()
                except Exception:
                    pass
            if self.show_window and cv2:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass
        except Exception as e:
            self.logger.warning(f"停止服务时释放资源异常: {e}")

        # 等待线程退出
        if self._thread:
            try:
                self._thread.join(timeout=3)
            except Exception:
                pass
        self.logger.info("CameraControllerService 已停止")

    def is_running(self) -> bool:
        return self._running

    def _run_loop(self):
        if keyboard is None or cv2 is None:
            self.logger.error("缺少必要依赖，退出摄像头服务循环")
            return
        self.logger.info("键盘监听已启动：按键触发摄像头录制；按 ESC 退出（仅窗口模式生效）")
        while self._running:
            try:
                if not self._is_recording:
                    for key, cam_index in self.key_map.items():
                        try:
                            if keyboard.is_pressed(key):
                                self.logger.info(f"按键 {key} 被按下，打开摄像头 {cam_index}")
                                self.record_camera(cam_index, self.duration, self.target_fps)
                        except Exception:
                            # keyboard 在某些环境下可能抛出异常，忽略本次检测
                            pass
                time.sleep(0.05)
            except Exception as e:
                self.logger.error(f"服务循环异常: {e}")
                time.sleep(0.2)

    def _post_json(self, url: str, payload: Dict) -> Optional[int]:
        if not requests or not self._session:
            self.logger.warning("requests 不可用，跳过网络请求")
            return None
        try:
            resp = self._session.post(url, json=payload, timeout=self.status_timeout)
            return resp.status_code
        except Exception as e:
            self.logger.error(f"POST {url} 失败: {e}")
            return None

    def record_camera(self, cam_index: int, duration: int, target_fps: int) -> None:
        self._is_recording = True
        try:
            if cv2 is None or np is None:
                self.logger.error("OpenCV/NumPy 不可用，无法录制")
                return
            cap = cv2.VideoCapture(cam_index)
            if not cap.isOpened():
                self.logger.error(f"无法打开摄像头 {cam_index}")
                return

            frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)) or 640
            frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)) or 480

            ts = int(time.time())
            filename = f"camera_{cam_index}_{ts}.mp4"
            filepath = os.path.join(self.output_dir, filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(filepath, fourcc, target_fps, (frame_width, frame_height))

            start_payload = {
                "camera_index": cam_index,
                "event": "start_recording",
                "duration": duration,
                "fps": target_fps,
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
            }
            self._post_json(self.status_url, start_payload)
            self.logger.info(f"开始录制摄像头 {cam_index}，严格时长 {duration} 秒，保存为 {filepath}")

            total_frames = int(duration * target_fps)
            last_frame = None

            for i in range(total_frames):
                # 支持 Ctrl+C 停止：若服务被要求停止，立刻结束录制循环
                if not self._running:
                    self.logger.info("收到停止信号，提前结束录制循环")
                    break
                ret, frame = cap.read()
                if ret:
                    last_frame = frame
                elif last_frame is not None:
                    frame = last_frame
                else:
                    frame = np.zeros((frame_height, frame_width, 3), dtype=np.uint8)

                out.write(frame)
                if self.show_window:
                    try:
                        cv2.imshow(f"Camera {cam_index}", frame)
                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            self.logger.info("收到 q，提前结束录制")
                            break
                    except Exception:
                        pass
                # 若服务已停止则不再等待
                if not self._running:
                    break
                time.sleep(1 / max(target_fps, 1))

            cap.release()
            out.release()
            if self.show_window:
                try:
                    cv2.destroyAllWindows()
                except Exception:
                    pass

            finish_payload = {
                "camera_index": cam_index,
                "event": "finish_recording",
                "duration": duration,
                "fps": target_fps,
                "filename": filename,
                "timestamp": datetime.now().isoformat(),
            }
            self._post_json(self.status_url, finish_payload)
            self.logger.info(f"录制完成，文件时长严格为 {duration} 秒，帧率 {target_fps}fps")

            # 抽帧并上传
            try:
                self.extract_and_upload(cam_index, filepath, self.extract_interval)
            except Exception as e:
                self.logger.error(f"抽帧/上传流程异常: {e}")

        finally:
            self._is_recording = False

    def extract_and_upload(self, cam_index: int, video_path: str, interval_sec: int) -> None:
        if cv2 is None:
            self.logger.error("OpenCV 不可用，无法抽帧")
            return
        video_name = os.path.splitext(os.path.basename(video_path))[0]
        output_folder = os.path.join(self.extract_output_root, f"{video_name}_{interval_sec}")
        os.makedirs(output_folder, exist_ok=True)

        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            self.logger.error(f"无法打开视频文件: {video_path}")
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_sec = (total_frames / fps) if fps > 0 else 0.0
        self.logger.info(f"视频时长: {duration_sec:.2f} 秒, 帧率: {fps:.2f} FPS, 总帧数: {total_frames}")

        if fps <= 0:
            self.logger.warning("FPS 无效，使用退化方式：每帧都保存")
            frame_interval = 1
        else:
            frame_interval = max(int(fps * interval_sec), 1)

        frame_count = 0
        saved_paths: List[str] = []

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_interval == 0:
                image_filename = os.path.join(output_folder, f"frame_{len(saved_paths):04d}.jpg")
                try:
                    cv2.imwrite(image_filename, frame)
                    saved_paths.append(image_filename)
                except Exception as e:
                    self.logger.error(f"保存帧失败 {image_filename}: {e}")
            frame_count += 1

        cap.release()
        self.logger.info(f"共保存了 {len(saved_paths)} 张图片至 {output_folder}")

        # 上传图片
        self._upload_images(cam_index, video_name, saved_paths)

    def _upload_images(self, cam_index: int, video_name: str, image_paths: List[str]) -> None:
        if self.upload_dry_run:
            self.logger.info(f"DRY-RUN: 跳过上传 {len(image_paths)} 张图片到 {self.upload_url}")
            return
        if not requests or not self._session:
            self.logger.warning("requests 不可用，无法上传图片")
            return
        for p in image_paths:
            try:
                with open(p, 'rb') as f:
                    files = {'file': (os.path.basename(p), f, 'image/jpeg')}
                    data = {
                        'camera_index': str(cam_index),
                        'video_name': video_name,
                        'timestamp': datetime.now().isoformat(),
                    }
                    resp = self._session.post(self.upload_url, files=files, data=data, timeout=self.upload_timeout)
                    if resp.status_code in (200, 201):
                        self.logger.info(f"上传成功: {p}")
                    else:
                        self.logger.warning(f"上传失败({resp.status_code}): {p} -> {resp.text[:200]}")
            except Exception as e:
                self.logger.error(f"上传异常 {p}: {e}")