#!/usr/bin/env python3
"""
测试数据生成脚本
用于批量创建recruit测试数据
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from unittest.mock import patch
from datetime import datetime, timedelta
import json
import random

from main import app
from models import Base, get_db

# 配置测试数据库
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_data.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 设置工作目录到后端根目录
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@patch('misc.dingtalk.send_dingtalk_message_to_user')
@patch('misc.auth.get_current_admin')
@patch('routes.admin.is_manager')
def generate_test_data(mock_manager, mock_admin, mock_dingtalk):
    """生成测试数据"""
    mock_dingtalk.return_value = True
    mock_admin.return_value = "00001"
    mock_manager.return_value = True
    
    # 清空现有数据并重新创建表
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    
    print("开始生成测试数据...")
    
    base_data = {
        "major_id": "20242112",
        "major_name": "计算机科学与技术",
        "college_id": "21",
        "college_name": "计算机科学与技术学院",
        "degree": 0,
        "grade": 24,
        "office_department_willing": 1,
        "competition_department_willing": 2,
        "activity_department_willing": 3,
        "research_department_willing": 4,
        "if_agree_to_be_reassigned": True,
        "if_be_member": True,
        "introduction": "我是一名计算机专业的学生，对编程有浓厚的兴趣，希望能在CSA中学习更多知识。",
        "skill": "Python, Java, 数据结构与算法"
    }
    
    time_slot_combinations = [
        ["周一 19:00-20:00", "周二 20:00-21:00"],
        ["周三 19:00-20:00", "周四 20:00-21:00"],
        ["周五 19:00-20:00", "周六 10:00-11:00"],
        ["周六 14:00-15:00", "周日 10:00-11:00"],
        ["周一 20:00-21:00", "周二 21:00-22:00"]
    ]
    
    created_recruits = []
    total_count = 20
    
    for i in range(total_count):
        recruit_data = base_data.copy()
        recruit_data.update({
            "name": f"测试学生{i+1:02d}",
            "render": i % 2 == 0,
            "uid": f"2024{i+1:03d}",
            "phone": f"13800138{i+1:03d}",
            "interview_time_slots": random.choice(time_slot_combinations)
        })
        
        response = client.post(f"/api/recruit/recruit_confirm", json=recruit_data)
        
        if response.status_code == 200:
            created_recruits.append(recruit_data)
            print(f"✓ 成功创建: {recruit_data['name']} ({recruit_data['uid']})")
        else:
            print(f"✗ 创建失败: {recruit_data['name']} - {response.status_code}")
            if response.status_code == 400:
                print(f"  错误详情: {response.json()}")
    
    print(f"\n总共成功创建了 {len(created_recruits)} 个纳新记录")
    return created_recruits

def clear_test_data():
    """清理测试数据"""
    print("清理测试数据...")
    Base.metadata.drop_all(bind=engine)
    print("测试数据清理完成！")

if __name__ == "__main__":
    import sys
    
    print("=== CSA Interview 测试数据生成器 ===")
    
    if len(sys.argv) > 1 and sys.argv[1] == "clear":
        clear_test_data()
    else:
        recruits = generate_test_data()
        print(f"测试数据生成完成！")
        print("\n使用方法:")
        print("  python generate_test_data.py      # 生成测试数据")
        print("  python generate_test_data.py clear # 清理测试数据")
