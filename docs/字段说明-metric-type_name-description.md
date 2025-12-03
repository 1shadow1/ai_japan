# 字段说明：metric、type_name、description 的区别

## 三个字段的定位

### 1. `metric`（指标名称）- **数据标识层**

**定位：** 数据查询和聚合的标准化标识

**特点：**
- ✅ **必填字段**（用于数据存储和查询）
- 格式：英文小写，标准化（如：`do`, `ph`, `temperature`, `water_level`）
- 用于数据库索引和查询
- 用于异常值检测和数据分析
- 用于数据聚合和统计

**示例：**
```json
"metric": "do"           // 溶解氧指标
"metric": "ph"          // pH值指标
"metric": "temperature" // 温度指标
```

**在代码中的使用：**
```python
# 异常值检测
is_anomaly = DataCleaningService.detect_anomaly(value, metric, threshold)

# 数据查询（按metric分组）
readings = session.query(SensorReading).filter_by(metric="do").all()

# 数据聚合
SELECT metric, AVG(value) FROM sensor_readings GROUP BY metric
```

---

### 2. `type_name`（传感器类型名称）- **设备描述层**

**定位：** 传感器设备的类型名称，用于显示和说明

**特点：**
- ❌ **可选字段**
- 格式：中文或可读性名称（如：`"溶解氧传感器"`, `"pH传感器"`）
- 用于前端显示
- 用于日志记录
- 用于设备分类

**示例：**
```json
"type_name": "溶解氧传感器"
"type_name": "pH传感器"
"type_name": "液位传感器"
```

**在代码中的使用：**
```python
# 前端显示
<div>传感器类型：{reading.type_name}</div>

# 日志记录
logger.info(f"传感器数据：{type_name} - {value}")

# 设备分类
sensors_by_type = group_by(type_name)
```

---

### 3. `description`（描述信息）- **上下文说明层**

**定位：** 更详细的描述信息，包含位置、批次等上下文

**特点：**
- ❌ **可选字段**
- 格式：自由文本，可包含任意描述信息
- 用于详细说明和备注
- 用于记录具体位置、批次等上下文信息
- 用于问题排查和日志记录

**示例：**
```json
"description": "1号池温度"
"description": "4号池溶解氧 - 批次2"
"description": "东侧深水区pH值监测"
"description": "异常：读数波动较大，需检查设备"
```

**在代码中的使用：**
```python
# 详细说明
print(f"数据说明：{reading.description}")

# 问题排查
if "异常" in reading.description:
    alert_admin(reading)
```

---

## 三者的关系和使用场景

### 关系图

```
┌─────────────────────────────────────────┐
│  数据记录                               │
├─────────────────────────────────────────┤
│  metric: "do"                          │ ← 数据标识（必填）
│  type_name: "溶解氧传感器"              │ ← 设备描述（可选）
│  description: "4号池溶解氧 - 批次2"     │ ← 上下文说明（可选）
└─────────────────────────────────────────┘
```

### 使用场景对比

| 场景 | metric | type_name | description |
|------|--------|-----------|-------------|
| **数据查询** | ✅ 用于WHERE条件 | ❌ 不用于查询 | ❌ 不用于查询 |
| **数据聚合** | ✅ 用于GROUP BY | ❌ 不用于聚合 | ❌ 不用于聚合 |
| **异常检测** | ✅ 用于阈值判断 | ❌ 不使用 | ❌ 不使用 |
| **前端显示** | ⚠️ 可显示但不够友好 | ✅ 用于显示 | ✅ 用于详细说明 |
| **日志记录** | ✅ 用于日志 | ✅ 用于日志 | ✅ 用于详细日志 |
| **问题排查** | ⚠️ 可辅助 | ⚠️ 可辅助 | ✅ 包含详细上下文 |

---

## 实际使用示例

### 示例1：溶解氧传感器数据

```python
api_client.send_sensor_data(
    sensor_id=1,
    value=7.5,
    metric="do",                    # ← 指标名称（必填）：用于查询和分析
    unit="mg/L",
    type_name="溶解氧传感器",        # ← 设备类型（可选）：用于显示
    description="4号池溶解氧 - 批次2" # ← 详细描述（可选）：包含位置和批次信息
)
```

**存储到数据库后：**
- `metric="do"` → 可以查询所有溶解氧数据：`WHERE metric='do'`
- `type_name="溶解氧传感器"` → 前端显示："溶解氧传感器：7.5 mg/L"
- `description="4号池溶解氧 - 批次2"` → 日志记录："4号池溶解氧 - 批次2: 7.5 mg/L"

### 示例2：pH传感器数据（包含温度）

```python
# pH值
api_client.send_sensor_data(
    sensor_id=3,
    value=7.2,
    metric="ph",                    # ← 指标：ph
    unit="pH",
    type_name="pH传感器",            # ← 设备：pH传感器
    description="4号池pH值 - 批次2"  # ← 描述：包含位置和批次
)

# pH温度
api_client.send_sensor_data(
    sensor_id=3,
    value=25.5,
    metric="temperature",           # ← 指标：temperature（注意：不是ph）
    unit="°C",
    type_name="pH传感器",            # ← 设备：仍然是pH传感器（因为温度是pH传感器的附加测量）
    description="4号池pH传感器温度 - 批次2" # ← 描述：说明这是pH传感器的温度
)
```

---

## 是否重复？

### 结论：**不重复，各有用途**

虽然看起来有些重叠，但它们服务于不同的目的：

1. **metric** - **数据层**：用于数据查询、聚合、分析（技术层面）
2. **type_name** - **设备层**：用于设备分类和显示（用户层面）
3. **description** - **上下文层**：用于详细说明和备注（业务层面）

### 类比说明

可以类比为：
- **metric** = 商品SKU（标准化标识，用于库存管理）
- **type_name** = 商品名称（用户友好的名称，用于展示）
- **description** = 商品详情（包含规格、产地等详细信息）

---

## 建议的使用方式

### 在配置文件中

```json
{
  "sensor_id": 1,
  "name": "溶解氧传感器",        // ← 这个会作为 type_name
  "type": "dissolved_oxygen",     // ← 传感器类型（内部使用）
  "metric": "do",                 // ← 指标名称（必填）
  "unit": "mg/L"
}
```

### 在上传数据时

```python
# 从配置读取
device_config = config_manager.get_sensor_devices()[0]

api_client.send_sensor_data(
    sensor_id=device_config['sensor_id'],
    value=7.5,
    metric=device_config['metric'],           # ← 从配置读取
    unit=device_config['unit'],
    type_name=device_config['name'],           # ← 从配置读取（name字段）
    description=f"{device_config['pool_id']}号池{device_config['name']} - 批次{device_config['batch_id']}"  # ← 动态生成
)
```

---

## 总结

| 字段 | 层级 | 必填 | 用途 | 示例 |
|------|------|------|------|------|
| **metric** | 数据标识层 | ✅ 是 | 查询、聚合、分析 | `"do"`, `"ph"`, `"temperature"` |
| **type_name** | 设备描述层 | ❌ 否 | 显示、分类、日志 | `"溶解氧传感器"`, `"pH传感器"` |
| **description** | 上下文说明层 | ❌ 否 | 详细说明、备注 | `"4号池溶解氧 - 批次2"` |

**三者配合使用，提供完整的数据信息：**
- `metric` 确保数据可查询和分析
- `type_name` 提供用户友好的显示
- `description` 提供详细的上下文信息

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX
