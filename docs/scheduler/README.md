# 调度器文档概览

核心实现：src/scheduler/task_scheduler.py

使用方式
- 入口运行：python -m src.app.main（或使用 start_tasks.bat）
- 在入口中通过 TaskScheduler 注册任务与调度规则

常用API
- BaseTask：自定义任务基类，需实现 execute() 返回布尔值
- TaskScheduler：任务注册、调度、重试与状态查询
- ScheduleRule/ScheduleType：支持 INTERVAL/ONCE 等调度类型
- 预定义任务工厂：create_data_upload_task()

示例（注册自定义任务）
```python
from src.scheduler.task_scheduler import TaskScheduler, ScheduleRule, ScheduleType, BaseTask

class MyTask(BaseTask):
    def __init__(self):
        super().__init__(task_id="my_task", name="示例任务")
    def execute(self) -> bool:
        print("Hello from MyTask")
        return True

scheduler = TaskScheduler()
scheduler.add_task(MyTask(), ScheduleRule(ScheduleType.INTERVAL, seconds=60))
scheduler.start()
```

更多细节请参考 README_scheduler.md 与代码注释。