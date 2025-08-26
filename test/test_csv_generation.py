#!/usr/bin/env python3
"""
测试CSV生成功能
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from routes.interview import generate_schedule_csv
from datetime import datetime

def test_csv_generation():
    """测试CSV生成功能"""
    
    # 模拟排班结果数据
    mock_schedule_results = [
        {
            'uid': '2024001',
            'name': '张三',
            'interview_date': datetime(2025, 8, 19, 20, 0),
            'display_slot': '周二 20:00-21:00 (本周)',
            'venue': '场地A',
            'candidate_index': 1,
            'total_in_slot': 2
        },
        {
            'uid': '2024002',
            'name': '李四',
            'interview_date': datetime(2025, 8, 19, 20, 0),
            'display_slot': '周二 20:00-21:00 (本周)',
            'venue': '场地A',
            'candidate_index': 2,
            'total_in_slot': 2
        },
        {
            'uid': '2024003',
            'name': '王五',
            'interview_date': datetime(2025, 8, 21, 19, 0),
            'display_slot': '周四 19:00-20:00 (本周)',
            'venue': '场地B',
            'candidate_index': 1,
            'total_in_slot': 1
        }
    ]
    
    try:
        # 生成CSV文件
        csv_file_path = generate_schedule_csv(mock_schedule_results, "2025-08-18")
        
        print(f"✅ CSV文件生成成功：{csv_file_path}")
        
        # 检查文件是否存在
        if os.path.exists(csv_file_path):
            print(f"✅ 文件存在，大小：{os.path.getsize(csv_file_path)} 字节")
            
            # 读取并显示文件内容
            with open(csv_file_path, 'r', encoding='utf-8-sig') as f:
                content = f.read()
                print("\n📄 CSV文件内容：")
                print(content)
        else:
            print("❌ 文件不存在")
            
    except Exception as e:
        print(f"❌ 生成CSV文件失败：{e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_csv_generation()
