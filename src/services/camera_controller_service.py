"""
CameraControllerService
后台持续运行的摄像头键盘监听与录制服务：
- 监听按键（默认 0~4），打开对应摄像头并录制固定时长视频，保存到指定目录；
- 录制开始/结束会向状态监控URL发送通知；
- 录制完成后按固定间隔抽帧生成图片，并将图片上传到指定URL；

改造说明：
- 使用配置管理模块（ConfigManager）
- 使用API客户端（ApiClient）发送数据
- 补充完整元数据（batch_id, pool_id等）
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

from src.config.config_manager import config_manager
from src.services.api_client import api_client


class CameraControllerService:
    def __init__(self):
        self.logger = logging.getLogger("CameraControllerService")
        
        # 从配置加载摄像头配置
        self.camera_configs = self._load_camera_configs()
        
        # 从配置获取参数
        camera_config = config_manager.get_camera_config()
        self.duration: int = camera_config.get('record_duration_seconds', 60)
        self.target_fps: int = camera_config.get('target_fps', 30)
        self.extract_interval: int = camera_config.get('extract_interval_seconds', 1)
        
        # 从配置获取路径
        paths_config = config_manager.get_paths_config()
        self.output_dir: str = paths_config.get('camera_video_dir', os.path.join("logs", "videos"))
        self.extract_output_root: str = paths_config.get('camera_extract_dir', "output")
        
        # 从配置获取API设置
        api_config = config_manager.get_api_config()
        self.upload_timeout: int = api_config.get('timeout_seconds', 15)
        self.upload_dry_run: bool = config_manager.is_camera_upload_dry_run()
        
        # 显示窗口（从环境变量读取，保持兼容性）
        show_env = os.getenv("AIJ_CAMERA_SHOW", "0").strip().lower()
        self.show_window: bool = show_env in ("1", "true", "yes", "on")

        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(self.extract_output_root, exist_ok=True)

        self._thread: Optional[threading.Thread] = None
        self._running: bool = False
        self._is_recording: bool = False

        if keyboard is None:
            self.logger.error("keyboard 库不可用，无法进行按键监听")
        if cv2 is None:
            self.logger.error("opencv-python 不可用，无法进行摄像头录制与抽帧")
    
    def _load_camera_configs(self) -> Dict[str, Dict]:
        """从配置加载摄像头配置，构建按键到摄像头配置的映射"""
        camera_configs = {}
        devices = config_manager.get_camera_devices()
        
        for device in devices:
            key = device.get('key', str(device.get('index', 0)))
            camera_configs[key] = {
                'camera_id': device.get('camera_id'),
                'name': device.get('name', f"摄像头{device.get('camera_id', 0)}"),
                'index': device.get('index', 0),
                'pool_id': device.get('pool_id', config_manager.get_pool_id()),
                'batch_id': device.get('batch_id', config_manager.get_batch_id()),
            }
        
        return camera_configs

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
                    for key, cam_config in self.camera_configs.items():
                        try:
                            if keyboard.is_pressed(key):
                                camera_id = cam_config['camera_id']
                                cam_index = cam_config['index']
                                self.logger.info(f"按键 {key} 被按下，打开摄像头 {cam_index} (ID: {camera_id})")
                                self.record_camera(cam_config, self.duration, self.target_fps)
                        except Exception:
                            # keyboard 在某些环境下可能抛出异常，忽略本次检测
                            pass
                time.sleep(0.05)
            except Exception as e:
                self.logger.error(f"服务循环异常: {e}")
                time.sleep(0.2)

    def record_camera(self, cam_config: Dict, duration: int, target_fps: int) -> None:
        """录制摄像头视频"""
        self._is_recording = True
        camera_id = cam_config['camera_id']
        cam_index = cam_config['index']
        camera_name = cam_config['name']
        
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
            filename = f"camera_{camera_id}_{ts}.mp4"
            filepath = os.path.join(self.output_dir, filename)
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            out = cv2.VideoWriter(filepath, fourcc, target_fps, (frame_width, frame_height))

            # 发送开始录制状态
            try:
                api_client.send_camera_status(
                    camera_index=cam_index,
                    event="start_recording",
                    duration=duration,
                    fps=target_fps,
                    filename=filename
                )
            except Exception as e:
                self.logger.warning(f"发送开始录制状态失败: {e}")
            
            self.logger.info(f"开始录制摄像头 {cam_index} (ID: {camera_id})，严格时长 {duration} 秒，保存为 {filepath}")

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
                        cv2.imshow(f"Camera {camera_id}", frame)
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

            # 发送完成录制状态
            try:
                api_client.send_camera_status(
                    camera_index=cam_index,
                    event="finish_recording",
                    duration=duration,
                    fps=target_fps,
                    filename=filename
                )
            except Exception as e:
                self.logger.warning(f"发送完成录制状态失败: {e}")
            
            self.logger.info(f"录制完成，文件时长严格为 {duration} 秒，帧率 {target_fps}fps")

            # 抽帧并上传
            try:
                self.extract_and_upload(cam_config, filepath, self.extract_interval)
            except Exception as e:
                self.logger.error(f"抽帧/上传流程异常: {e}")

        finally:
            self._is_recording = False

    def extract_and_upload(self, cam_config: Dict, video_path: str, interval_sec: int) -> None:
        """从视频中抽帧并上传"""
        if cv2 is None:
            self.logger.error("OpenCV 不可用，无法抽帧")
            return
        
        camera_id = cam_config['camera_id']
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
        saved_paths: List[Dict[str, any]] = []  # 存储路径和元数据

        while True:
            ret, frame = cap.read()
            if not ret:
                break
            if frame_count % frame_interval == 0:
                image_filename = os.path.join(output_folder, f"{video_name}_{interval_sec}_frame_{len(saved_paths):04d}.jpg")
                try:
                    cv2.imwrite(image_filename, frame)
                    height, width = frame.shape[:2]
                    saved_paths.append({
                        'path': image_filename,
                        'width': width,
                        'height': height
                    })
                except Exception as e:
                    self.logger.error(f"保存帧失败 {image_filename}: {e}")
            frame_count += 1

        cap.release()
        self.logger.info(f"共保存了 {len(saved_paths)} 张图片至 {output_folder}")

        # 上传图片
        self._upload_images(cam_config, saved_paths)

    def _upload_images(self, cam_config: Dict, image_info_list: List[Dict]) -> None:
        """上传图片到服务端"""
        camera_id = cam_config['camera_id']
        
        for img_info in image_info_list:
            image_path = img_info['path']
            width = img_info.get('width')
            height = img_info.get('height')
            
            try:
                # 获取时间戳（毫秒）
                timestamp_ms = int(time.time() * 1000)
                
                # 使用API客户端上传
                api_client.send_camera_image(
                    camera_id=camera_id,
                    image_path=image_path,
                    timestamp=timestamp_ms,
                    width_px=width,
                    height_px=height,
                    format='jpg'
                )
                self.logger.info(f"上传成功: {image_path}")
            except Exception as e:
                self.logger.error(f"上传异常 {image_path}: {e}")
