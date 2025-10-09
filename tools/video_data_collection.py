import time
from video_capture import capture 

def main():
    try:
        while True:
            print("开始采集视频帧...")
            capture()  
            time.sleep(60)
    except KeyboardInterrupt:
        print("\n采集结束，退出程序。")

if __name__ == "__main__":
    main()
