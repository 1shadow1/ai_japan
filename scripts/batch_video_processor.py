#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量视频处理脚本
功能：
1. 扫描 videos 文件夹下的所有视频文件
2. 对每个视频进行抽帧
3. 生成批量图片和文件夹
4. 发送请求到服务端进行 YOLO 检测
5. 完成整个流程

使用方法：
    python scripts/batch_video_processor.py [--videos-dir <视频目录>] [--extract-interval <抽帧间隔秒数>] [--camera-id <摄像头ID>]
"""

import os
import sys
import cv2
import argparse
import logging
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_manager import config_manager
from src.services.batch_image_client import send_batch_images_for_detection

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/batch_video_processor.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class BatchVideoProcessor:
    """批量视频处理器"""
    
    def __init__(
        self,
        videos_dir: str,
        extract_interval: float = 1.0,
        output_dir: Optional[str] = None,
        camera_id: Optional[int] = None
    ):
        """
        初始化批量视频处理器
        
        Args:
            videos_dir: 视频文件目录
            extract_interval: 抽帧间隔（秒）
            output_dir: 输出目录，如果为 None 则使用配置中的路径
            camera_id: 摄像头ID，如果为 None 则从视频文件名推断
        """
        self.videos_dir = Path(videos_dir)
        self.extract_interval = extract_interval
        
        if output_dir:
            self.output_dir = Path(output_dir)
        else:
            self.output_dir = Path(config_manager.get_path('camera_extract_dir', './output'))
        
        self.camera_id = camera_id
        self.batch_id = config_manager.get_batch_id()
        self.pool_id = config_manager.get_pool_id()
        
        # 支持的视频格式
        self.video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.m4v'}
        
        # 统计信息
        self.stats = {
            'total_videos': 0,
            'processed_videos': 0,
            'failed_videos': 0,
            'total_images': 0,
            'successful_detections': 0,
            'failed_detections': 0
        }
    
    def find_video_files(self) -> List[Path]:
        """
        查找所有视频文件
        
        Returns:
            视频文件路径列表
        """
        video_files = []
        
        if not self.videos_dir.exists():
            logger.error(f"视频目录不存在: {self.videos_dir}")
            return video_files
        
        logger.info(f"扫描视频目录: {self.videos_dir}")
        
        for file_path in self.videos_dir.iterdir():
            if file_path.is_file() and file_path.suffix.lower() in self.video_extensions:
                video_files.append(file_path)
                logger.debug(f"找到视频文件: {file_path.name}")
        
        video_files.sort()  # 按文件名排序
        logger.info(f"共找到 {len(video_files)} 个视频文件")
        self.stats['total_videos'] = len(video_files)
        
        return video_files
    
    def extract_frames_from_video(
        self,
        video_path: Path,
        camera_id: Optional[int] = None
    ) -> Dict[str, any]:
        """
        从视频中抽帧
        
        Args:
            video_path: 视频文件路径
            camera_id: 摄像头ID，如果为 None 则从文件名推断
            
        Returns:
            包含图片路径列表和元数据的字典
        """
        if cv2 is None:
            logger.error("OpenCV 不可用，无法抽帧")
            return {'images': [], 'error': 'OpenCV not available'}
        
        # 从文件名推断摄像头ID（如果未提供）
        if camera_id is None:
            camera_id = self._extract_camera_id_from_filename(video_path)
        
        video_name = video_path.stem  # 不含扩展名的文件名
        timestamp = int(datetime.now().timestamp())
        output_folder = self.output_dir / f"{video_name}_{timestamp}"
        output_folder.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"开始抽帧: {video_path.name} -> {output_folder}")
        
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            error_msg = f"无法打开视频文件: {video_path}"
            logger.error(error_msg)
            return {'images': [], 'error': error_msg}
        
        fps = cap.get(cv2.CAP_PROP_FPS) or 0.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        duration_sec = (total_frames / fps) if fps > 0 else 0.0
        
        logger.info(f"视频信息: 时长={duration_sec:.2f}秒, 帧率={fps:.2f}fps, 总帧数={total_frames}")
        
        if fps <= 0:
            logger.warning("FPS 无效，使用退化方式：每帧都保存")
            frame_interval = 1
        else:
            frame_interval = max(int(fps * self.extract_interval), 1)
        
        frame_count = 0
        saved_images = []
        
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % frame_interval == 0:
                    image_filename = output_folder / f"frame_{len(saved_images):04d}.jpg"
                    try:
                        cv2.imwrite(str(image_filename), frame)
                        height, width = frame.shape[:2]
                        saved_images.append({
                            'path': str(image_filename),
                            'width': width,
                            'height': height
                        })
                    except Exception as e:
                        logger.error(f"保存帧失败 {image_filename}: {e}")
                
                frame_count += 1
        finally:
            cap.release()
        
        logger.info(f"抽帧完成: 共保存 {len(saved_images)} 张图片到 {output_folder}")
        
        return {
            'images': saved_images,
            'camera_id': camera_id,
            'video_path': str(video_path),
            'output_folder': str(output_folder),
            'frame_count': len(saved_images),
            'duration_sec': duration_sec,
            'fps': fps
        }
    
    def _extract_camera_id_from_filename(self, video_path: Path) -> int:
        """
        从文件名中提取摄像头ID
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            摄像头ID，如果无法提取则返回默认值 1
        """
        filename = video_path.stem.lower()
        
        # 尝试从文件名中提取摄像头ID
        # 例如: camera_1_xxx.mp4, cam1_xxx.mp4, 1_xxx.mp4
        import re
        
        patterns = [
            r'camera[_\s]*(\d+)',
            r'cam[_\s]*(\d+)',
            r'^(\d+)[_\s]',
            r'[_\s](\d+)[_\s]',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    continue
        
        # 如果无法提取，尝试从配置中获取第一个摄像头ID
        try:
            cameras = config_manager.get('cameras.devices', [])
            if cameras:
                return cameras[0].get('camera_id', 1)
        except Exception:
            pass
        
        logger.warning(f"无法从文件名提取摄像头ID: {video_path.name}，使用默认值 1")
        return 1
    
    def upload_and_detect(self, image_paths: List[str], camera_id: int) -> Dict[str, any]:
        """
        上传图片并触发检测
        
        Args:
            image_paths: 图片路径列表
            camera_id: 摄像头ID
            
        Returns:
            检测结果
        """
        if not image_paths:
            logger.warning("图片列表为空，跳过上传")
            return {'success': False, 'error': 'No images to upload'}
        
        logger.info(f"开始上传 {len(image_paths)} 张图片进行检测...")
        
        try:
            result = send_batch_images_for_detection(
                camera_id=camera_id,
                image_paths=image_paths,
                batch_id=self.batch_id,
                pool_id=self.pool_id,
                save_results=False  # 不保存检测结果图，节省空间
            )
            
            if result.get('success'):
                data = result.get('data', {})
                total_live = data.get('total_live', 0)
                total_dead = data.get('total_dead', 0)
                logger.info(f"检测完成: 活虾={total_live}只, 死虾={total_dead}只")
                self.stats['successful_detections'] += 1
                self.stats['total_images'] += len(image_paths)
                return result
            else:
                error_msg = result.get('error', 'Unknown error')
                logger.error(f"检测失败: {error_msg}")
                self.stats['failed_detections'] += 1
                return result
                
        except Exception as e:
            logger.error(f"上传/检测异常: {e}", exc_info=True)
            self.stats['failed_detections'] += 1
            return {'success': False, 'error': str(e)}
    
    def process_video(self, video_path: Path) -> bool:
        """
        处理单个视频：抽帧 -> 上传 -> 检测
        
        Args:
            video_path: 视频文件路径
            
        Returns:
            是否处理成功
        """
        logger.info(f"\n{'='*60}")
        logger.info(f"处理视频: {video_path.name}")
        logger.info(f"{'='*60}")
        
        try:
            # 1. 抽帧
            extract_result = self.extract_frames_from_video(video_path, self.camera_id)
            
            if extract_result.get('error'):
                logger.error(f"抽帧失败: {extract_result['error']}")
                self.stats['failed_videos'] += 1
                return False
            
            images = extract_result.get('images', [])
            if not images:
                logger.warning("未提取到任何图片，跳过")
                self.stats['failed_videos'] += 1
                return False
            
            camera_id = extract_result.get('camera_id', self.camera_id or 1)
            
            # 2. 上传并检测
            image_paths = [img['path'] for img in images]
            detect_result = self.upload_and_detect(image_paths, camera_id)
            
            if detect_result.get('success'):
                logger.info(f"✓ 视频处理完成: {video_path.name}")
                self.stats['processed_videos'] += 1
                return True
            else:
                logger.error(f"✗ 视频处理失败: {video_path.name} - {detect_result.get('error', 'Unknown error')}")
                self.stats['failed_videos'] += 1
                return False
                
        except Exception as e:
            logger.error(f"处理视频异常: {video_path.name} - {e}", exc_info=True)
            self.stats['failed_videos'] += 1
            return False
    
    def process_all(self) -> Dict[str, int]:
        """
        处理所有视频
        
        Returns:
            统计信息字典
        """
        logger.info("="*60)
        logger.info("开始批量处理视频")
        logger.info("="*60)
        
        video_files = self.find_video_files()
        
        if not video_files:
            logger.warning("未找到任何视频文件")
            return self.stats
        
        for i, video_path in enumerate(video_files, 1):
            logger.info(f"\n进度: [{i}/{len(video_files)}]")
            self.process_video(video_path)
        
        # 打印统计信息
        logger.info("\n" + "="*60)
        logger.info("批量处理完成")
        logger.info("="*60)
        logger.info(f"总视频数: {self.stats['total_videos']}")
        logger.info(f"成功处理: {self.stats['processed_videos']}")
        logger.info(f"处理失败: {self.stats['failed_videos']}")
        logger.info(f"总图片数: {self.stats['total_images']}")
        logger.info(f"成功检测: {self.stats['successful_detections']}")
        logger.info(f"失败检测: {self.stats['failed_detections']}")
        logger.info("="*60)
        
        return self.stats


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description='批量视频处理脚本 - 抽帧、上传、检测',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 处理默认目录下的所有视频
  python scripts/batch_video_processor.py
  
  # 指定视频目录和抽帧间隔
  python scripts/batch_video_processor.py --videos-dir ./logs/videos --extract-interval 2
  
  # 指定摄像头ID
  python scripts/batch_video_processor.py --camera-id 3
        """
    )
    
    parser.add_argument(
        '--videos-dir',
        type=str,
        default=None,
        help='视频文件目录（默认: 从配置读取 camera_video_dir）'
    )
    
    parser.add_argument(
        '--extract-interval',
        type=float,
        default=None,
        help='抽帧间隔（秒，默认: 从配置读取 extract_interval_seconds）'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='输出目录（默认: 从配置读取 camera_extract_dir）'
    )
    
    parser.add_argument(
        '--camera-id',
        type=int,
        default=None,
        help='摄像头ID（默认: 从文件名推断）'
    )
    
    args = parser.parse_args()
    
    # 从配置获取默认值
    if args.videos_dir is None:
        args.videos_dir = config_manager.get_path('camera_video_dir', './logs/videos')
    
    if args.extract_interval is None:
        args.extract_interval = config_manager.get('cameras.extract_interval_seconds', 1.0)
    
    # 创建处理器并执行
    processor = BatchVideoProcessor(
        videos_dir=args.videos_dir,
        extract_interval=args.extract_interval,
        output_dir=args.output_dir,
        camera_id=args.camera_id
    )
    
    try:
        stats = processor.process_all()
        
        # 根据结果设置退出码
        if stats['failed_videos'] > 0:
            sys.exit(1)
        else:
            sys.exit(0)
            
    except KeyboardInterrupt:
        logger.info("\n用户中断，退出...")
        sys.exit(130)
    except Exception as e:
        logger.error(f"程序异常: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()

