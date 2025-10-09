"""
HTTP请求任务测试脚本
测试HTTP请求任务的完整功能，包括错误处理和重试机制
"""

import sys
import os
import json
import time
from datetime import datetime

# 添加项目路径到sys.path
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# 导入相关模块
from http_request_task import HttpRequestTask
from sensor_data_service import SensorDataService

def test_http_request_basic():
    """测试基本HTTP请求功能"""
    print("=" * 60)
    print("测试1: 基本HTTP请求功能")
    print("=" * 60)
    
    # 创建HTTP请求任务
    http_task = HttpRequestTask()
    
    # 获取任务信息
    task_info = http_task.get_task_info()
    print("任务信息:")
    print(json.dumps(task_info, indent=2, ensure_ascii=False))
    
    # 执行任务
    print("\n执行HTTP请求任务...")
    result = http_task.execute()
    
    print("\n执行结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    return result["success"] if "success" in result else False

def test_http_request_with_sensor():
    """测试与传感器服务集成的HTTP请求"""
    print("\n" + "=" * 60)
    print("测试2: 与传感器服务集成的HTTP请求")
    print("=" * 60)
    
    # 创建传感器服务
    sensor_service = SensorDataService()
    
    # 创建HTTP请求任务并关联传感器服务
    http_task = HttpRequestTask()
    http_task.set_sensor_service(sensor_service)
    
    # 启动传感器服务（短时间）
    print("启动传感器服务...")
    sensor_service.start()
    time.sleep(3)  # 等待3秒收集数据
    
    # 执行HTTP请求
    print("执行HTTP请求任务...")
    result = http_task.execute()
    
    print("\n执行结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 停止传感器服务
    sensor_service.stop()
    
    return result["success"] if "success" in result else False

def test_http_request_error_handling():
    """测试HTTP请求的错误处理和重试机制"""
    print("\n" + "=" * 60)
    print("测试3: 错误处理和重试机制")
    print("=" * 60)
    
    # 创建HTTP请求任务，使用无效的URL
    http_task = HttpRequestTask(target_url="http://invalid-url-for-testing:9999/api/test")
    
    print("使用无效URL测试错误处理...")
    print(f"目标URL: {http_task.target_url}")
    
    # 执行任务（应该失败并重试）
    start_time = datetime.now()
    result = http_task.execute()
    end_time = datetime.now()
    
    execution_time = (end_time - start_time).total_seconds()
    
    print(f"\n执行时间: {execution_time:.2f}秒")
    print("执行结果:")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 验证重试机制
    if "http_result" in result and "attempt" in result["http_result"]:
        attempts = result["http_result"]["attempt"]
        print(f"\n重试验证: 执行了 {attempts} 次尝试")
        return attempts > 1  # 如果尝试次数大于1，说明重试机制工作
    
    return False

def test_http_url_update():
    """测试HTTP URL更新功能"""
    print("\n" + "=" * 60)
    print("测试4: HTTP URL更新功能")
    print("=" * 60)
    
    # 创建HTTP请求任务
    http_task = HttpRequestTask()
    
    # 获取初始URL
    initial_info = http_task.get_task_info()
    print(f"初始URL: {initial_info['target_url']}")
    
    # 更新URL
    new_url = "http://localhost:8080/api/test"
    http_task.set_target_url(new_url)
    
    # 验证URL更新
    updated_info = http_task.get_task_info()
    print(f"更新后URL: {updated_info['target_url']}")
    
    return updated_info['target_url'] == new_url

def test_sensor_data_formatting():
    """测试传感器数据格式化功能"""
    print("\n" + "=" * 60)
    print("测试5: 传感器数据格式化")
    print("=" * 60)
    
    # 创建HTTP请求任务
    http_task = HttpRequestTask()
    
    # 模拟传感器数据
    test_sensor_data = {
        'dissolved_oxygen': 6.5,
        'liquid_level': 950,
        'ph': 7.2,
        'ph_temperature': 25.5,
        'turbidity': 2.1,
        'turbidity_temperature': 25.8
    }
    
    print("测试传感器数据:")
    print(json.dumps(test_sensor_data, indent=2, ensure_ascii=False))
    
    # 构建请求载荷
    payload = http_task._build_request_payload(test_sensor_data)
    
    print("\n生成的请求载荷:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    
    # 验证载荷结构
    required_fields = ["message_type", "content", "priority", "metadata", "expires_at"]
    has_all_fields = all(field in payload for field in required_fields)
    
    print(f"\n载荷结构验证: {'通过' if has_all_fields else '失败'}")
    
    return has_all_fields

def test_alert_level_determination():
    """测试告警级别判断功能"""
    print("\n" + "=" * 60)
    print("测试6: 告警级别判断")
    print("=" * 60)
    
    # 创建HTTP请求任务
    http_task = HttpRequestTask()
    
    # 测试不同的传感器数据场景
    test_scenarios = [
        {
            "name": "正常数据",
            "data": {
                'dissolved_oxygen': 7.5,
                'ph': 7.0,
                'turbidity': 1.0
            }
        },
        {
            "name": "低溶解氧告警",
            "data": {
                'dissolved_oxygen': 4.5,
                'ph': 7.0,
                'turbidity': 1.0
            }
        },
        {
            "name": "pH异常告警",
            "data": {
                'dissolved_oxygen': 7.0,
                'ph': 9.0,
                'turbidity': 1.0
            }
        },
        {
            "name": "高浊度告警",
            "data": {
                'dissolved_oxygen': 7.0,
                'ph': 7.0,
                'turbidity': 15.0
            }
        }
    ]
    
    all_tests_passed = True
    
    for scenario in test_scenarios:
        print(f"\n测试场景: {scenario['name']}")
        print(f"传感器数据: {scenario['data']}")
        
        alert_info = http_task._determine_alert_level(scenario['data'])
        print(f"告警信息: {json.dumps(alert_info, indent=2, ensure_ascii=False)}")
        
        # 验证告警信息结构
        required_alert_fields = ["alert_type", "priority", "severity", "recommended_actions"]
        has_alert_fields = all(field in alert_info for field in required_alert_fields)
        
        if not has_alert_fields:
            all_tests_passed = False
            print("❌ 告警信息结构不完整")
        else:
            print("✅ 告警信息结构完整")
    
    return all_tests_passed

def run_comprehensive_test():
    """运行综合测试"""
    print("🚀 开始HTTP请求任务综合测试")
    print("=" * 80)
    
    test_results = []
    
    # 执行所有测试
    tests = [
        ("基本HTTP请求功能", test_http_request_basic),
        ("传感器数据格式化", test_sensor_data_formatting),
        ("告警级别判断", test_alert_level_determination),
        ("HTTP URL更新功能", test_http_url_update),
        ("错误处理和重试机制", test_http_request_error_handling),
        ("与传感器服务集成", test_http_request_with_sensor)
    ]
    
    for test_name, test_func in tests:
        try:
            print(f"\n🔍 执行测试: {test_name}")
            result = test_func()
            test_results.append((test_name, result, None))
            status = "✅ 通过" if result else "❌ 失败"
            print(f"测试结果: {status}")
        except Exception as e:
            test_results.append((test_name, False, str(e)))
            print(f"测试异常: ❌ {str(e)}")
    
    # 输出测试总结
    print("\n" + "=" * 80)
    print("📊 测试总结")
    print("=" * 80)
    
    passed_count = 0
    total_count = len(test_results)
    
    for test_name, result, error in test_results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if error:
            print(f"  错误信息: {error}")
        if result:
            passed_count += 1
    
    print(f"\n总体结果: {passed_count}/{total_count} 测试通过")
    
    if passed_count == total_count:
        print("🎉 所有测试通过！HTTP请求任务功能正常")
    else:
        print("⚠️  部分测试失败，请检查相关功能")
    
    return passed_count == total_count

def main():
    """主函数"""
    try:
        # 运行综合测试
        success = run_comprehensive_test()
        
        if success:
            print("\n🎯 HTTP请求任务已准备就绪，可以集成到定时任务系统中")
        else:
            print("\n⚠️  请修复测试中发现的问题后再集成")
            
    except KeyboardInterrupt:
        print("\n\n⏹️  测试被用户中断")
    except Exception as e:
        print(f"\n❌ 测试过程中发生异常: {str(e)}")

if __name__ == "__main__":
    main()