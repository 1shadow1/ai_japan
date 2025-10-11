import requests
import json
import time

BASE_URL = "https://ffish.huaeran.cn:8081/commonRequest"  # 登录/获取设备列表

# TODO:定时喂
# TODO:时区修改
# TODO:通过AI控制的喂食记录


class FeederAPI:
    def __init__(self, user_id: str, password: str):
        self.user_id = user_id
        self.password = password
        self.authkey = None

    def login(self):
        """获取 authkey"""
        payload = {
            "msgType": 1000,
            "userID": self.user_id,
            "password": self.password
        }
        resp = requests.post(BASE_URL, json=payload, verify=False)
        data = resp.json()
        if data.get("status") == 1:
            self.authkey = data["data"][0]["authkey"]
            print(f"[登录成功] authkey: {self.authkey}")
            return True
        else:
            print(f"[登录失败] {data}")
            return False

    def get_devices(self, page_index=0, page_size=50):
        """获取设备列表"""
        if not self.authkey:
            raise Exception("请先登录获取 authkey")
        payload = {
            "msgType": 1401,
            "authkey": self.authkey,
            "userID": self.user_id,
            "pageIndex": page_index,
            "pageSize": page_size
        }
        resp = requests.post(BASE_URL, json=payload, verify=False)
        data = resp.json()
        print(f"dev info:{data}")
        if data.get("status") == 1:
            devices = data.get("data", [])
            print(f"[获取设备成功] 共 {len(devices)} 个设备")
            return devices
        else:
            print(f"[获取设备失败] {data}")
            return []

    def get_device_status(self, dev_id: str):
        """查询设备状态"""
        payload = {
            "msgType": 2000,
            "authkey": self.authkey,
            "userID": self.user_id,
            "devID": dev_id
        }
        resp = requests.post(BASE_URL, json=payload, verify=False)
        data = resp.json()
        print(f"dev status:{data}")
        if data.get("status") == 1:
            status = data["data"][0]
            print(f"[设备状态] {status}")
            return status
        else:
            print(f"[获取状态失败] {data}")
            return None

    def feed(self, dev_id: str, count: int):
        """手动喂食 count 份"""
        payload = {
            "msgType": 2001,   
            "authkey": self.authkey,
            "userID": self.user_id,
            "devID": dev_id,
            "feedCount": count
        }
        resp = requests.post(BASE_URL, json=payload, verify=False)
        data = resp.json()
        print(f"feed status:{data}")

        if data.get("status") == 1:
            print(f"[喂食成功] 已发送 {count} 份喂食指令")
            return True
        else:
            print(f"[喂食失败] {data}")
            return False


if __name__ == "__main__":
    user_id = "8619034657726"      # 替换为实际用户ID（区号+手机号）
    password = "123456789"     # 替换为实际密钥

    feeder = FeederAPI(user_id, password)

    if feeder.login():
        devices = feeder.get_devices()
        if devices:
            dev_id = devices[0]["devID"]
            dev_id = "98f4abf5481e"
            print(f"devID:{dev_id}")
            feeder.get_device_status(dev_id)
            # feeder.feed(dev_id, 1)  # 喂 5 份
