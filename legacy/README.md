# legacy 目录

存放旧版或已被新架构替代的脚本，保留以便参考与回退。

当前主要内容：
- scheduled_tasks.py：旧的任务入口，已由 src/app/main.py 替代。
- scheduler.py：旧的调度器脚本，已由 src/scheduler/task_scheduler.py 替代。
- sensor_data_collection.py：旧的传感器采集脚本，已由 src/services/sensor_data_service.py 替代。

如何回退使用旧版
- 直接运行 legacy/scheduled_tasks.py（不推荐，仅在需要对比时使用）
- 注意：旧版不支持统一的模拟/干运行开关，且目录结构与日志路径不同。