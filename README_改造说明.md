# AI Japan 项目改造说明

**改造日期：** 2025-01-XX  
**改造版本：** v2.0

---

## 改造目标

1. ✅ 符合工程化标准，提供接口文档
2. ✅ 符合文档中的数据传输请求规范
3. ✅ 统一配置管理，移除硬编码值
4. ✅ 补充完整元数据（batch_id, pool_id等）

---

## 主要改造内容

### 1. 配置管理模块

**新增文件：**
- `src/config/__init__.py` - 配置模块初始化
- `src/config/config_manager.py` - 配置管理器（单例模式）

**功能：**
- 统一读取 `config/client_config.json` 配置文件
- 支持环境变量覆盖
- 提供便捷的配置访问方法

**使用示例：**
```python
from src.config.config_manager import config_manager

# 获取配置值
pool_id = config_manager.get_pool_id()  # "4"
batch_id = config_manager.get_batch_id()  # 2
api_url = config_manager.get_api_endpoint('sensor_data')
```

### 2. API客户端模块

**新增文件：**
- `src/services/api_client.py` - 统一API客户端

**功能：**
- 统一处理与服务端的HTTP请求
- 自动重试机制
- 支持干运行模式
- 自动补充元数据（batch_id, pool_id等）

**使用示例：**
```python
from src.services.api_client import api_client

# 发送传感器数据
api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C"
)
```

### 3. 传感器数据服务改造

**改造文件：**
- `src/services/sensor_data_service_v2.py` - 重构版传感器服务

**改进：**
- ✅ 使用配置管理模块
- ✅ 从配置文件读取传感器设备列表
- ✅ 自动补充完整元数据（sensor_id, batch_id, pool_id, metric, unit等）
- ✅ 使用标准API接口（`/api/data/sensors`）
- ✅ 实时上传数据到服务端

### 4. 配置文件更新

**更新文件：**
- `config/client_config.json` - 统一配置文件

**配置项：**
- 站点信息（pool_id, batch_id, location, timezone）
- 传感器设备配置（串口、波特率、地址等）
- 摄像头设备配置
- 喂食机配置
- API端点配置
- 任务调度配置
- 路径配置

### 5. API接口文档

**新增文件：**
- `docs/API接口文档.md` - 完整的API接口文档

**内容：**
- 所有接口的详细说明
- 请求/响应格式
- 字段说明
- 使用示例
- 错误处理

---

## 配置说明

### 默认配置值

根据要求，以下配置已设置为默认值：

- `pool_id`: "4" （4号池）
- `batch_id`: 2 （批次2）
- 所有传感器、摄像头、喂食机都关联到 pool_id=4, batch_id=2

### 环境变量

可通过环境变量覆盖配置：

```bash
# 传感器模拟模式
export AIJ_SENSOR_SIMULATE=1

# 上传干运行模式
export AIJ_UPLOAD_DRY_RUN=1

# 摄像头上传干运行模式
export AIJ_CAMERA_UPLOAD_DRY_RUN=1

# 自定义配置文件路径
export AIJ_CONFIG_PATH=/path/to/config.json
```

---

## 待完成的工作

### 客户端

1. ⏳ **摄像头服务改造**
   - 使用配置管理模块
   - 补充完整元数据
   - 使用标准API接口

2. ⏳ **喂食机服务改造**
   - 实现数据记录功能
   - 实现数据上传功能
   - 补充完整元数据

3. ⏳ **主入口文件更新**
   - 使用新的配置和服务
   - 统一任务注册

### 服务端

1. ⚠️ **需要添加摄像头数据接收接口**
   - 当前服务端缺少 `/api/data/cameras` 接口
   - 需要在 `japan_server/routes/data_collection_routes.py` 中添加

**建议实现：**
```python
@data_collection_bp.route('/cameras', methods=['POST'])
def receive_camera_data():
    """
    接收摄像头图像数据接口
    
    请求方式：multipart/form-data
    参数：
    - file: 图像文件
    - camera_id: 摄像头ID
    - batch_id: 批次ID（可选）
    - pool_id: 池号（可选）
    - timestamp: 时间戳（可选）
    - width_px: 图像宽度（可选）
    - height_px: 图像高度（可选）
    - format: 图像格式（可选）
    """
    # TODO: 实现图像接收和存储逻辑
    pass
```

---

## 使用指南

### 1. 启动服务

```bash
# 方式1：使用批处理脚本
start_tasks.bat

# 方式2：命令行启动
python -m src.app.main
```

### 2. 查看日志

```bash
# 传感器服务日志
tail -f logs/sensor_service.log

# 调度器日志
tail -f logs/scheduler.log
```

### 3. 配置修改

编辑 `config/client_config.json` 文件，修改后重启服务即可生效。

---

## 接口文档

详细的API接口文档请参考：`docs/API接口文档.md`

---

## 注意事项

1. **配置文件路径**：确保 `config/client_config.json` 文件存在且格式正确
2. **服务端地址**：默认服务端地址为 `http://8.216.33.92:5000`，可在配置文件中修改
3. **网络连接**：确保客户端能够访问服务端地址
4. **依赖安装**：确保安装了必要的Python包（requests, pymodbus等）

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX




**改造日期：** 2025-01-XX  
**改造版本：** v2.0

---

## 改造目标

1. ✅ 符合工程化标准，提供接口文档
2. ✅ 符合文档中的数据传输请求规范
3. ✅ 统一配置管理，移除硬编码值
4. ✅ 补充完整元数据（batch_id, pool_id等）

---

## 主要改造内容

### 1. 配置管理模块

**新增文件：**
- `src/config/__init__.py` - 配置模块初始化
- `src/config/config_manager.py` - 配置管理器（单例模式）

**功能：**
- 统一读取 `config/client_config.json` 配置文件
- 支持环境变量覆盖
- 提供便捷的配置访问方法

**使用示例：**
```python
from src.config.config_manager import config_manager

# 获取配置值
pool_id = config_manager.get_pool_id()  # "4"
batch_id = config_manager.get_batch_id()  # 2
api_url = config_manager.get_api_endpoint('sensor_data')
```

### 2. API客户端模块

**新增文件：**
- `src/services/api_client.py` - 统一API客户端

**功能：**
- 统一处理与服务端的HTTP请求
- 自动重试机制
- 支持干运行模式
- 自动补充元数据（batch_id, pool_id等）

**使用示例：**
```python
from src.services.api_client import api_client

# 发送传感器数据
api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C"
)
```

### 3. 传感器数据服务改造

**改造文件：**
- `src/services/sensor_data_service_v2.py` - 重构版传感器服务

**改进：**
- ✅ 使用配置管理模块
- ✅ 从配置文件读取传感器设备列表
- ✅ 自动补充完整元数据（sensor_id, batch_id, pool_id, metric, unit等）
- ✅ 使用标准API接口（`/api/data/sensors`）
- ✅ 实时上传数据到服务端

### 4. 配置文件更新

**更新文件：**
- `config/client_config.json` - 统一配置文件

**配置项：**
- 站点信息（pool_id, batch_id, location, timezone）
- 传感器设备配置（串口、波特率、地址等）
- 摄像头设备配置
- 喂食机配置
- API端点配置
- 任务调度配置
- 路径配置

### 5. API接口文档

**新增文件：**
- `docs/API接口文档.md` - 完整的API接口文档

**内容：**
- 所有接口的详细说明
- 请求/响应格式
- 字段说明
- 使用示例
- 错误处理

---

## 配置说明

### 默认配置值

根据要求，以下配置已设置为默认值：

- `pool_id`: "4" （4号池）
- `batch_id`: 2 （批次2）
- 所有传感器、摄像头、喂食机都关联到 pool_id=4, batch_id=2

### 环境变量

可通过环境变量覆盖配置：

```bash
# 传感器模拟模式
export AIJ_SENSOR_SIMULATE=1

# 上传干运行模式
export AIJ_UPLOAD_DRY_RUN=1

# 摄像头上传干运行模式
export AIJ_CAMERA_UPLOAD_DRY_RUN=1

# 自定义配置文件路径
export AIJ_CONFIG_PATH=/path/to/config.json
```

---

## 待完成的工作

### 客户端

1. ⏳ **摄像头服务改造**
   - 使用配置管理模块
   - 补充完整元数据
   - 使用标准API接口

2. ⏳ **喂食机服务改造**
   - 实现数据记录功能
   - 实现数据上传功能
   - 补充完整元数据

3. ⏳ **主入口文件更新**
   - 使用新的配置和服务
   - 统一任务注册

### 服务端

1. ⚠️ **需要添加摄像头数据接收接口**
   - 当前服务端缺少 `/api/data/cameras` 接口
   - 需要在 `japan_server/routes/data_collection_routes.py` 中添加

**建议实现：**
```python
@data_collection_bp.route('/cameras', methods=['POST'])
def receive_camera_data():
    """
    接收摄像头图像数据接口
    
    请求方式：multipart/form-data
    参数：
    - file: 图像文件
    - camera_id: 摄像头ID
    - batch_id: 批次ID（可选）
    - pool_id: 池号（可选）
    - timestamp: 时间戳（可选）
    - width_px: 图像宽度（可选）
    - height_px: 图像高度（可选）
    - format: 图像格式（可选）
    """
    # TODO: 实现图像接收和存储逻辑
    pass
```

---

## 使用指南

### 1. 启动服务

```bash
# 方式1：使用批处理脚本
start_tasks.bat

# 方式2：命令行启动
python -m src.app.main
```

### 2. 查看日志

```bash
# 传感器服务日志
tail -f logs/sensor_service.log

# 调度器日志
tail -f logs/scheduler.log
```

### 3. 配置修改

编辑 `config/client_config.json` 文件，修改后重启服务即可生效。

---

## 接口文档

详细的API接口文档请参考：`docs/API接口文档.md`

---

## 注意事项

1. **配置文件路径**：确保 `config/client_config.json` 文件存在且格式正确
2. **服务端地址**：默认服务端地址为 `http://8.216.33.92:5000`，可在配置文件中修改
3. **网络连接**：确保客户端能够访问服务端地址
4. **依赖安装**：确保安装了必要的Python包（requests, pymodbus等）

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX



**改造日期：** 2025-01-XX  
**改造版本：** v2.0

---

## 改造目标

1. ✅ 符合工程化标准，提供接口文档
2. ✅ 符合文档中的数据传输请求规范
3. ✅ 统一配置管理，移除硬编码值
4. ✅ 补充完整元数据（batch_id, pool_id等）

---

## 主要改造内容

### 1. 配置管理模块

**新增文件：**
- `src/config/__init__.py` - 配置模块初始化
- `src/config/config_manager.py` - 配置管理器（单例模式）

**功能：**
- 统一读取 `config/client_config.json` 配置文件
- 支持环境变量覆盖
- 提供便捷的配置访问方法

**使用示例：**
```python
from src.config.config_manager import config_manager

# 获取配置值
pool_id = config_manager.get_pool_id()  # "4"
batch_id = config_manager.get_batch_id()  # 2
api_url = config_manager.get_api_endpoint('sensor_data')
```

### 2. API客户端模块

**新增文件：**
- `src/services/api_client.py` - 统一API客户端

**功能：**
- 统一处理与服务端的HTTP请求
- 自动重试机制
- 支持干运行模式
- 自动补充元数据（batch_id, pool_id等）

**使用示例：**
```python
from src.services.api_client import api_client

# 发送传感器数据
api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C"
)
```

### 3. 传感器数据服务改造

**改造文件：**
- `src/services/sensor_data_service_v2.py` - 重构版传感器服务

**改进：**
- ✅ 使用配置管理模块
- ✅ 从配置文件读取传感器设备列表
- ✅ 自动补充完整元数据（sensor_id, batch_id, pool_id, metric, unit等）
- ✅ 使用标准API接口（`/api/data/sensors`）
- ✅ 实时上传数据到服务端

### 4. 配置文件更新

**更新文件：**
- `config/client_config.json` - 统一配置文件

**配置项：**
- 站点信息（pool_id, batch_id, location, timezone）
- 传感器设备配置（串口、波特率、地址等）
- 摄像头设备配置
- 喂食机配置
- API端点配置
- 任务调度配置
- 路径配置

### 5. API接口文档

**新增文件：**
- `docs/API接口文档.md` - 完整的API接口文档

**内容：**
- 所有接口的详细说明
- 请求/响应格式
- 字段说明
- 使用示例
- 错误处理

---

## 配置说明

### 默认配置值

根据要求，以下配置已设置为默认值：

- `pool_id`: "4" （4号池）
- `batch_id`: 2 （批次2）
- 所有传感器、摄像头、喂食机都关联到 pool_id=4, batch_id=2

### 环境变量

可通过环境变量覆盖配置：

```bash
# 传感器模拟模式
export AIJ_SENSOR_SIMULATE=1

# 上传干运行模式
export AIJ_UPLOAD_DRY_RUN=1

# 摄像头上传干运行模式
export AIJ_CAMERA_UPLOAD_DRY_RUN=1

# 自定义配置文件路径
export AIJ_CONFIG_PATH=/path/to/config.json
```

---

## 待完成的工作

### 客户端

1. ⏳ **摄像头服务改造**
   - 使用配置管理模块
   - 补充完整元数据
   - 使用标准API接口

2. ⏳ **喂食机服务改造**
   - 实现数据记录功能
   - 实现数据上传功能
   - 补充完整元数据

3. ⏳ **主入口文件更新**
   - 使用新的配置和服务
   - 统一任务注册

### 服务端

1. ⚠️ **需要添加摄像头数据接收接口**
   - 当前服务端缺少 `/api/data/cameras` 接口
   - 需要在 `japan_server/routes/data_collection_routes.py` 中添加

**建议实现：**
```python
@data_collection_bp.route('/cameras', methods=['POST'])
def receive_camera_data():
    """
    接收摄像头图像数据接口
    
    请求方式：multipart/form-data
    参数：
    - file: 图像文件
    - camera_id: 摄像头ID
    - batch_id: 批次ID（可选）
    - pool_id: 池号（可选）
    - timestamp: 时间戳（可选）
    - width_px: 图像宽度（可选）
    - height_px: 图像高度（可选）
    - format: 图像格式（可选）
    """
    # TODO: 实现图像接收和存储逻辑
    pass
```

---

## 使用指南

### 1. 启动服务

```bash
# 方式1：使用批处理脚本
start_tasks.bat

# 方式2：命令行启动
python -m src.app.main
```

### 2. 查看日志

```bash
# 传感器服务日志
tail -f logs/sensor_service.log

# 调度器日志
tail -f logs/scheduler.log
```

### 3. 配置修改

编辑 `config/client_config.json` 文件，修改后重启服务即可生效。

---

## 接口文档

详细的API接口文档请参考：`docs/API接口文档.md`

---

## 注意事项

1. **配置文件路径**：确保 `config/client_config.json` 文件存在且格式正确
2. **服务端地址**：默认服务端地址为 `http://8.216.33.92:5000`，可在配置文件中修改
3. **网络连接**：确保客户端能够访问服务端地址
4. **依赖安装**：确保安装了必要的Python包（requests, pymodbus等）

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX




**改造日期：** 2025-01-XX  
**改造版本：** v2.0

---

## 改造目标

1. ✅ 符合工程化标准，提供接口文档
2. ✅ 符合文档中的数据传输请求规范
3. ✅ 统一配置管理，移除硬编码值
4. ✅ 补充完整元数据（batch_id, pool_id等）

---

## 主要改造内容

### 1. 配置管理模块

**新增文件：**
- `src/config/__init__.py` - 配置模块初始化
- `src/config/config_manager.py` - 配置管理器（单例模式）

**功能：**
- 统一读取 `config/client_config.json` 配置文件
- 支持环境变量覆盖
- 提供便捷的配置访问方法

**使用示例：**
```python
from src.config.config_manager import config_manager

# 获取配置值
pool_id = config_manager.get_pool_id()  # "4"
batch_id = config_manager.get_batch_id()  # 2
api_url = config_manager.get_api_endpoint('sensor_data')
```

### 2. API客户端模块

**新增文件：**
- `src/services/api_client.py` - 统一API客户端

**功能：**
- 统一处理与服务端的HTTP请求
- 自动重试机制
- 支持干运行模式
- 自动补充元数据（batch_id, pool_id等）

**使用示例：**
```python
from src.services.api_client import api_client

# 发送传感器数据
api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C"
)
```

### 3. 传感器数据服务改造

**改造文件：**
- `src/services/sensor_data_service_v2.py` - 重构版传感器服务

**改进：**
- ✅ 使用配置管理模块
- ✅ 从配置文件读取传感器设备列表
- ✅ 自动补充完整元数据（sensor_id, batch_id, pool_id, metric, unit等）
- ✅ 使用标准API接口（`/api/data/sensors`）
- ✅ 实时上传数据到服务端

### 4. 配置文件更新

**更新文件：**
- `config/client_config.json` - 统一配置文件

**配置项：**
- 站点信息（pool_id, batch_id, location, timezone）
- 传感器设备配置（串口、波特率、地址等）
- 摄像头设备配置
- 喂食机配置
- API端点配置
- 任务调度配置
- 路径配置

### 5. API接口文档

**新增文件：**
- `docs/API接口文档.md` - 完整的API接口文档

**内容：**
- 所有接口的详细说明
- 请求/响应格式
- 字段说明
- 使用示例
- 错误处理

---

## 配置说明

### 默认配置值

根据要求，以下配置已设置为默认值：

- `pool_id`: "4" （4号池）
- `batch_id`: 2 （批次2）
- 所有传感器、摄像头、喂食机都关联到 pool_id=4, batch_id=2

### 环境变量

可通过环境变量覆盖配置：

```bash
# 传感器模拟模式
export AIJ_SENSOR_SIMULATE=1

# 上传干运行模式
export AIJ_UPLOAD_DRY_RUN=1

# 摄像头上传干运行模式
export AIJ_CAMERA_UPLOAD_DRY_RUN=1

# 自定义配置文件路径
export AIJ_CONFIG_PATH=/path/to/config.json
```

---

## 待完成的工作

### 客户端

1. ⏳ **摄像头服务改造**
   - 使用配置管理模块
   - 补充完整元数据
   - 使用标准API接口

2. ⏳ **喂食机服务改造**
   - 实现数据记录功能
   - 实现数据上传功能
   - 补充完整元数据

3. ⏳ **主入口文件更新**
   - 使用新的配置和服务
   - 统一任务注册

### 服务端

1. ⚠️ **需要添加摄像头数据接收接口**
   - 当前服务端缺少 `/api/data/cameras` 接口
   - 需要在 `japan_server/routes/data_collection_routes.py` 中添加

**建议实现：**
```python
@data_collection_bp.route('/cameras', methods=['POST'])
def receive_camera_data():
    """
    接收摄像头图像数据接口
    
    请求方式：multipart/form-data
    参数：
    - file: 图像文件
    - camera_id: 摄像头ID
    - batch_id: 批次ID（可选）
    - pool_id: 池号（可选）
    - timestamp: 时间戳（可选）
    - width_px: 图像宽度（可选）
    - height_px: 图像高度（可选）
    - format: 图像格式（可选）
    """
    # TODO: 实现图像接收和存储逻辑
    pass
```

---

## 使用指南

### 1. 启动服务

```bash
# 方式1：使用批处理脚本
start_tasks.bat

# 方式2：命令行启动
python -m src.app.main
```

### 2. 查看日志

```bash
# 传感器服务日志
tail -f logs/sensor_service.log

# 调度器日志
tail -f logs/scheduler.log
```

### 3. 配置修改

编辑 `config/client_config.json` 文件，修改后重启服务即可生效。

---

## 接口文档

详细的API接口文档请参考：`docs/API接口文档.md`

---

## 注意事项

1. **配置文件路径**：确保 `config/client_config.json` 文件存在且格式正确
2. **服务端地址**：默认服务端地址为 `http://8.216.33.92:5000`，可在配置文件中修改
3. **网络连接**：确保客户端能够访问服务端地址
4. **依赖安装**：确保安装了必要的Python包（requests, pymodbus等）

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX



**改造日期：** 2025-01-XX  
**改造版本：** v2.0

---

## 改造目标

1. ✅ 符合工程化标准，提供接口文档
2. ✅ 符合文档中的数据传输请求规范
3. ✅ 统一配置管理，移除硬编码值
4. ✅ 补充完整元数据（batch_id, pool_id等）

---

## 主要改造内容

### 1. 配置管理模块

**新增文件：**
- `src/config/__init__.py` - 配置模块初始化
- `src/config/config_manager.py` - 配置管理器（单例模式）

**功能：**
- 统一读取 `config/client_config.json` 配置文件
- 支持环境变量覆盖
- 提供便捷的配置访问方法

**使用示例：**
```python
from src.config.config_manager import config_manager

# 获取配置值
pool_id = config_manager.get_pool_id()  # "4"
batch_id = config_manager.get_batch_id()  # 2
api_url = config_manager.get_api_endpoint('sensor_data')
```

### 2. API客户端模块

**新增文件：**
- `src/services/api_client.py` - 统一API客户端

**功能：**
- 统一处理与服务端的HTTP请求
- 自动重试机制
- 支持干运行模式
- 自动补充元数据（batch_id, pool_id等）

**使用示例：**
```python
from src.services.api_client import api_client

# 发送传感器数据
api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C"
)
```

### 3. 传感器数据服务改造

**改造文件：**
- `src/services/sensor_data_service_v2.py` - 重构版传感器服务

**改进：**
- ✅ 使用配置管理模块
- ✅ 从配置文件读取传感器设备列表
- ✅ 自动补充完整元数据（sensor_id, batch_id, pool_id, metric, unit等）
- ✅ 使用标准API接口（`/api/data/sensors`）
- ✅ 实时上传数据到服务端

### 4. 配置文件更新

**更新文件：**
- `config/client_config.json` - 统一配置文件

**配置项：**
- 站点信息（pool_id, batch_id, location, timezone）
- 传感器设备配置（串口、波特率、地址等）
- 摄像头设备配置
- 喂食机配置
- API端点配置
- 任务调度配置
- 路径配置

### 5. API接口文档

**新增文件：**
- `docs/API接口文档.md` - 完整的API接口文档

**内容：**
- 所有接口的详细说明
- 请求/响应格式
- 字段说明
- 使用示例
- 错误处理

---

## 配置说明

### 默认配置值

根据要求，以下配置已设置为默认值：

- `pool_id`: "4" （4号池）
- `batch_id`: 2 （批次2）
- 所有传感器、摄像头、喂食机都关联到 pool_id=4, batch_id=2

### 环境变量

可通过环境变量覆盖配置：

```bash
# 传感器模拟模式
export AIJ_SENSOR_SIMULATE=1

# 上传干运行模式
export AIJ_UPLOAD_DRY_RUN=1

# 摄像头上传干运行模式
export AIJ_CAMERA_UPLOAD_DRY_RUN=1

# 自定义配置文件路径
export AIJ_CONFIG_PATH=/path/to/config.json
```

---

## 待完成的工作

### 客户端

1. ⏳ **摄像头服务改造**
   - 使用配置管理模块
   - 补充完整元数据
   - 使用标准API接口

2. ⏳ **喂食机服务改造**
   - 实现数据记录功能
   - 实现数据上传功能
   - 补充完整元数据

3. ⏳ **主入口文件更新**
   - 使用新的配置和服务
   - 统一任务注册

### 服务端

1. ⚠️ **需要添加摄像头数据接收接口**
   - 当前服务端缺少 `/api/data/cameras` 接口
   - 需要在 `japan_server/routes/data_collection_routes.py` 中添加

**建议实现：**
```python
@data_collection_bp.route('/cameras', methods=['POST'])
def receive_camera_data():
    """
    接收摄像头图像数据接口
    
    请求方式：multipart/form-data
    参数：
    - file: 图像文件
    - camera_id: 摄像头ID
    - batch_id: 批次ID（可选）
    - pool_id: 池号（可选）
    - timestamp: 时间戳（可选）
    - width_px: 图像宽度（可选）
    - height_px: 图像高度（可选）
    - format: 图像格式（可选）
    """
    # TODO: 实现图像接收和存储逻辑
    pass
```

---

## 使用指南

### 1. 启动服务

```bash
# 方式1：使用批处理脚本
start_tasks.bat

# 方式2：命令行启动
python -m src.app.main
```

### 2. 查看日志

```bash
# 传感器服务日志
tail -f logs/sensor_service.log

# 调度器日志
tail -f logs/scheduler.log
```

### 3. 配置修改

编辑 `config/client_config.json` 文件，修改后重启服务即可生效。

---

## 接口文档

详细的API接口文档请参考：`docs/API接口文档.md`

---

## 注意事项

1. **配置文件路径**：确保 `config/client_config.json` 文件存在且格式正确
2. **服务端地址**：默认服务端地址为 `http://8.216.33.92:5000`，可在配置文件中修改
3. **网络连接**：确保客户端能够访问服务端地址
4. **依赖安装**：确保安装了必要的Python包（requests, pymodbus等）

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX




**改造日期：** 2025-01-XX  
**改造版本：** v2.0

---

## 改造目标

1. ✅ 符合工程化标准，提供接口文档
2. ✅ 符合文档中的数据传输请求规范
3. ✅ 统一配置管理，移除硬编码值
4. ✅ 补充完整元数据（batch_id, pool_id等）

---

## 主要改造内容

### 1. 配置管理模块

**新增文件：**
- `src/config/__init__.py` - 配置模块初始化
- `src/config/config_manager.py` - 配置管理器（单例模式）

**功能：**
- 统一读取 `config/client_config.json` 配置文件
- 支持环境变量覆盖
- 提供便捷的配置访问方法

**使用示例：**
```python
from src.config.config_manager import config_manager

# 获取配置值
pool_id = config_manager.get_pool_id()  # "4"
batch_id = config_manager.get_batch_id()  # 2
api_url = config_manager.get_api_endpoint('sensor_data')
```

### 2. API客户端模块

**新增文件：**
- `src/services/api_client.py` - 统一API客户端

**功能：**
- 统一处理与服务端的HTTP请求
- 自动重试机制
- 支持干运行模式
- 自动补充元数据（batch_id, pool_id等）

**使用示例：**
```python
from src.services.api_client import api_client

# 发送传感器数据
api_client.send_sensor_data(
    sensor_id=1,
    value=25.5,
    metric="temperature",
    unit="°C"
)
```

### 3. 传感器数据服务改造

**改造文件：**
- `src/services/sensor_data_service_v2.py` - 重构版传感器服务

**改进：**
- ✅ 使用配置管理模块
- ✅ 从配置文件读取传感器设备列表
- ✅ 自动补充完整元数据（sensor_id, batch_id, pool_id, metric, unit等）
- ✅ 使用标准API接口（`/api/data/sensors`）
- ✅ 实时上传数据到服务端

### 4. 配置文件更新

**更新文件：**
- `config/client_config.json` - 统一配置文件

**配置项：**
- 站点信息（pool_id, batch_id, location, timezone）
- 传感器设备配置（串口、波特率、地址等）
- 摄像头设备配置
- 喂食机配置
- API端点配置
- 任务调度配置
- 路径配置

### 5. API接口文档

**新增文件：**
- `docs/API接口文档.md` - 完整的API接口文档

**内容：**
- 所有接口的详细说明
- 请求/响应格式
- 字段说明
- 使用示例
- 错误处理

---

## 配置说明

### 默认配置值

根据要求，以下配置已设置为默认值：

- `pool_id`: "4" （4号池）
- `batch_id`: 2 （批次2）
- 所有传感器、摄像头、喂食机都关联到 pool_id=4, batch_id=2

### 环境变量

可通过环境变量覆盖配置：

```bash
# 传感器模拟模式
export AIJ_SENSOR_SIMULATE=1

# 上传干运行模式
export AIJ_UPLOAD_DRY_RUN=1

# 摄像头上传干运行模式
export AIJ_CAMERA_UPLOAD_DRY_RUN=1

# 自定义配置文件路径
export AIJ_CONFIG_PATH=/path/to/config.json
```

---

## 待完成的工作

### 客户端

1. ⏳ **摄像头服务改造**
   - 使用配置管理模块
   - 补充完整元数据
   - 使用标准API接口

2. ⏳ **喂食机服务改造**
   - 实现数据记录功能
   - 实现数据上传功能
   - 补充完整元数据

3. ⏳ **主入口文件更新**
   - 使用新的配置和服务
   - 统一任务注册

### 服务端

1. ⚠️ **需要添加摄像头数据接收接口**
   - 当前服务端缺少 `/api/data/cameras` 接口
   - 需要在 `japan_server/routes/data_collection_routes.py` 中添加

**建议实现：**
```python
@data_collection_bp.route('/cameras', methods=['POST'])
def receive_camera_data():
    """
    接收摄像头图像数据接口
    
    请求方式：multipart/form-data
    参数：
    - file: 图像文件
    - camera_id: 摄像头ID
    - batch_id: 批次ID（可选）
    - pool_id: 池号（可选）
    - timestamp: 时间戳（可选）
    - width_px: 图像宽度（可选）
    - height_px: 图像高度（可选）
    - format: 图像格式（可选）
    """
    # TODO: 实现图像接收和存储逻辑
    pass
```

---

## 使用指南

### 1. 启动服务

```bash
# 方式1：使用批处理脚本
start_tasks.bat

# 方式2：命令行启动
python -m src.app.main
```

### 2. 查看日志

```bash
# 传感器服务日志
tail -f logs/sensor_service.log

# 调度器日志
tail -f logs/scheduler.log
```

### 3. 配置修改

编辑 `config/client_config.json` 文件，修改后重启服务即可生效。

---

## 接口文档

详细的API接口文档请参考：`docs/API接口文档.md`

---

## 注意事项

1. **配置文件路径**：确保 `config/client_config.json` 文件存在且格式正确
2. **服务端地址**：默认服务端地址为 `http://8.216.33.92:5000`，可在配置文件中修改
3. **网络连接**：确保客户端能够访问服务端地址
4. **依赖安装**：确保安装了必要的Python包（requests, pymodbus等）

---

**文档状态：** ✅ 已完成  
**最后更新：** 2025-01-XX


