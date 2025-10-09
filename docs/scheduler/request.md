  curl -X POST http://localhost:5002/api/messages/ \
  -H "Content-Type: application/json" \
  -d '{
    "message_type": "system_alert",
    "content": " 溶解氧饱和度: 7.33947  液位: 983 mm  pH: 7.38  温度(pH): 27.0 °C  浊度: 0.0 NTU  温度(浊度): 26.7 °C",图像数据：
    "priority": "urgent",
    "metadata": {
      "alert_type": "critical_oxygen_level",
      "pond_id": "pond_002",
      "current_values": {
        "dissolved_oxygen": 3.2,
        "threshold_min": 5.0,
        "deviation_percentage": -36
      },
      "recommended_actions": [
        "启动增氧设备",
        "检查水质过滤系统",
        "减少投饲量",
        "监控鱼类行为"
      ],
      "severity": "high",
      "auto_response_enabled": true,
      "notification_sent": true,
      "timestamp": "2025-09-25T14:53:00Z"
    },
    "expires_at": "2025-09-25T18:53:00Z"
  }' 