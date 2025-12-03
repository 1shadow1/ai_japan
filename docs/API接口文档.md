# AI Japan 客户端 API 接口文档

**版本：** v2.0  
**更新日期：** 2025-01-XX  
**服务端地址：** `http://8.216.33.92:5000`

---

## 目录

1. [概述](#概述)
2. [认证与配置](#认证与配置)
3. [传感器数据接口](#传感器数据接口)
4. [喂食机数据接口](#喂食机数据接口)
5. [操作日志接口](#操作日志接口)
6. [摄像头数据接口](#摄像头数据接口)
7. [摄像头状态接口](#摄像头状态接口)
8. [错误处理](#错误处理)

---

## 概述

本文档描述了 `ai_japan` 客户端与服务端之间的API接口规范。所有接口均基于HTTP/HTTPS协议，使用JSON格式进行数据交换。

### 基础URL

```
http://8.216.33.92:5000
```

### 通用请求头

```
Content-Type: application/json
```

### 通用响应格式

**成功响应：**
```json
{
  "success": true,
  "data": {
    "id": 123,
    ...
  },
  "timestamp": 1704067200000
}
```

**失败响应：**
```json
{
  "success": false,
  "error": "错误描述信息",
  "timestamp": 1704067200000
}
```

---

## 认证与配置

### 配置管理

客户端使用配置文件 `config/client_config.json` 管理所有配置项，包括：

- **站点信息**：`pool_id`, `batch_id`, `location`, `timezone`
- **设备配置**：传感器、摄像头、喂食机的详细配置
- **API配置**：服务端地址、端点路径、超时设置等
- **任务配置**：采样频率、上传间隔等

### 环境变量覆盖

部分配置可通过环境变量覆盖：

- `AIJ_SENSOR_SIMULATE=1` - 启用传感器模拟模式
- `AIJ_UPLOAD_DRY_RUN=1` - 启用上传干运行模式
- `AIJ_CAMERA_UPLOAD_DRY_RUN=1` - 启用摄像头上传干运行模式
- `AIJ_CONFIG_PATH=/path/to/config.json` - 指定配置文件路径

---

## 传感器数据接口

### POST /api/data/sensors

**功能：** 上传传感器数据到服务端

**请求体：**
```json
{
  "sensor_id": 1,
  "batch_id": 2,
  "pool_id": "4",
  "value": 25.5,
  "metric": "temperature",
  "unit": "°C",
  "timestamp": 1704067200000,
  "type_name": "温度传感器",
  "description": "1号池温度"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sensor_id` | int | 是 | 传感器设备ID |
| `value` | float | 是 | 传感器数值 |
| `metric` | string | 是 | 指标名称（如：temperature, ph, do, turbidity等） |
| `unit` | string | 是 | 计量单位（如：°C, pH, mg/L, NTU等） |
| `batch_id` | int | 否 | 批次ID（默认从配置读取） |
| `pool_id` | string | 否 | 池号/分区标识（默认从配置读取） |
| `timestamp` | int | 否 | Unix时间戳（毫秒），不提供则使用当前时间 |
| `type_name` | string | 否 | 传感器类型名称 |
| `description` | string | 否 | 描述信息 |

**响应示例：**
```json
{
  "success": true,
  "data": {
    "id": 12345,
    "sensor_id": 1,
    "value": 25.5,
    "quality_flag": "ok"
  },
  "timestamp": 1704067200000
}
```

**状态码：**
- `201` - 创建成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**使用示例（Python）：**
```python
from src.services.api_client import api_client

# 发送传感器数据
response = api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C",
    timestamp=1704067200000,
    type_name="温度传感器",
    description="1号池温度"
)
```

---

## 喂食机数据接口

### POST /api/data/feeders

**功能：** 上传喂食机操作记录

**请求体：**
```json
{
  "feeder_id": "AI",
  "batch_id": 2,
  "pool_id": "4",
  "feed_amount_g": 500.0,
  "run_time_s": 120,
  "status": "ok",
  "leftover_estimate_g": 50.0,
  "timestamp": 1704067200000,
  "notes": "正常投喂"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `feeder_id` | string | 是 | 喂食机设备ID |
| `batch_id` | int | 否 | 批次ID（默认从配置读取） |
| `pool_id` | string | 否 | 池号/分区标识（默认从配置读取） |
| `feed_amount_g` | float | 否 | 投喂量（克） |
| `run_time_s` | int | 否 | 运行时长（秒） |
| `status` | string | 否 | 状态（ok/warning/error），默认"ok" |
| `leftover_estimate_g` | float | 否 | 剩余饵料估计（克） |
| `timestamp` | int | 否 | Unix时间戳（毫秒） |
| `notes` | string | 否 | 备注信息 |

**响应示例：**
```json
{
  "success": true,
  "data": {
    "id": 12346,
    "feeder_id": "AI",
    "status": "ok"
  },
  "timestamp": 1704067200000
}
```

**状态码：**
- `201` - 创建成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**使用示例（Python）：**
```python
from src.services.api_client import api_client

# 发送喂食机数据
response = api_client.send_feeder_data(
    feeder_id="AI",
    feed_amount_g=500.0,
    run_time_s=120,
    status="ok",
    leftover_estimate_g=50.0,
    notes="正常投喂"
)
```

---

## 操作日志接口

### POST /api/data/operations

**功能：** 上传操作日志记录

**请求体：**
```json
{
  "operator_id": "user001",
  "batch_id": 2,
  "pool_id": "4",
  "action_type": "投料",
  "remarks": "正常投喂操作",
  "attachment_uri": "s3://bucket/file.pdf",
  "timestamp": 1704067200000
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `operator_id` | string | 是 | 操作人ID |
| `action_type` | string | 是 | 操作类型（如：投料、水质调控、巡检、清洗等） |
| `batch_id` | int | 否 | 批次ID（默认从配置读取） |
| `pool_id` | string | 否 | 池号/分区标识（默认从配置读取） |
| `remarks` | string | 否 | 备注信息 |
| `attachment_uri` | string | 否 | 附件URI（如：图片、文档的存储路径） |
| `timestamp` | int | 否 | Unix时间戳（毫秒） |

**响应示例：**
```json
{
  "success": true,
  "data": {
    "id": 12347,
    "operator_id": "user001",
    "action_type": "投料"
  },
  "timestamp": 1704067200000
}
```

**状态码：**
- `201` - 创建成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**使用示例（Python）：**
```python
from src.services.api_client import api_client

# 发送操作日志
response = api_client.send_operation_data(
    operator_id="user001",
    action_type="投料",
    remarks="正常投喂操作",
    attachment_uri="s3://bucket/file.pdf"
)
```

---

## 摄像头数据接口

### POST /api/data/cameras

**功能：** 上传摄像头图像文件

**请求方式：** `multipart/form-data`

**请求参数：**

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | file | 是 | 图像文件（JPG/PNG格式） |
| `camera_id` | string | 是 | 摄像头ID |
| `batch_id` | string | 否 | 批次ID（默认从配置读取） |
| `pool_id` | string | 否 | 池号/分区标识（默认从配置读取） |
| `timestamp` | string | 否 | Unix时间戳（毫秒） |
| `width_px` | string | 否 | 图像宽度（像素） |
| `height_px` | string | 否 | 图像高度（像素） |
| `format` | string | 否 | 图像格式（jpg/png） |

**响应示例：**
```json
{
  "success": true,
  "data": {
    "id": 12348,
    "camera_id": 1,
    "storage_uri": "s3://bucket/image.jpg"
  },
  "timestamp": 1704067200000
}
```

**状态码：**
- `201` - 创建成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**使用示例（Python）：**
```python
from src.services.api_client import api_client

# 发送摄像头图像
response = api_client.send_camera_image(
    camera_id=1,
    image_path="/path/to/image.jpg",
    timestamp=1704067200000,
    width_px=1920,
    height_px=1080,
    format="jpg"
)
```

---

## 摄像头状态接口

### POST /api/camera_device_status

**功能：** 上报摄像头状态事件（录制开始/结束）

**请求体：**
```json
{
  "camera_index": 0,
  "event": "start_recording",
  "duration": 60,
  "fps": 30,
  "filename": "camera_0_1704067200.mp4",
  "timestamp": "2025-01-01T12:00:00"
}
```

**字段说明：**

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `camera_index` | int | 是 | 摄像头索引 |
| `event` | string | 是 | 事件类型（start_recording/finish_recording） |
| `duration` | int | 否 | 录制时长（秒） |
| `fps` | int | 否 | 帧率 |
| `filename` | string | 否 | 文件名 |
| `timestamp` | string | 否 | ISO格式时间戳 |

**响应示例：**
```json
{
  "success": true,
  "timestamp": 1704067200000
}
```

**状态码：**
- `200` - 成功
- `400` - 请求参数错误
- `500` - 服务器内部错误

**使用示例（Python）：**
```python
from src.services.api_client import api_client

# 发送摄像头状态
response = api_client.send_camera_status(
    camera_index=0,
    event="start_recording",
    duration=60,
    fps=30,
    filename="camera_0_1704067200.mp4"
)
```

---

## 错误处理

### 错误码说明

| 状态码 | 说明 | 处理建议 |
|--------|------|----------|
| `400` | 请求参数错误 | 检查请求体格式和必填字段 |
| `401` | 未授权 | 检查认证信息 |
| `404` | 接口不存在 | 检查接口路径是否正确 |
| `500` | 服务器内部错误 | 稍后重试或联系管理员 |

### 重试机制

客户端实现了自动重试机制：

- **默认重试次数：** 3次
- **重试间隔：** 2秒
- **可配置：** 通过配置文件 `api.retry_attempts` 和 `api.retry_delay_seconds` 调整

### 干运行模式

在开发和测试环境中，可以启用干运行模式，不会实际发送请求：

```bash
export AIJ_UPLOAD_DRY_RUN=1
```

或在配置文件中设置：
```json
{
  "simulation": {
    "upload_dry_run": true
  }
}
```

---

## 附录

### 支持的指标类型（metric）

| 指标名称 | 说明 | 单位示例 |
|---------|------|----------|
| `temperature` | 温度 | °C |
| `ph` | pH值 | pH |
| `do` | 溶解氧 | mg/L |
| `dissolved_oxygen` | 溶解氧（同do） | mg/L |
| `turbidity` | 浊度 | NTU |
| `water_level` | 水位 | mm, cm, m |
| `ammonia` | 氨氮 | mg/L |
| `nitrite` | 亚硝酸盐 | mg/L |

### 操作类型（action_type）

| 操作类型 | 说明 |
|---------|------|
| `投料` | 投喂饲料 |
| `水质调控` | 调整水质参数 |
| `巡检` | 日常巡检 |
| `清洗` | 清洗设备或池子 |
| `其他` | 其他操作 |

### 时间戳格式

- **Unix时间戳（毫秒）：** `1704067200000`
- **ISO格式：** `2025-01-01T12:00:00+09:00`

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX
