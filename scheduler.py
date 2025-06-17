from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time
import threading


from data_collection import main as data_collect

def run_data_collect():
    data_collect()

def morning_task():
    print(f"[{datetime.now()}] 执行上午任务 A")

def afternoon_task():
    print(f"[{datetime.now()}] 执行下午任务 B")
    t = threading.Thread(target=run_data_collect)
    t.daemon = True  
    t.start()

def evening_task():
    print(f"[{datetime.now()}] 执行晚上任务 C")
    print(123)

scheduler = BackgroundScheduler()

scheduler.add_job(morning_task, 'cron', hour=9, minute=0)
scheduler.add_job(afternoon_task, 'cron', hour=19, minute=24)
scheduler.add_job(evening_task, 'cron', hour=19, minute=25)

scheduler.start()
print("定时任务启动中，按 Ctrl+C 停止...")

try:
    while True:
        time.sleep(1)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    print("定时任务已终止。")
