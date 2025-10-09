from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime
import time
import threading


from sensor_data_collection import main as sensor_data_collect
from video_data_collection import  main as video_data_collect

def run_sensor_data_collect():
    sensor_data_collect()

def run_video_data_collect():
    video_data_collect()    

def morning_task():
    print(f"[{datetime.now()}] 执行上午任务 A")

def afternoon_task():
    print(f"[{datetime.now()}] 执行下午任务 B")
    A = threading.Thread(target=run_sensor_data_collect)
    A.daemon = True  
    A.start()
    B = threading.Thread(target=video_data_collect)
    B.daemon = True  
    B.start()    

def evening_task():
    print(f"[{datetime.now()}] 执行晚上任务 C")
    print(123)

scheduler = BackgroundScheduler()

scheduler.add_job(morning_task, 'cron', hour=9, minute=0)
scheduler.add_job(afternoon_task, 'cron', hour=17, minute=45)
scheduler.add_job(evening_task, 'cron', hour=19, minute=25)

scheduler.start()
print("定时任务启动中，按 Ctrl+C 停止...")

try:
    while True:
        time.sleep(1)
except (KeyboardInterrupt, SystemExit):
    scheduler.shutdown()
    print("定时任务已终止。")
