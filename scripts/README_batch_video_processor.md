# 批量视频处理脚本使用说明

## 功能概述

`batch_video_processor.py` 是一个独立的批量视频处理脚本，能够自动完成以下完整流程：

1. **扫描视频文件** - 自动扫描指定目录下的所有视频文件
2. **视频抽帧** - 从每个视频中按指定间隔抽取帧图片
3. **生成图片文件夹** - 为每个视频创建独立的图片输出文件夹
4. **上传到服务端** - 将批量图片上传到服务端
5. **YOLO 目标检测** - 服务端自动运行 YOLO 检测
6. **保存统计结果** - 检测结果自动保存到数据库

## 使用方法

### 基本用法

```bash
# 处理默认目录下的所有视频（使用配置文件中的设置）
python scripts/batch_video_processor.py
```

### 高级用法

```bash
# 指定视频目录和抽帧间隔
python scripts/batch_video_processor.py --videos-dir ./logs/videos --extract-interval 2

# 指定摄像头ID
python scripts/batch_video_processor.py --camera-id 3

# 指定输出目录
python scripts/batch_video_processor.py --output-dir ./output/frames

# 组合使用
python scripts/batch_video_processor.py \
    --videos-dir ./logs/videos \
    --extract-interval 1.5 \
    --camera-id 2 \
    --output-dir ./output/frames
```

## 参数说明

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `--videos-dir` | 字符串 | 配置中的 `camera_video_dir` | 视频文件目录路径 |
| `--extract-interval` | 浮点数 | 配置中的 `extract_interval_seconds` | 抽帧间隔（秒） |
| `--output-dir` | 字符串 | 配置中的 `camera_extract_dir` | 图片输出目录 |
| `--camera-id` | 整数 | 从文件名推断 | 摄像头ID |

## 工作流程

### 1. 视频扫描
- 自动扫描指定目录下的所有视频文件
- 支持的格式：`.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.m4v`
- 按文件名排序处理

### 2. 视频抽帧
- 根据视频帧率和抽帧间隔计算需要保存的帧
- 为每个视频创建独立的输出文件夹：`{视频名}_{时间戳}/`
- 保存的图片命名格式：`frame_0000.jpg`, `frame_0001.jpg`, ...

### 3. 摄像头ID推断
如果未指定 `--camera-id`，脚本会尝试从文件名中提取：
- 匹配模式：`camera_1`, `cam1`, `1_xxx` 等
- 如果无法提取，使用配置中的第一个摄像头ID
- 如果配置中也没有，使用默认值 1

### 4. 批量上传和检测
- 将每个视频的所有抽帧图片打包上传
- 发送到服务端的 `/api/data/batch_images` 接口
- 服务端自动运行 YOLO 检测
- 检测结果自动保存到 `shrimp_stats` 表

### 5. 统计信息
处理完成后会显示：
- 总视频数
- 成功处理数
- 处理失败数
- 总图片数
- 成功检测数
- 失败检测数

## 输出示例

```
============================================================
开始批量处理视频
============================================================
扫描视频目录: ./logs/videos
共找到 5 个视频文件

进度: [1/5]
============================================================
处理视频: camera_1_20250101_120000.mp4
============================================================
开始抽帧: camera_1_20250101_120000.mp4 -> ./output/camera_1_20250101_120000_1704067200
视频信息: 时长=60.00秒, 帧率=30.00fps, 总帧数=1800
抽帧完成: 共保存 60 张图片到 ./output/camera_1_20250101_120000_1704067200
开始上传 60 张图片进行检测...
检测完成: 活虾=150只, 死虾=2只
✓ 视频处理完成: camera_1_20250101_120000.mp4

...

============================================================
批量处理完成
============================================================
总视频数: 5
成功处理: 5
处理失败: 0
总图片数: 300
成功检测: 5
失败检测: 0
============================================================
```

## 日志文件

脚本运行日志会保存到：
- `logs/batch_video_processor.log` - 文件日志
- 控制台输出 - 实时显示处理进度

## 配置说明

脚本使用项目配置文件 `config/client_config.json` 中的以下配置：

```json
{
  "cameras": {
    "extract_interval_seconds": 1,  // 抽帧间隔（秒）
    "devices": [...]                 // 摄像头设备列表
  },
  "paths": {
    "camera_video_dir": "./logs/videos",    // 视频目录
    "camera_extract_dir": "./output"        // 图片输出目录
  },
  "api": {
    "base_url": "http://8.216.33.92:5002",
    "endpoints": {
      "batch_images": "/api/data/batch_images"  // 批量图片接口
    }
  },
  "site": {
    "batch_id": 2,    // 默认批次ID
    "pool_id": "4"    // 默认池号
  }
}
```

## 注意事项

1. **依赖要求**
   - 需要安装 `opencv-python`：`pip install opencv-python`
   - 需要安装 `requests`：`pip install requests`

2. **服务端要求**
   - 服务端必须运行并可以访问
   - 服务端必须已配置 YOLO 检测服务
   - 服务端必须已实现 `/api/data/batch_images` 接口

3. **文件路径**
   - 确保视频目录存在且有读取权限
   - 确保输出目录有写入权限
   - 图片文件会占用磁盘空间，注意清理

4. **性能考虑**
   - 大量视频处理可能需要较长时间
   - 建议在服务器空闲时运行
   - 可以通过 Ctrl+C 中断处理

5. **错误处理**
   - 单个视频处理失败不会影响其他视频
   - 所有错误都会记录到日志文件
   - 处理完成后会显示失败统计

## 故障排查

### 问题：找不到视频文件
- 检查 `--videos-dir` 参数是否正确
- 检查视频文件格式是否支持
- 检查文件权限

### 问题：抽帧失败
- 检查视频文件是否损坏
- 检查 OpenCV 是否正确安装
- 查看日志文件获取详细错误信息

### 问题：上传失败
- 检查服务端是否运行
- 检查网络连接
- 检查 API 配置是否正确
- 查看日志文件获取详细错误信息

### 问题：检测失败
- 检查服务端 YOLO 服务是否正常
- 检查服务端模型文件是否存在
- 查看服务端日志

## 示例场景

### 场景1：处理新录制的视频
```bash
# 每天定时处理新录制的视频
python scripts/batch_video_processor.py --videos-dir ./logs/videos
```

### 场景2：批量处理历史视频
```bash
# 处理指定目录下的所有历史视频
python scripts/batch_video_processor.py \
    --videos-dir /path/to/historical/videos \
    --extract-interval 2 \
    --output-dir ./output/historical_frames
```

### 场景3：处理特定摄像头的视频
```bash
# 只处理摄像头3的视频
python scripts/batch_video_processor.py --camera-id 3
```

