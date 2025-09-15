#!/usr/bin/env python3
"""
测试硕士和博士报名功能
"""
import requests
import json

# 测试数据
test_data_master = {
    "name": "测试硕士",
    "render": True,
    "uid": "1234567890",
    "major_id": None,  # 不提供教学计划号
    "major_name": "计算机科学与技术",
    "college_id": None,  # 不提供学院ID
    "college_name": None,  # 不提供学院名称
    "degree": 1,  # 硕士
    "grade": 25,
    "phone": "13800138000",
    "office_department_willing": 1,
    "competition_department_willing": 2,
    "activity_department_willing": 3,
    "research_department_willing": 4,
    "if_agree_to_be_reassigned": True,
    "if_be_member": True,
    "introduction": "我是测试硕士学生",
    "skill": "编程技能",
    "interview_time_slots": ["2024-09-15 14:00-15:00"]
}

test_data_phd = {
    "name": "测试博士",
    "render": True,
    "uid": "1234567891",
    "major_id": None,  # 不提供教学计划号
    "major_name": "软件工程",
    "college_id": None,  # 不提供学院ID
    "college_name": None,  # 不提供学院名称
    "degree": 2,  # 博士
    "grade": 25,
    "phone": "13800138001",
    "office_department_willing": 1,
    "competition_department_willing": 2,
    "activity_department_willing": 3,
    "research_department_willing": 4,
    "if_agree_to_be_reassigned": True,
    "if_be_member": True,
    "introduction": "我是测试博士学生",
    "skill": "研究技能",
    "interview_time_slots": ["2024-09-15 15:00-16:00"]
}

def test_recruit_confirm(data, degree_name):
    """测试报名确认接口"""
    url = "http://localhost:8000/api/recruit/recruit_confirm"
    
    print(f"\n=== 测试{degree_name}报名 ===")
    print(f"请求数据: {json.dumps(data, ensure_ascii=False, indent=2)}")
    
    try:
        response = requests.post(url, json=data)
        print(f"响应状态码: {response.status_code}")
        print(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            print(f"✅ {degree_name}报名成功")
        else:
            print(f"❌ {degree_name}报名失败")
            
    except Exception as e:
        print(f"❌ 请求异常: {e}")

if __name__ == "__main__":
    # 测试硕士报名
    test_recruit_confirm(test_data_master, "硕士")
    
    # 测试博士报名
    test_recruit_confirm(test_data_phd, "博士")
