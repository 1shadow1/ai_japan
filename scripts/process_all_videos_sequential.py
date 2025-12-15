#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
顺序处理 logs/videos 下的全部视频：抽帧 -> 批量上传 -> 等待检测结果 -> 再处理下一个
使用方法：
    python scripts/process_all_videos_sequential.py
可选：
    指定目录/抽帧间隔/摄像头ID可在此脚本中修改默认值
"""

import sys
from pathlib import Path

# 保证项目根目录在模块搜索路径中
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config.config_manager import config_manager
from scripts.batch_video_processor import BatchVideoProcessor


def main():
    # 从配置读取默认视频目录与抽帧间隔
    videos_dir = config_manager.get_path('camera_video_dir', './logs/videos')
    extract_interval = config_manager.get('cameras.extract_interval_seconds', 1.0)

    # 如需覆盖默认目录或间隔，可在此修改：
    # videos_dir = './logs/videos'
    # extract_interval = 1.0

    # 使用默认输出目录，与 batch_video_processor 一致
    output_dir = None
    camera_id = None  # 默认从文件名推断

    processor = BatchVideoProcessor(
        videos_dir=videos_dir,
        extract_interval=extract_interval,
        output_dir=output_dir,
        camera_id=camera_id,
    )

    stats = processor.process_all()

    # 根据统计信息设置退出码
    if stats.get('failed_videos', 0) > 0:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()