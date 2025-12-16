#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量图片上传客户端
用于上传批量图片进行 YOLO 检测
"""

import os
import logging
from typing import List, Optional, Dict, Any

try:
    import requests
except ImportError:
    requests = None

from src.config.config_manager import config_manager
from src.services.api_client import api_client

logger = logging.getLogger(__name__)


def send_batch_images_for_detection(
    camera_id: int,
    image_paths: List[str],
    batch_id: Optional[int] = None,
    pool_id: Optional[str] = None,
    conf: Optional[float] = None,
    iou: Optional[float] = None,
    save_results: bool = False,
    source_video: Optional[str] = None
) -> Dict[str, Any]:
    """
    发送批量图片进行 YOLO 检测
    
    Args:
        camera_id: 摄像头ID
        image_paths: 图片文件路径列表
        batch_id: 批次ID，可选（默认从配置获取）
        pool_id: 池号，可选（默认从配置获取）
        conf: 置信度阈值，可选
        iou: IOU阈值，可选
        save_results: 是否保存检测结果图，可选
        
    Returns:
        响应数据（包含检测统计结果）
    """
    endpoint = config_manager.get_api_endpoint('batch_images')
    base_url = config_manager.get_api_base_url()
    timeout = config_manager.get('api.timeout_seconds', 15)
    dry_run = config_manager.is_upload_dry_run()
    
    if batch_id is None:
        batch_id = config_manager.get_batch_id()
    if pool_id is None:
        pool_id = config_manager.get_pool_id()
    
    # 检查文件是否存在
    valid_paths = []
    for img_path in image_paths:
        if os.path.exists(img_path):
            valid_paths.append(img_path)
        else:
            logger.warning(f"图片文件不存在，跳过: {img_path}")
    
    if not valid_paths:
        raise ValueError("没有有效的图片文件")
    
    # 构建URL
    url = endpoint if str(endpoint).startswith(("http://", "https://")) else f"{base_url.rstrip('/')}/{str(endpoint).lstrip('/')}"
    
    if dry_run:
        logger.info(f"[DRY-RUN] POST {url} (multipart) - {len(valid_paths)} 张图片")
        return {
            "success": True,
            "dry_run": True,
            "data": {"simulated": True, "total_live": 0, "total_dead": 0}
        }
    
    if requests is None:
        raise RuntimeError("requests 库未安装，无法发送请求")
    
    file_handles = []
    try:
        # 准备文件列表
        files = []
        for img_path in valid_paths:
            filename = os.path.basename(img_path)
            file_handle = open(img_path, 'rb')
            file_handles.append(file_handle)
            files.append(('files', (filename, file_handle, 'image/jpeg')))
        
        # 准备表单数据
        data = {
            'camera_id': str(camera_id),
            'batch_id': str(batch_id),
            'pool_id': pool_id,
            'save_results': 'true' if save_results else 'false',
        }
        
        if conf is not None:
            data['conf'] = str(conf)
        if iou is not None:
            data['iou'] = str(iou)
        # 新增：来源视频文件名
        if source_video:
            data['source_video'] = source_video
        
        # 发送请求
        session = requests.Session()
        response = session.post(
            url,
            files=files,
            data=data,
            timeout=timeout * max(1, len(valid_paths))  # 根据图片数量增加超时时间
        )
        
        # 关闭文件句柄
        for file_handle in file_handles:
            try:
                file_handle.close()
            except Exception:
                pass
        
        response.raise_for_status()
        return response.json()
        
    except requests.exceptions.RequestException as e:
        # 确保文件句柄被关闭
        for file_handle in file_handles:
            try:
                file_handle.close()
            except Exception:
                pass
        logger.error(f"批量图片上传失败: {url} - {e}")
        raise

