# examples 目录

示例代码与演示脚本：
- task_examples.py：任务用法示例（参考新架构）。

快速示例：自定义任务
```python
from src.scheduler.task_scheduler import TaskScheduler, ScheduleRule, ScheduleType, BaseTask

class DemoTask(BaseTask):
    def __init__(self):
        super().__init__(task_id="demo", name="演示任务")
    def execute(self) -> bool:
        print("DemoTask executed")
        return True

scheduler = TaskScheduler()
scheduler.add_task(DemoTask(), ScheduleRule(ScheduleType.INTERVAL, seconds=30))
scheduler.start()
```