#!/usr/bin/env python3
"""
Interview测试数据生成脚本
向localhost:5173发送HTTP请求生成纳新数据和面试排班数据
"""

import requests
import json
from datetime import datetime, timedelta
import hashlib
import random

# 配置服务器地址
BASE_URL = "http://localhost:5173"

def generate_interview_test_data():
    """生成interview测试数据"""
    print("开始生成Interview测试数据...")
    print(f"目标服务器: {BASE_URL}")
    
    print()
    
    # 定义基础纳新数据模板
    base_recruit_data = {
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
    
    # 定义基础时间段选项
    weekday_times = [
        "周一 19:00-20:00", "周一 20:00-21:00", "周一 21:00-22:00",
        "周二 19:00-20:00", "周二 20:00-21:00", "周二 21:00-22:00",
        "周三 19:00-20:00", "周三 20:00-21:00", "周三 21:00-22:00",
        "周四 19:00-20:00", "周四 20:00-21:00", "周四 21:00-22:00",
        "周五 19:00-20:00", "周五 20:00-21:00", "周五 21:00-22:00"
    ]
    
    weekend_times = [
        "周六 10:00-11:00", "周六 11:00-12:00", "周六 14:00-15:00", 
        "周六 15:00-16:00", "周六 16:00-17:00", "周六 19:00-20:00",
        "周日 10:00-11:00", "周日 11:00-12:00", "周日 14:00-15:00",
        "周日 15:00-16:00", "周日 16:00-17:00", "周日 19:00-20:00"
    ]
    
    def generate_random_time_slots():
        """生成随机的时间段组合"""
        # 随机决定选择多少个时间段 (1-6个，更随机)
        num_slots = random.randint(4, 8)
        
        # 随机决定是否包含工作日和周末
        include_weekday = random.choice([True, False])
        include_weekend = random.choice([True, False])
        
        # 如果都不包含，至少选择一个
        if not include_weekday and not include_weekend:
            include_weekday = True
        
        available_times = []
        if include_weekday:
            available_times.extend(weekday_times)
        if include_weekend:
            available_times.extend(weekend_times)
        
        # 随机选择时间段，不重复
        selected_times = random.sample(available_times, min(num_slots, len(available_times)))
        
        # 按时间顺序排序
        day_order = {"周一": 1, "周二": 2, "周三": 3, "周四": 4, "周五": 5, "周六": 6, "周日": 7}
        selected_times.sort(key=lambda x: (day_order[x.split()[0]], x.split()[1]))
        
        return selected_times
    
    # 定义不同的技能组合
    skill_combinations = [
        "Python, Java, 数据结构与算法",
        "C++, 算法竞赛, 网络安全",
        "Web开发, JavaScript, 数据库",
        "机器学习, 深度学习, 数据分析",
        "系统安全, 逆向工程, 汇编语言",
        "网络协议, 渗透测试, 漏洞挖掘",
        "移动安全, Android开发, iOS开发",
        "云安全, Docker, Kubernetes",
        "区块链, 智能合约, 密码学",
        "物联网安全, 嵌入式系统, 硬件安全"
    ]
    
    # 定义不同的自我介绍
    introduction_templates = [
        "我是一名计算机专业的学生，对编程有浓厚的兴趣，希望能在CSA中学习更多知识。",
        "我对网络安全领域充满热情，参加过一些CTF比赛，希望能进一步提升技能。",
        "我擅长算法和数据结构，参加过ACM竞赛，希望能在CSA中学习更多安全知识。",
        "我对Web安全和渗透测试很感兴趣，自学了一些相关技术，希望能系统学习。",
        "我是一名软件工程专业的学生，对系统安全和逆向工程很感兴趣。",
        "我参加过一些网络安全比赛，对漏洞挖掘和利用有一定了解。",
        "我对移动安全和应用开发有研究，希望能学习更多安全防护技术。",
        "我是一名信息安全专业的学生，对密码学和区块链技术很感兴趣。",
        "我擅长网络编程，对网络协议和安全防护有深入研究。",
        "我对物联网安全和嵌入式系统很感兴趣，希望能学习相关安全技术。"
    ]
    
    # 生成纳新数据
    created_recruits = []
    # 随机生成15-40个纳新记录
    total_recruits = random.randint(10, 20)
    
    passwd = hashlib.sha256(b"ZJUCSA@2025_90381664123847").hexdigest()

    data = {
        "uid": "00001",
        "passwd": passwd
    }
    response = requests.post(f"{BASE_URL}/api/user/login/admin", json=data, timeout=10)
    print(response.json())
    admin_token = response.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {admin_token}"
    }

    for i in range(total_recruits):
        recruit_data = base_recruit_data.copy()
        recruit_data.update({
            "name": f"面试测试学生{i+1:02d}",
            "render": i % 2 == 0,  # 交替男女
            "uid": f"6666{i+1:03d}",  # 2024001, 2024002, ...
            "phone": f"13800138{i+1:03d}",
            "interview_time_slots": generate_random_time_slots(),
            "skill": random.choice(skill_combinations),
            "introduction": random.choice(introduction_templates)
        })

        try:
            response = requests.post(f"{BASE_URL}/api/recruit/recruit_confirm", json=recruit_data, timeout=10, headers=headers)
            
            if response.status_code == 200:
                created_recruits.append(recruit_data)
                print(f"✓ 成功创建纳新记录: {recruit_data['name']} ({recruit_data['uid']})")
            else:
                print(f"✗ 创建纳新记录失败: {recruit_data['name']} - {response.status_code}")
                if response.status_code == 400:
                    print(f"  错误详情: {response.json()}")
                elif response.status_code == 422:
                    print(f"  数据格式错误: {response.json()}")
        except requests.exceptions.ConnectionError:
            print(f"✗ 连接失败: 无法连接到 {BASE_URL}")
            print(f"  请确保服务器正在运行")
            break
        except requests.exceptions.Timeout:
            print(f"✗ 请求超时: {recruit_data['name']}")
        except Exception as e:
            print(f"✗ 请求失败: {recruit_data['name']} - {e}")
    
    print(f"\n=== 纳新数据生成完成 ===")
    print(f"总共成功创建了 {len(created_recruits)} 个纳新记录")
    
    # # 生成面试排班数据
    # if created_recruits:
    #     print(f"\n开始生成面试排班数据...")
        
    #     # 面试官列表
    #     interviewers = ["面试官A", "面试官B", "面试官C", "面试官D", "面试官E"]
        
    #     # 面试阶段
    #     stages = ["screening", "first_round", "second_round"]
        
    #     # 面试地点
    #     locations = ["会议室A", "会议室B", "会议室C", "线上会议室"]
        
    #     created_schedules = []
        
    #     # 随机为60%-90%的纳新记录创建面试排班
    #     num_schedules = random.randint(int(len(created_recruits) * 0.6), int(len(created_recruits) * 0.9))
    #     selected_recruits = random.sample(created_recruits, min(num_schedules, len(created_recruits)))
        
    #     for i, recruit in enumerate(selected_recruits):
    #         # 随机选择面试阶段
    #         stage = random.choice(stages)
            
    #         # 生成面试时间（未来1-7天内）
    #         interview_date = datetime.now() + timedelta(
    #             days=random.randint(1, 7), 
    #             hours=random.randint(9, 21)
    #         )
            
    #         # 构建面试排班数据
    #         schedule_data = {
    #             "uid": recruit["uid"],
    #             "stage": stage,
    #             "interview_date": interview_date.isoformat(),
    #             "interviewer": random.choice(interviewers),
    #             "interview_duration": random.choice([30, 40, 60]),
    #             "location": random.choice(locations),
    #             "notes": f"第{i+1}个面试排班，{recruit['name']}的{stage}面试",
    #             "status": random.choice(["scheduled", "completed", "cancelled"])
    #         }
            
    #         # 创建面试排班
    #         try:
    #             response = requests.post(f"{BASE_URL}/api/interview/schedule", json=schedule_data, timeout=10)
                
    #             if response.status_code == 200:
    #                 created_schedules.append(schedule_data)
    #                 print(f"✓ 成功创建面试排班: {recruit['name']} - {stage} - {interview_date.strftime('%m-%d %H:%M')}")
    #             else:
    #                 print(f"✗ 创建面试排班失败: {recruit['name']} - {response.status_code}")
    #                 if response.status_code == 400:
    #                     print(f"  错误详情: {response.json()}")
    #                 elif response.status_code == 401:
    #                     print(f"  认证失败，请确保已登录管理员账户")
    #                 elif response.status_code == 422:
    #                     print(f"  数据格式错误: {response.json()}")
    #         except requests.exceptions.ConnectionError:
    #             print(f"✗ 连接失败: 无法连接到 {BASE_URL}")
    #             print(f"  请确保服务器正在运行")
    #             break
    #         except requests.exceptions.Timeout:
    #             print(f"✗ 请求超时: {recruit['name']}")
    #         except Exception as e:
    #             print(f"✗ 请求失败: {recruit['name']} - {e}")
        
    #     print(f"\n=== 面试排班数据生成完成 ===")
    #     print(f"总共成功创建了 {len(created_schedules)} 个面试排班")
        
    #     # 统计信息
    #     print(f"\n=== 数据统计 ===")
    #     print(f"纳新记录: {len(created_recruits)} 个")
    #     print(f"面试排班: {len(created_schedules)} 个")
    #     print(f"目标服务器: {BASE_URL}")
        
    #     # 按阶段统计面试排班
    #     stage_stats = {}
    #     for schedule in created_schedules:
    #         stage = schedule['stage']
    #         stage_stats[stage] = stage_stats.get(stage, 0) + 1
        
    #     print(f"\n面试阶段分布:")
    #     for stage, count in stage_stats.items():
    #         stage_name = {
    #             'screening': '简历筛选',
    #             'first_round': '第一轮面试',
    #             'second_round': '第二轮面试'
    #         }.get(stage, stage)
    #         print(f"  {stage_name}: {count}个")
        
    #     return created_recruits, created_schedules
    
    return created_recruits, []

def check_server_status():
    """检查服务器状态"""
    try:
        # 尝试连接服务器根路径
        response = requests.get(f"{BASE_URL}/", timeout=5)
        print(f"✓ 服务器连接正常: {BASE_URL}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"✗ 无法连接到服务器: {BASE_URL}")
        print(f"  请确保服务器正在运行")
        return False
    except Exception as e:
        print(f"✗ 连接检查失败: {e}")
        return False

if __name__ == "__main__":
    print("=== CSA Interview 测试数据生成器 ===")
    print("向localhost:5173发送HTTP请求生成纳新数据和面试排班数据")
    print()
    
    # 检查服务器状态
    if not check_server_status():
        print("\n请确保服务器正在运行后再试")
        exit(1)
    
    print("\n请选择要生成的数据类型:")
    print("1. 生成纳新测试数据")
    print("2. 生成面试排班数据")
    print("3. 生成所有测试数据")
    
    try:
        choice = input("\n请输入选择 (1/2/3): ").strip()
        
        if choice == "1":
            recruits, _ = generate_interview_test_data()
            print(f"\n纳新数据生成完成！")
        elif choice == "2":
            # 只生成面试排班数据，需要先有一些纳新数据
            print("生成面试排班数据需要先有纳新数据...")
            recruits, schedules = generate_interview_test_data()
            print(f"\n面试排班数据生成完成！")
        elif choice == "3":
            recruits, schedules = generate_interview_test_data()
            print(f"\n所有测试数据生成完成！")
            print(f"纳新记录: {len(recruits)} 个")
            print(f"面试排班: {len(schedules)} 个")
        else:
            print("无效选择，请重新运行脚本")
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
    except Exception as e:
        print(f"\n操作失败: {e}")
    
    print(f"\n测试数据生成完成！")
    print(f"目标服务器: {BASE_URL}")
