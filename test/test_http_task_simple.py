#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简化版HTTP请求任务测试脚本
避免pandas依赖问题，直接测试HTTP请求任务的核心功能
"""

import sys
import os
import json
import logging
from datetime import datetime

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_http_task_basic():
    """基本HTTP请求任务测试"""
    print("=" * 60)
    print("基本HTTP请求任务测试")
    print("=" * 60)
    
    try:
        # 直接导入HttpRequestTask，不依赖sensor_data_service
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        
        # 创建一个简化的HttpRequestTask类用于测试
        from http_request_task import HttpRequestTask
        
        # 创建HTTP请求任务实例
        http_task = HttpRequestTask(
            target_url="http://localhost:5002/api/messages/",
            sensor_service=None  # 不使用传感器服务，使用模拟数据
        )
        
        print(f"任务ID: {http_task.task_id}")
        print(f"任务名称: {http_task.name}")
        print(f"任务描述: {http_task.description}")
        print(f"目标URL: {http_task.target_url}")
        print(f"请求超时: {http_task.request_timeout}秒")
        print(f"最大重试次数: {http_task.max_retries}")
        
        # 获取任务信息
        task_info = http_task.get_task_info()
        print("\n任务信息:")
        print(json.dumps(task_info, indent=2, ensure_ascii=False))
        
        # 测试传感器数据获取
        print("\n测试传感器数据获取:")
        sensor_data = http_task._get_current_sensor_data()
        print(json.dumps(sensor_data, indent=2, ensure_ascii=False))
        
        # 测试请求载荷构建
        print("\n测试请求载荷构建:")
        payload = http_task._build_request_payload(sensor_data)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        
        # 测试告警级别判断
        print("\n测试告警级别判断:")
        alert_info = http_task._determine_alert_level(sensor_data)
        print(json.dumps(alert_info, indent=2, ensure_ascii=False))
        
        print("\n=" * 60)
        print("基本功能测试完成！")
        print("=" * 60)
        
        return True
        
    except Exception as e:
        print(f"测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def test_task_status():
    """测试任务状态管理"""
    print("\n" + "=" * 60)
    print("任务状态管理测试")
    print("=" * 60)
    
    try:
        from http_request_task import HttpRequestTask
        
        # 创建任务实例
        http_task = HttpRequestTask()
        
        # 检查初始状态
        print("初始状态:")
        status_info = http_task.get_status_info()
        print(json.dumps(status_info, indent=2, ensure_ascii=False))
        
        # 模拟执行任务
        print("\n模拟执行任务...")
        result = http_task.execute()
        print(f"执行结果: {result}")
        
        # 检查执行后状态
        print("\n执行后状态:")
        status_info = http_task.get_status_info()
        print(json.dumps(status_info, indent=2, ensure_ascii=False))
        
        return True
        
    except Exception as e:
        print(f"状态测试失败: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主测试函数"""
    print("HTTP请求任务简化测试")
    print("时间:", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    # 执行测试
    test_results = []
    
    # 基本功能测试
    test_results.append(("基本功能测试", test_http_task_basic()))
    
    # 状态管理测试
    test_results.append(("状态管理测试", test_task_status()))
    
    # 输出测试总结
    print("\n" + "=" * 60)
    print("测试总结")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in test_results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
        else:
            failed += 1
    
    print(f"\n总计: {len(test_results)} 项测试")
    print(f"通过: {passed} 项")
    print(f"失败: {failed} 项")
    
    if failed == 0:
        print("\n🎉 所有测试通过！")
        return True
    else:
        print(f"\n❌ {failed} 项测试失败")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)