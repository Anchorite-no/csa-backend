#!/usr/bin/env python3
"""
测试一键排班功能
"""

import requests
import json
from datetime import datetime

# 配置
BASE_URL = "http://localhost:8000"

def test_auto_schedule():
    """测试一键排班功能"""
    print("=== 测试一键排班功能 ===")
    
    # 1. 管理员登录
    login_data = {
        "uid": "00001",
        "passwd": "240be518fabd2724ddb6f04eeb1da5967448d7e831c08c8fa822809f74c720a9"
    }
    
    try:
        login_response = requests.post(f"{BASE_URL}/api/user/login/admin", json=login_data)
        if login_response.status_code != 200:
            print(f"❌ 登录失败: {login_response.status_code}")
            return
        
        admin_token = login_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {admin_token}"}
        print("✅ 管理员登录成功")
        
    except Exception as e:
        print(f"❌ 登录异常: {e}")
        return
    
    # 2. 获取排班统计
    try:
        stats_response = requests.get(f"{BASE_URL}/api/interview/schedule-statistics", headers=headers)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"\n📊 当前排班统计:")
            print(f"  总面试者: {stats['total_recruits']}")
            print(f"  有时间段选择: {stats['recruits_with_time_slots']}")
            print(f"  已排班: {stats['scheduled_recruits']}")
            print(f"  未排班: {stats['unscheduled_recruits']}")
        else:
            print(f"❌ 获取统计失败: {stats_response.status_code}")
            
    except Exception as e:
        print(f"❌ 获取统计异常: {e}")
    
    # 3. 执行一键排班
    auto_schedule_data = {
        "base_date": datetime.now().strftime("%Y-%m-%d"),
        "max_candidates_per_slot": 8
    }
    
    try:
        print(f"\n🚀 开始一键排班...")
        print(f"  基准日期: {auto_schedule_data['base_date']}")
        print(f"  每时间段最大人数: {auto_schedule_data['max_candidates_per_slot']}")
        
        schedule_response = requests.post(
            f"{BASE_URL}/api/interview/auto-schedule", 
            json=auto_schedule_data, 
            headers=headers
        )
        
        if schedule_response.status_code == 200:
            result = schedule_response.json()
            print(f"\n✅ 排班成功!")
            print(f"  消息: {result['message']}")
            print(f"  总面试者: {result['total_candidates']}")
            print(f"  成功排班: {result['scheduled_candidates']}")
            print(f"  未排班: {result['unscheduled_candidates']}")
            
            # 显示排班详情
            if result['schedule_details']:
                print(f"\n📋 排班详情:")
                for detail in result['schedule_details'][:5]:  # 只显示前5个
                    print(f"  {detail['name']} ({detail['uid']}) - {detail['time_slot']} - {detail['venue']}")
                if len(result['schedule_details']) > 5:
                    print(f"  ... 还有 {len(result['schedule_details']) - 5} 个排班记录")
            
            # 显示场地分配
            if result['venue_assignments']:
                print(f"\n🏢 场地分配:")
                for time_slot, venues in result['venue_assignments'].items():
                    print(f"  {time_slot}: {', '.join(venues)}")
                    
        else:
            print(f"❌ 排班失败: {schedule_response.status_code}")
            print(f"  错误: {schedule_response.text}")
            
    except Exception as e:
        print(f"❌ 排班异常: {e}")
    
    # 4. 再次获取排班统计
    try:
        print(f"\n📊 排班后统计:")
        stats_response = requests.get(f"{BASE_URL}/api/interview/schedule-statistics", headers=headers)
        if stats_response.status_code == 200:
            stats = stats_response.json()
            print(f"  总面试者: {stats['total_recruits']}")
            print(f"  有时间段选择: {stats['recruits_with_time_slots']}")
            print(f"  已排班: {stats['scheduled_recruits']}")
            print(f"  未排班: {stats['unscheduled_recruits']}")
            
            # 显示时间段统计
            if stats['time_slot_statistics']:
                print(f"\n⏰ 时间段统计:")
                for time_slot, info in stats['time_slot_statistics'].items():
                    venues = ', '.join(info['venues']) if info['venues'] else '无'
                    print(f"  {time_slot}: {info['count']}人 - 场地: {venues}")
        else:
            print(f"❌ 获取统计失败: {stats_response.status_code}")
            
    except Exception as e:
        print(f"❌ 获取统计异常: {e}")

if __name__ == "__main__":
    test_auto_schedule()
