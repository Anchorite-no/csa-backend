#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models.recruit import Recruitment
from routes.interview import auto_schedule_algorithm

def test_new_scheduling_logic():
    """测试新的排序逻辑"""
    print("测试新的排序逻辑...")
    
    # 创建测试数据
    candidates = []
    
    # 创建有不同时间段数量的面试者
    test_cases = [
        # (uid, name, time_slots, expected_priority)
        ("2024001", "面试者01", ["周一 19:00-20:00"], 1),  # 1个时间段，优先级最低
        ("2024002", "面试者02", ["周一 19:00-20:00", "周二 19:00-20:00"], 2),  # 2个时间段
        ("2024003", "面试者03", ["周一 19:00-20:00", "周二 19:00-20:00", "周三 19:00-20:00"], 3),  # 3个时间段
        ("2024004", "面试者04", ["周一 19:00-20:00", "周二 19:00-20:00", "周三 19:00-20:00", "周四 19:00-20:00"], 4),  # 4个时间段
        ("2024005", "面试者05", ["周二 19:00-20:00"], 1),  # 1个时间段，但时间段不同
        ("2024006", "面试者06", ["周二 19:00-20:00", "周三 19:00-20:00"], 2),  # 2个时间段，但时间段不同
    ]
    
    for uid, name, time_slots, expected_priority in test_cases:
        candidate = Recruitment()
        candidate.uid = uid
        candidate.name = name
        candidate.interview_time_slots = str(time_slots)
        candidates.append(candidate)
    
    # 运行算法
    base_date = "2025-08-18"  # 周一
    result = auto_schedule_algorithm(candidates, base_date, max_per_slot=8)
    
    print(f"\n算法结果:")
    print(f"总面试者: {len(candidates)}")
    print(f"成功排班: {len(result['schedule_results'])}")
    print(f"未排班: {len(result['unscheduled'])}")
    
    # 分析排班结果
    print(f"\n排班详情:")
    for i, schedule in enumerate(result['schedule_results']):
        print(f"{i+1}. {schedule['name']} ({schedule['uid']}) - {schedule['display_slot']} - {schedule['venue']}")
    
    # 验证排序逻辑
    print(f"\n验证排序逻辑:")
    print("期望的排序优先级（按时间段数量，然后按最早时间段）:")
    for uid, name, time_slots, expected_priority in test_cases:
        print(f"- {name}: {len(time_slots)}个时间段")
    
    # 检查是否有未排班的
    if result['unscheduled']:
        print(f"\n未排班的面试者:")
        for candidate in result['unscheduled']:
            print(f"- {candidate.name} ({candidate.uid})")
    
    return result

if __name__ == "__main__":
    test_new_scheduling_logic()
