# 企业级定时任务调度器

## 概述

这是一个为日本养殖项目开发的企业级定时任务调度器，支持多种类型的定时任务，包括脚本执行、函数调用和自定义任务。调度器具备完善的错误处理、重试机制、日志记录和任务监控功能。

## 核心特性

### 🚀 核心功能
- **多种任务类型**：支持脚本任务、函数任务和自定义任务
- **灵活调度**：支持间隔调度、一次性任务等多种调度模式
- **并发执行**：基于线程池的并发任务执行
- **错误处理**：完善的异常处理和重试机制
- **状态监控**：实时任务状态监控和统计

### 🛡️ 企业级特性
- **配置管理**：外部化配置文件支持
- **日志系统**：完整的日志记录和管理
- **优雅关闭**：支持信号处理和优雅关闭
- **资源管理**：自动资源清理和内存管理
- **扩展性**：模块化设计，易于扩展

## 快速开始

### 1. 基本使用

```python
from task_scheduler import TaskScheduler, ScriptTask, ScheduleRule, ScheduleType

# 创建调度器
scheduler = TaskScheduler()

# 创建脚本任务
task = ScriptTask(
    task_id="data_upload",
    name="数据上传任务",
    script_path="client/updata.py"
)

# 创建调度规则（每小时执行一次）
schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=3600)

# 添加任务
scheduler.add_task(task, schedule)

# 启动调度器
scheduler.start()

# 保持运行
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    scheduler.stop()
```

### 2. 运行预定义任务

```bash
# 直接运行主程序，包含预定义的任务
python task_scheduler.py
```

### 3. 查看示例

```bash
# 运行示例程序
python task_examples.py
```

## 任务类型

### 1. 脚本任务 (ScriptTask)

执行Python脚本文件：

```python
task = ScriptTask(
    task_id="upload_task",
    name="数据上传",
    script_path="client/updata.py",
    args=["--mode", "auto"],           # 脚本参数
    working_dir="/path/to/workdir",    # 工作目录
    timeout=300,                       # 超时时间（秒）
    description="上传传感器数据"
)
```

### 2. 函数任务 (FunctionTask)

执行Python函数：

```python
def my_function(param1, param2):
    print(f"执行函数: {param1}, {param2}")
    return True

task = FunctionTask(
    task_id="func_task",
    name="函数任务",
    func=my_function,
    args=("arg1", "arg2"),
    kwargs={"key": "value"},
    description="执行自定义函数"
)
```

### 3. 自定义任务 (BaseTask)

继承BaseTask创建自定义任务：

```python
class CustomTask(BaseTask):
    def __init__(self, task_id, name):
        super().__init__(task_id, name)
    
    def execute(self) -> bool:
        # 实现具体的任务逻辑
        try:
            # 执行任务
            return True  # 成功返回True
        except Exception as e:
            self.last_error = str(e)
            return False  # 失败返回False
```

## 调度规则

### 1. 间隔调度

```python
# 每30秒执行一次
schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=30)

# 每5分钟执行一次
schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=300)

# 每小时执行一次
schedule = ScheduleRule(ScheduleType.INTERVAL, seconds=3600)
```

### 2. 一次性任务

```python
from datetime import datetime, timedelta

# 5分钟后执行一次
run_time = datetime.now() + timedelta(minutes=5)
schedule = ScheduleRule(ScheduleType.ONCE, run_at=run_time)
```

## 配置管理

### 配置文件结构 (scheduler_config.json)

```json
{
    "scheduler": {
        "max_workers": 10,        // 最大工作线程数
        "check_interval": 1,      // 检查间隔（秒）
        "enable_monitoring": true, // 启用监控
        "log_level": "INFO"       // 日志级别
    },
    "tasks": {
        "default_timeout": 300,   // 默认超时时间
        "max_retries": 3,         // 最大重试次数
        "retry_delay": 5          // 重试延迟（秒）
    },
    "logging": {
        "log_dir": "logs",        // 日志目录
        "log_file": "scheduler.log", // 日志文件名
        "max_log_size": "10MB",   // 最大日志大小
        "backup_count": 5         // 备份文件数量
    }
}
```

### 使用自定义配置

```python
# 使用自定义配置文件
scheduler = TaskScheduler("my_config.json")
```

## 任务管理

### 添加任务

```python
scheduler.add_task(task, schedule_rule)
```

### 移除任务

```python
scheduler.remove_task("task_id")
```

### 查看任务状态

```python
# 查看所有任务状态
status = scheduler.get_task_status()
print(f"总任务数: {status['total_tasks']}")
print(f"运行中: {status['running_tasks']}")

# 查看特定任务状态
task_status = scheduler.get_task_status("task_id")
print(f"任务状态: {task_status['status']}")
print(f"执行次数: {task_status['run_count']}")
print(f"成功率: {task_status['success_rate']}")
```

## 预定义任务

调度器包含以下预定义任务：

1. **数据上传任务** - 每小时执行一次
   - 执行 `client/updata.py` 脚本
   - 上传传感器数据和操作日志

2. **传感器数据采集** - 每5分钟执行一次
   - 执行 `sensor_data_collection.py` 脚本
   - 采集各种传感器数据

3. **心跳检测** - 每30秒执行一次
   - 执行 `client/heart_beat.py` 脚本
   - 发送系统心跳信号

4. **日志清理** - 每24小时执行一次
   - 清理7天前的日志文件
   - 保持日志目录整洁

## 监控和日志

### 日志级别

- **DEBUG**: 详细的调试信息
- **INFO**: 一般信息（默认）
- **WARNING**: 警告信息
- **ERROR**: 错误信息

### 日志格式

```
2024-01-01 12:00:00 - TaskScheduler - INFO - _execute_task:123 - 开始执行任务: 数据上传任务
```

### 任务统计

每个任务都会记录以下统计信息：
- 总执行次数
- 成功次数
- 失败次数
- 成功率
- 最后执行时间
- 下次执行时间
- 最后错误信息

## 错误处理

### 重试机制

- 任务失败时自动重试
- 可配置最大重试次数
- 可配置重试延迟时间
- 指数退避策略（可选）

### 异常处理

- 捕获并记录所有异常
- 任务超时处理
- 资源清理保证

### 故障恢复

- 调度器异常时自动恢复
- 任务状态持久化（可选）
- 优雅关闭机制

## 性能优化

### 线程池管理

- 可配置最大工作线程数
- 自动任务队列管理
- 资源复用和清理

### 内存管理

- 自动清理已完成的Future对象
- 定期垃圾回收
- 内存使用监控

### 性能监控

- 任务执行时间统计
- 系统资源使用监控
- 性能瓶颈识别

## 扩展开发

### 创建自定义任务类

```python
class MyCustomTask(BaseTask):
    def __init__(self, task_id, name, custom_param):
        super().__init__(task_id, name)
        self.custom_param = custom_param
    
    def execute(self) -> bool:
        # 实现自定义逻辑
        try:
            # 执行具体任务
            result = self.do_something()
            return result
        except Exception as e:
            logging.error(f"任务执行失败: {e}")
            self.last_error = str(e)
            return False
    
    def do_something(self):
        # 具体的业务逻辑
        pass
```

### 添加新的调度类型

```python
class CronScheduleRule(ScheduleRule):
    def __init__(self, cron_expression):
        super().__init__(ScheduleType.CRON, cron=cron_expression)
    
    def get_next_run_time(self, last_run=None):
        # 实现Cron表达式解析逻辑
        pass
```

## 部署建议

### 生产环境部署

1. **配置优化**
   ```json
   {
       "scheduler": {
           "max_workers": 20,
           "log_level": "WARNING"
       },
       "tasks": {
           "max_retries": 5,
           "retry_delay": 10
       }
   }
   ```

2. **系统服务**
   ```bash
   # 创建systemd服务文件
   sudo nano /etc/systemd/system/task-scheduler.service
   ```

3. **监控集成**
   - 集成Prometheus监控
   - 配置告警规则
   - 日志聚合分析

### 安全考虑

- 脚本路径验证
- 执行权限控制
- 敏感信息保护
- 网络访问限制

## 故障排除

### 常见问题

1. **任务不执行**
   - 检查任务状态
   - 验证调度规则
   - 查看错误日志

2. **脚本执行失败**
   - 检查脚本路径
   - 验证执行权限
   - 查看脚本输出

3. **内存使用过高**
   - 减少最大工作线程数
   - 优化任务逻辑
   - 增加垃圾回收频率

### 调试技巧

```python
# 启用调试日志
scheduler.config.config['scheduler']['log_level'] = 'DEBUG'

# 查看详细任务信息
status = scheduler.get_task_status()
for task_id, info in status['tasks'].items():
    print(json.dumps(info, indent=2, ensure_ascii=False))
```

## 版本历史

- **v1.0** - 初始版本
  - 基本任务调度功能
  - 脚本和函数任务支持
  - 配置管理和日志系统

## 许可证

本项目采用MIT许可证，详见LICENSE文件。

## 支持

如有问题或建议，请联系开发团队或提交Issue。