#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from routes.interview import calculate_slot_date

def test_date_calculation():
    """测试日期计算是否正确"""
    print("测试日期计算...")
    
    # 设置基准日期为2025年8月18日（周一）
    base_date = "2025-08-18"
    print(f"基准日期: {base_date}")
    
    # 测试时间段
    test_slots = [
        "周一 19:00-20:00",
        "周二 20:00-21:00", 
        "周三 21:00-22:00",
        "周四 19:00-20:00",
        "周五 20:00-21:00",
        "周六 10:00-11:00",
        "周日 14:00-15:00"
    ]
    
    for slot in test_slots:
        print(f"\n时间段: {slot}")
        
        # 计算本周的日期
        week0_date = calculate_slot_date(base_date, slot, 0)
        print(f"  本周: {week0_date.strftime('%Y-%m-%d %H:%M')}")
        
        # 计算下周的日期
        week1_date = calculate_slot_date(base_date, slot, 1)
        print(f"  下周: {week1_date.strftime('%Y-%m-%d %H:%M')}")
        
        # 验证日期差是否为7天
        date_diff = (week1_date - week0_date).days
        print(f"  日期差: {date_diff}天")
        
        if date_diff != 7:
            print(f"  ❌ 错误: 日期差应该是7天，实际是{date_diff}天")
        else:
            print(f"  ✅ 正确: 日期差是7天")

if __name__ == "__main__":
    test_date_calculation()
