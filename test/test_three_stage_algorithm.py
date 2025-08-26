#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from models.recruit import Recruitment
from routes.interview import auto_schedule_algorithm
import json

def test_three_stage_algorithm():
    """测试新的三阶段排班算法"""
    print("测试新的三阶段排班算法...")
    
    # 创建测试数据
    candidates = []
    
    # 创建有不同时间段数量的面试者
    test_cases = [
        # (uid, name, time_slots, expected_priority)
        ("2024001", "面试者01", ["周一 19:00-20:00"], 1),  # 1个时间段
        ("2024002", "面试者02", ["周一 19:00-20:00", "周二 19:00-20:00"], 2),  # 2个时间段
        ("2024003", "面试者03", ["周一 19:00-20:00", "周二 19:00-20:00", "周三 19:00-20:00"], 3),  # 3个时间段
        ("2024004", "面试者04", ["周一 19:00-20:00", "周二 19:00-20:00", "周三 19:00-20:00", "周四 19:00-20:00"], 4),  # 4个时间段
        ("2024005", "面试者05", ["周二 19:00-20:00", "周三 19:00-20:00"], 2),
        ("2024006", "面试者06", ["周二 19:00-20:00", "周三 19:00-20:00", "周四 19:00-20:00"], 3),
        ("2024007", "面试者07", ["周三 19:00-20:00", "周四 19:00-20:00"], 2),
        ("2024008", "面试者08", ["周四 19:00-20:00", "周五 19:00-20:00"], 2),
        ("2024009", "面试者09", ["周五 19:00-20:00", "周六 10:00-11:00"], 2),
        ("2024010", "面试者10", ["周六 10:00-11:00", "周日 10:00-11:00"], 2),
        ("2024011", "面试者11", ["周一 20:00-21:00", "周二 20:00-21:00"], 2),
        ("2024012", "面试者12", ["周二 20:00-21:00", "周三 20:00-21:00"], 2),
        ("2024013", "面试者13", ["周三 20:00-21:00", "周四 20:00-21:00"], 2),
        ("2024014", "面试者14", ["周四 20:00-21:00", "周五 20:00-21:00"], 2),
        ("2024015", "面试者15", ["周五 20:00-21:00", "周六 11:00-12:00"], 2),
        ("2024016", "面试者16", ["周六 11:00-12:00", "周日 11:00-12:00"], 2),
        ("2024017", "面试者17", ["周一 21:00-22:00", "周二 21:00-22:00"], 2),
        ("2024018", "面试者18", ["周二 21:00-22:00", "周三 21:00-22:00"], 2),
        ("2024019", "面试者19", ["周三 21:00-22:00", "周四 21:00-22:00"], 2),
        ("2024020", "面试者20", ["周四 21:00-22:00", "周五 21:00-22:00"], 2),
        ("2024021", "面试者21", ["周五 21:00-22:00", "周六 14:00-15:00"], 2),
        ("2024022", "面试者22", ["周六 14:00-15:00", "周日 14:00-15:00"], 2),
        ("2024023", "面试者23", ["周六 15:00-16:00", "周日 15:00-16:00"], 2),
        ("2024024", "面试者24", ["周六 16:00-17:00", "周日 16:00-17:00"], 2),
        ("2024025", "面试者25", ["周六 19:00-20:00", "周日 19:00-20:00"], 2),
    ]
    
    for uid, name, time_slots, expected_priority in test_cases:
        candidate = Recruitment(
            uid=uid,
            name=name,
            interview_time_slots=json.dumps(time_slots, ensure_ascii=False)
        )
        candidates.append(candidate)
    
    # 设置基准日期为2025年8月18日（周一）
    base_date = "2025-08-18"
    
    print(f"测试数据：{len(candidates)}个面试者")
    print(f"基准日期：{base_date}")
    
    # 执行算法
    try:
        result = auto_schedule_algorithm(candidates, base_date)
        
        # 分析结果
        print("\n=== 算法执行结果 ===")
        print(f"成功排班：{len(result['schedule_results'])}人")
        print(f"未排班：{len(result['unscheduled'])}人")
        
        # 分析时间段分布
        slot_counts = {}
        for schedule in result['schedule_results']:
            slot_key = schedule['display_slot']
            if slot_key not in slot_counts:
                slot_counts[slot_key] = 0
            slot_counts[slot_key] += 1
        
        print("\n=== 时间段分布 ===")
        for slot, count in sorted(slot_counts.items()):
            print(f"{slot}: {count}人")
        
        # 分析算法效果
        print("\n=== 算法效果分析 ===")
        overloaded_slots = [slot for slot, count in slot_counts.items() if count > 5]
        underloaded_slots = [slot for slot, count in slot_counts.items() if count < 4]
        
        print(f"人数大于5的时间段：{len(overloaded_slots)}个")
        if overloaded_slots:
            for slot in overloaded_slots:
                print(f"  - {slot}: {slot_counts[slot]}人")
        
        print(f"人数小于4的时间段：{len(underloaded_slots)}个")
        if underloaded_slots:
            for slot in underloaded_slots:
                print(f"  - {slot}: {slot_counts[slot]}人")
        
        # 保存详细结果
        with open('test/three_stage_results.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"\n详细结果已保存到：test/three_stage_results.json")
        
        return result
        
    except Exception as e:
        print(f"算法执行失败：{e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    test_three_stage_algorithm()
