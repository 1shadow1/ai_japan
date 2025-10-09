# AI Japan 定时任务系统

## 📋 概述

本系统将 `updata.py` 和 `sensor_data_collection.py` 两个脚本集成为企业级定时任务系统，实现：

- **传感器数据采集**: 后台持续运行，实时采集传感器数据
- **数据上传任务**: 每日定时执行，自动上传数据到服务器
- **任务监控**: Web界面实时监控任务状态和系统健康度
- **错误处理**: 自动重试机制和异常恢复

## 🏗️ 系统架构

```
ai_japan/
├── scheduled_tasks.py          # 主要定时任务脚本
├── sensor_data_service.py      # 传感器数据采集服务
├── task_monitor.py            # Web监控界面
├── task_scheduler.py          # 任务调度器核心
├── start_tasks.bat           # 启动定时任务系统
├── start_monitor.bat         # 启动监控界面
├── client/updata.py          # 数据上传脚本（已优化）
└── sensor_data_collection.py # 原传感器脚本（保留）
```

## 🚀 快速开始

### 方式一：使用批处理脚本（推荐）

1. **启动定时任务系统**
   ```bash
   双击运行: start_tasks.bat
   ```

2. **启动监控界面**
   ```bash
   双击运行: start_monitor.bat
   ```

### 方式二：命令行启动

1. **启动定时任务系统**
   ```bash
   cd f:/work/singa/ai_japan
   python scheduled_tasks.py
   ```

2. **启动监控界面**
   ```bash
   cd f:/work/singa/ai_japan
   python task_monitor.py
   ```

3. **访问监控界面**
   ```
   浏览器打开: http://localhost:5000
   ```

## 📊 任务配置详情

### 1. 传感器数据采集任务

- **执行方式**: 后台持续运行
- **数据采集**: 每10秒读取一次传感器数据
- **数据记录**: 每5秒记录一次到CSV文件
- **状态检查**: 每小时检查一次服务状态
- **输出文件**: `./output/sensor/data_collection.csv`

**支持的传感器**:
- 溶解氧传感器 (COM18)
- 液位传感器 (COM25)
- pH传感器 (COM4)
- 浊度传感器 (COM5)

### 2. 数据上传任务

- **执行频率**: 每日凌晨2点执行
- **执行脚本**: `client/updata.py`
- **超时设置**: 5分钟
- **重试机制**: 自动重试失败的上传
- **日志记录**: 详细记录执行结果

## 🎛️ 监控界面功能

访问 `http://localhost:5000` 查看：

### 系统状态面板
- 调度器运行状态
- 系统运行时长
- 实时系统时间

### 传感器监控
- 服务运行状态
- 实时传感器数据
- 数据采集统计

### 上传任务监控
- 任务执行状态
- 下次执行时间
- 历史执行结果

### 手动控制
- 启动/停止传感器服务
- 手动触发数据上传
- 刷新系统状态

## 🔧 配置说明

### 传感器配置

在 `sensor_data_service.py` 中修改传感器配置：

```python
self.sensor_configs = {
    'dissolved_oxygen': {
        'port': 'COM18',        # 串口号
        'baudrate': 4800,       # 波特率
        'address': 0x0002,      # 寄存器地址
        'count': 2,             # 寄存器数量
        'slave': 0x01,          # 从机地址
    },
    # ... 其他传感器配置
}
```

### 上传任务配置

在 `scheduled_tasks.py` 中修改上传时间：

```python
# 设置每天凌晨2点执行上传任务
tomorrow_2am = datetime.now().replace(hour=2, minute=0, second=0, microsecond=0)
```

### 调度器配置

使用 `scheduler_config.json` 进行高级配置：

```json
{
    "scheduler": {
        "max_workers": 4,
        "enable_logging": true,
        "log_level": "INFO"
    },
    "tasks": {
        "sensor_check_interval": 3600,
        "upload_time": "02:00:00"
    }
}
```

## 📁 输出文件

### 数据文件
- `./output/sensor/data_collection.csv` - 传感器数据记录
- `./client/output/` - 上传文件存储目录

### 日志文件
- `./logs/sensor_service.log` - 传感器服务日志
- `./logs/scheduled_tasks.log` - 定时任务日志
- `./logs/task_scheduler.log` - 调度器日志

## 🛠️ 故障排除

### 常见问题

1. **传感器连接失败**
   - 检查串口号是否正确
   - 确认传感器设备已连接
   - 检查串口权限

2. **上传任务失败**
   - 检查网络连接
   - 验证服务器地址和端口
   - 查看上传脚本日志

3. **监控界面无法访问**
   - 确认端口5000未被占用
   - 检查防火墙设置
   - 验证Flask依赖是否安装

### 日志查看

```bash
# 查看传感器服务日志
type logs\sensor_service.log

# 查看定时任务日志
type logs\scheduled_tasks.log

# 查看调度器日志
type logs\task_scheduler.log
```

## 🔄 系统维护

### 定期维护任务

1. **清理日志文件** (建议每月)
   ```bash
   # 清理30天前的日志
   forfiles /p logs /s /m *.log /d -30 /c "cmd /c del @path"
   ```

2. **备份数据文件** (建议每周)
   ```bash
   # 备份传感器数据
   copy "output\sensor\data_collection.csv" "backup\data_collection_%date%.csv"
   ```

3. **检查磁盘空间**
   - 监控日志文件大小
   - 定期清理临时文件

### 性能优化

1. **传感器采集频率调整**
   - 根据需求调整采集间隔
   - 平衡数据精度和系统负载

2. **日志级别配置**
   - 生产环境使用INFO级别
   - 调试时使用DEBUG级别

## 🚀 扩展功能

### 添加新传感器

1. 在 `sensor_data_service.py` 中添加传感器配置
2. 实现对应的数据处理函数
3. 更新CSV文件列名

### 添加新定时任务

1. 继承 `Task` 类创建新任务
2. 在 `scheduled_tasks.py` 中注册任务
3. 配置执行规则

### 集成外部系统

1. 通过API接口集成
2. 使用消息队列通信
3. 数据库持久化存储

## 📞 技术支持

如遇到问题，请检查：

1. **系统要求**
   - Python 3.7+
   - 必要的依赖包
   - 串口驱动程序

2. **依赖安装**
   ```bash
   pip install pandas pymodbus flask threading
   ```

3. **权限设置**
   - 串口访问权限
   - 文件写入权限
   - 网络访问权限

---

## 📝 版本历史

- **v1.0** - 基础定时任务系统
- **v1.1** - 添加Web监控界面
- **v1.2** - 增强错误处理和重试机制
- **v1.3** - 优化性能和资源管理

---

**开发团队**: AI Japan Project  
**最后更新**: 2024年12月  
**文档版本**: v1.3