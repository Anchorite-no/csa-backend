from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta, timedelta
import json
import random
import csv
import io
import os
from collections import defaultdict
import re # Added for time format validation

from models import get_db
from models.recruit import Recruitment
from models.interview import Interview, InterviewTimeSlot
from models.admin import Admin
from models.user import User
from misc.auth import get_current_admin
from routes.admin import is_manager

router = APIRouter()


def get_interview_format_label(format_type: str) -> str:
    """获取面试形式的中文标签"""
    format_labels = {
        'one_to_one': '一对一',
        'one_to_many': '一对多',
        'many_to_many': '多对多'
    }
    return format_labels.get(format_type, '一对一')

def parse_time_slots(time_slots_json: str) -> List[str]:
    """解析面试时间段JSON字符串"""
    try:
        if not time_slots_json or time_slots_json.strip() == "":
            return []
        
        if isinstance(time_slots_json, str):
            parsed = json.loads(time_slots_json)
            if isinstance(parsed, list):
                return parsed
            else:
                return []
        elif isinstance(time_slots_json, list):
            return time_slots_json
        else:
            return []
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"解析面试时间段失败: {e}, 原始数据: {time_slots_json}")
        return []


def calculate_slot_date(base_date: str, time_slot: str, week_offset: int = 0) -> datetime:
    """根据基准日期和时间段计算具体面试日期"""
    try:
        base = datetime.strptime(base_date, "%Y-%m-%d")
        parts = time_slot.split()
        
        if len(parts) < 2:
            raise ValueError(f"时间段格式错误: {time_slot}")
            
        day_name = parts[0]  # 提取周几
        time_part = parts[1]  # 提取时间部分
        
        # 周几到数字的映射
        day_mapping = {
            "周一": 0, "周二": 1, "周三": 2, "周四": 3, 
            "周五": 4, "周六": 5, "周日": 6
        }
        
        target_day = day_mapping.get(day_name)
        if target_day is None:
            raise ValueError(f"无效的星期: {day_name}")
        
        current_day = base.weekday()
        
        # 计算需要加的天数
        days_to_add = target_day - current_day
        if days_to_add < 0:
            days_to_add += 7
        
        # 先计算本周的日期
        target_date = base + timedelta(days=days_to_add)
        
        # 然后加上周偏移
        if week_offset > 0:
            target_date = target_date + timedelta(days=week_offset * 7)
        
        # 验证时间格式
        if not re.match(r'^\d{1,2}:\d{2}-\d{1,2}:\d{2}$', time_part):
            raise ValueError(f"时间格式错误: {time_part}")
        
        start_time = time_part.split("-")[0]
        
        if not re.match(r'^\d{1,2}:\d{2}$', start_time):
            raise ValueError(f"开始时间格式错误: {start_time}")
        
        datetime_str = f"{target_date.strftime('%Y-%m-%d')} {start_time}:00"
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        print(f"计算面试日期失败: {e}, 基准日期: {base_date}, 时间段: {time_slot}")
        return datetime.strptime(base_date, "%Y-%m-%d")


def get_available_dates_for_slot(base_date: str, time_slot: str, num_weeks: int = 2) -> List[datetime]:
    """获取时间段在多个周内的可用日期"""
    dates = []
    for week in range(num_weeks):
        date = calculate_slot_date(base_date, time_slot, week)
        dates.append(date)
    return dates


def auto_schedule_algorithm(candidates: List[Recruitment], base_date: str, max_per_slot: int = 8) -> Dict[str, Any]:
    """
    自动排班算法 - 四阶段算法
    1. 第一轮：贪心算法，选择最早且人数不多于7的时间段
    2. 第二轮：负载均衡，将人数大于5的时间段中的人员重新分配
    3. 第三轮：多轮迭代聚类，优化人数小于4的时间段
    4. 第四轮：重新分配，将人数少于4的时间段中的人员分配到其他人数不多于7的时间段
    """
    # 数据验证
    if not candidates:
        return {
            'allocations': {},
            'schedule_results': [],
            'venue_assignments': {},
            'unscheduled': [],
            'time_slot_counts': {},
            'time_slot_instances': {}
        }
    
    # 验证基准日期格式
    try:
        datetime.strptime(base_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"无效的基准日期格式: {base_date}")
    
    # 1. 数据预处理 - 为每个时间段创建多个时间槽（本周和下周）
    time_slot_instances = {}  # 存储每个时间段的多个实例
    time_slot_counts = defaultdict(int)  # 每个时间槽的当前人数
    
    # 为每个时间段创建本周和下周的实例
    all_time_slots = set()
    valid_candidates = []
    
    for candidate in candidates:
        time_slots = parse_time_slots(candidate.interview_time_slots)
        if time_slots:  # 只处理有时间段偏好的面试者
            valid_candidates.append(candidate)
            for slot in time_slots:
                all_time_slots.add(slot)
    
    if not all_time_slots:
        return {
            'allocations': {},
            'schedule_results': [],
            'venue_assignments': {},
            'unscheduled': valid_candidates,
            'time_slot_counts': {},
            'time_slot_instances': {}
        }
    
    # 为每个时间段创建多个周的时间槽
    for slot in all_time_slots:
        slot_instances = []
        for week in range(2):  # 本周和下周
            date = calculate_slot_date(base_date, slot, week)
            slot_key = f"{slot}_week_{week}"
            slot_instances.append({
                'slot_key': slot_key,
                'original_slot': slot,
                'date': date,
                'week': week,
                'count': 0
            })
        time_slot_instances[slot] = slot_instances
    
    # 2. 第一轮：贪心算法 - 选择最早且人数不多于7的时间段
    allocations = defaultdict(list)  # 按时间槽键分配
    candidate_to_slot = {}  # 记录每个候选人的分配情况
    unscheduled = []
    
    # 按偏好数量排序（少的优先）
    candidates_with_preferences = []
    for candidate in valid_candidates:
        time_slots = parse_time_slots(candidate.interview_time_slots)
        candidates_with_preferences.append({
            'candidate': candidate,
            'preferences': time_slots,
            'preference_count': len(time_slots)
        })
    
    candidates_with_preferences.sort(key=lambda x: x['preference_count'])
    
    for candidate_info in candidates_with_preferences:
        candidate = candidate_info['candidate']
        preferences = candidate_info['preferences']
        
        # 按时间顺序排序偏好时间段
        sorted_preferences = sorted(preferences, key=lambda slot: 
            time_slot_instances[slot][0]['date'] if slot in time_slot_instances else datetime.max)
        
        # 找到最早且人数不多于7的时间段
        best_slot_instance = None
        for slot in sorted_preferences:
            if slot in time_slot_instances:
                # 先检查本周
                instance = time_slot_instances[slot][0]
                if instance['count'] < 7:
                    best_slot_instance = instance
                    break
                
                # 如果本周满了，检查下周
                instance = time_slot_instances[slot][1]
                if instance['count'] < 7:
                    best_slot_instance = instance
                    break
        
        # 如果找到合适的时间槽
        if best_slot_instance:
            allocations[best_slot_instance['slot_key']].append(candidate)
            best_slot_instance['count'] += 1
            time_slot_counts[best_slot_instance['slot_key']] = best_slot_instance['count']
            candidate_to_slot[candidate.uid] = best_slot_instance['slot_key']
        else:
            unscheduled.append(candidate)
    
    # 3. 第二轮：负载均衡 - 处理人数大于5的时间段
    def rebalance_overloaded_slots():
        max_iterations = 200
        iteration = 0
        while True:
            overloaded_slots = []
            for slot_key, candidates_list in allocations.items():
                if len(candidates_list) > 5:
                    overloaded_slots.append(slot_key)
            
            if not overloaded_slots:
                break
                
            changes_made = False
            for slot_key in overloaded_slots:
                # 重新检查当前时间段是否仍然超过5人
                if slot_key not in allocations or len(allocations[slot_key]) <= 5:
                    continue
                    
                candidates_list = allocations[slot_key].copy()
                target_count = 5  # 目标人数
                
                for candidate in candidates_list:
                    # 再次检查当前时间段是否仍然超过目标人数
                    if slot_key not in allocations or len(allocations[slot_key]) <= target_count:
                        break
                    
                    # 检查该候选人是否有其他可选的时间段
                    candidate_preferences = parse_time_slots(candidate.interview_time_slots)
                    alternative_slot = None
                    
                    for pref_slot in candidate_preferences:
                        if pref_slot in time_slot_instances:
                            # 检查本周和下周
                            for week in range(2):
                                instance = time_slot_instances[pref_slot][week]
                                if (instance['slot_key'] != slot_key and 
                                    instance['count'] < 5):
                                    alternative_slot = instance
                                    break
                            if alternative_slot:
                                break
                    
                    # 如果找到替代时间段，进行重新分配
                    if alternative_slot:
                        # 从原时间段移除
                        allocations[slot_key].remove(candidate)
                        # 更新原时间槽的计数
                        original_slot_name = slot_key.split('_week_')[0]
                        original_week = int(slot_key.split('_week_')[1])
                        time_slot_instances[original_slot_name][original_week]['count'] -= 1
                        time_slot_counts[slot_key] -= 1
                        
                        # 添加到新时间段
                        allocations[alternative_slot['slot_key']].append(candidate)
                        alternative_slot['count'] += 1
                        time_slot_counts[alternative_slot['slot_key']] = alternative_slot['count']
                        candidate_to_slot[candidate.uid] = alternative_slot['slot_key']
                        
                        changes_made = True
                        # 立即跳出内层循环，重新开始外层循环
                        break
            iteration += 1
            # 如果没有变化，停止迭代
            if not changes_made or iteration >= max_iterations - 1:
                break
    
    # 执行负载均衡
    rebalance_overloaded_slots()
    
    # 4. 第三轮：多轮迭代聚类 - 优化人数小于4的时间段
    def optimize_underloaded_slots():
        max_iterations = 200
        for iteration in range(max_iterations):
            changes_made = False
            
            # 找出所有人数小于4的时间段
            underloaded_slots = []
            for slot_key, candidates_list in allocations.items():
                if len(candidates_list) < 4:
                    underloaded_slots.append(slot_key)
            
            # 对于每个人数小于4的时间段
            for slot_key in underloaded_slots:
                # 重新获取当前时间段的人员列表（因为可能已经被修改）
                if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                    continue
                    
                candidates_list = allocations[slot_key].copy()
                
                for candidate in candidates_list:
                    # 再次检查当前时间段是否仍然小于4人
                    if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                        break
                        
                    candidate_preferences = parse_time_slots(candidate.interview_time_slots)
                    
                    # 找出该候选人可以去的其他人数小于4的时间段
                    alternative_slots = []
                    for pref_slot in candidate_preferences:
                        if pref_slot in time_slot_instances:
                            for week in range(2):
                                instance = time_slot_instances[pref_slot][week]
                                if (instance['slot_key'] != slot_key and 
                                    instance['count'] < 4):
                                    alternative_slots.append(instance)
                    
                    # 如果找到替代时间段，选择人数最多的
                    if alternative_slots:
                        best_alternative = max(alternative_slots, key=lambda x: x['count'])
                        
                        # 进行重新分配
                        allocations[slot_key].remove(candidate)
                        # 更新原时间槽的计数
                        original_slot_name = slot_key.split('_week_')[0]
                        original_week = int(slot_key.split('_week_')[1])
                        time_slot_instances[original_slot_name][original_week]['count'] -= 1
                        time_slot_counts[slot_key] -= 1
                        
                        allocations[best_alternative['slot_key']].append(candidate)
                        best_alternative['count'] += 1
                        time_slot_counts[best_alternative['slot_key']] = best_alternative['count']
                        candidate_to_slot[candidate.uid] = best_alternative['slot_key']
                        
                        changes_made = True
                        
                        # 立即跳出内层循环，重新开始外层循环，确保状态更新后重新评估
                        break
            
            # 如果没有变化，停止迭代
            if not changes_made:
                break
    
    # 执行聚类优化
    optimize_underloaded_slots()
    
    # 5. 第四轮：处理人数少于4的时间段 - 分配到其他人数不多于7的时间段
    def redistribute_underloaded_slots():
        max_iterations = 100
        for iteration in range(max_iterations):
            changes_made = False
            
            # 找出所有人数少于4的时间段
            underloaded_slots = []
            for slot_key, candidates_list in allocations.items():
                if len(candidates_list) < 4:
                    underloaded_slots.append(slot_key)
            
            # 对于每个人数少于4的时间段
            for slot_key in underloaded_slots:
                # 重新获取当前时间段的人员列表（因为可能已经被修改）
                if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                    continue
                    
                candidates_list = allocations[slot_key].copy()
                
                for candidate in candidates_list:
                    # 再次检查当前时间段是否仍然少于4人
                    if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                        break
                        
                    candidate_preferences = parse_time_slots(candidate.interview_time_slots)
                    
                    # 找出该候选人可以去的其他人数不多于7的时间段
                    alternative_slots = []
                    for pref_slot in candidate_preferences:
                        if pref_slot in time_slot_instances:
                            for week in range(2):
                                instance = time_slot_instances[pref_slot][week]
                                if (instance['slot_key'] != slot_key and 
                                    instance['count'] <= 7 and instance['count'] >= 4):
                                    alternative_slots.append(instance)
                    
                    # 如果找到替代时间段，选择人数最少的（优先填充人数少的时间段）
                    if alternative_slots:
                        best_alternative = min(alternative_slots, key=lambda x: x['count'])
                        
                        # 进行重新分配
                        allocations[slot_key].remove(candidate)
                        # 更新原时间槽的计数
                        original_slot_name = slot_key.split('_week_')[0]
                        original_week = int(slot_key.split('_week_')[1])
                        time_slot_instances[original_slot_name][original_week]['count'] -= 1
                        time_slot_counts[slot_key] -= 1
                        
                        allocations[best_alternative['slot_key']].append(candidate)
                        best_alternative['count'] += 1
                        time_slot_counts[best_alternative['slot_key']] = best_alternative['count']
                        candidate_to_slot[candidate.uid] = best_alternative['slot_key']
                        
                        changes_made = True
                        # 立即跳出内层循环，重新开始外层循环，确保状态更新后重新评估
                        break
            
            # 如果没有变化，停止迭代
            if not changes_made:
                break
    
    # 执行第四轮重新分配
    redistribute_underloaded_slots()
    
    # 4. 生成排班结果
    schedule_results = []
    venue_assignments = {}
    
    for slot_key, candidates_list in allocations.items():
        # 从slot_key中提取原始时间段和周信息
        # slot_key格式: "周一 19:00-20:00_week_0"
        parts = slot_key.split('_week_')
        original_slot = parts[0]
        week_num = int(parts[1])
        
        # 计算面试日期
        interview_date = calculate_slot_date(base_date, original_slot, week_num)
        
        # 分配场地 - 简化版本，只有一个场地
        venue = "场地A"
        venue_assignments[slot_key] = ["场地A"]
        
        # 为每个面试者创建排班记录
        for i, candidate in enumerate(candidates_list):
            # 添加周信息到时间段显示
            week_label = "本周" if week_num == 0 else "下周"
            display_slot = f"{original_slot} ({week_label})"
            
            schedule_results.append({
                'uid': candidate.uid,
                'name': candidate.name,
                'time_slot': slot_key,  # 使用slot_key而不是original_slot
                'display_slot': display_slot,
                'interview_date': interview_date,
                'venue': venue,
                'candidate_index': i + 1,
                'total_in_slot': len(candidates_list),
                'week': week_num
            })
    
    return {
        'allocations': allocations,
        'schedule_results': schedule_results,
        'venue_assignments': venue_assignments,
        'unscheduled': unscheduled,
        'time_slot_counts': dict(time_slot_counts),
        'time_slot_instances': time_slot_instances
    }


class InterviewSchedule(BaseModel):
    uid: str
    stage: str = Field(..., pattern="^(screening|first_round|second_round)$")
    interview_date: datetime
    interview_format: str = Field("one_to_one", pattern="^(one_to_one|one_to_many|many_to_many)$")
    interview_duration: int = 40  # 默认30分钟
    location: Optional[str] = None
    notes: Optional[str] = None
    status: str = Field("scheduled", pattern="^(scheduled|completed|cancelled)$")
    notification_sent: bool = False


class InterviewScheduleUpdate(BaseModel):
    interview_date: Optional[datetime] = None
    interview_format: Optional[str] = Field(None, pattern="^(one_to_one|one_to_many|many_to_many)$")
    interview_duration: Optional[int] = None
    location: Optional[str] = None
    notes: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(scheduled|completed|cancelled)$")
    notification_sent: Optional[bool] = None


class InterviewScheduleResponse(BaseModel):
    id: int
    uid: str
    stage: str
    interview_date: datetime
    interview_format: str
    interview_duration: int
    location: Optional[str]
    notes: Optional[str]
    status: str
    notification_sent: bool
    created_at: datetime
    updated_at: datetime


class AutoScheduleRequest(BaseModel):
    base_date: str  # 基准日期，格式：YYYY-MM-DD
    max_candidates_per_slot: int = 8  # 每个时间段最多面试者数量
    max_venues_per_slot: int = 2  # 每个时间段最多场地数量


class AutoScheduleResponse(BaseModel):
    success: bool
    message: str
    total_candidates: int
    scheduled_candidates: int
    unscheduled_candidates: int
    schedule_details: List[Dict[str, Any]]
    venue_assignments: Dict[str, List[str]]
    csv_file_path: Optional[str] = None  # CSV文件路径


@router.post("/schedule", tags=["interview"])
def create_interview_schedule(
    schedule_data: InterviewSchedule,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """创建面试排班"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    # 检查纳新记录是否存在
    recruit = db.query(Recruitment).filter(Recruitment.uid == schedule_data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="纳新记录未找到"
        )
    
    try:
        # 创建面试排班记录
        new_schedule = Interview(**schedule_data.dict())
        
        db.add(new_schedule)
        
        # 更新纳新记录的面试状态
        recruit.interview_status = schedule_data.stage
        recruit.interview_completed = False  # 设置为未完成状态
        
        db.commit()
        db.refresh(new_schedule)
        
        return new_schedule
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建面试排班时发生错误: {e}"
        )


@router.post("/auto-schedule", tags=["interview"])
def auto_schedule_interviews(
    request: AutoScheduleRequest,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """一键自动排班"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 1. 获取所有有面试时间段的纳新记录
        candidates = db.query(Recruitment).filter(
            Recruitment.interview_time_slots.isnot(None),
            Recruitment.interview_time_slots != "",
            Recruitment.interview_status.in_(["first_round", "second_round"])  # 排班一面和二面的
        ).all()
        
        print(f"找到 {len(candidates)} 个可排班的面试者")
        
        if not candidates:
            return AutoScheduleResponse(
                success=False,
                message="没有找到可排班的面试者",
                total_candidates=0,
                scheduled_candidates=0,
                unscheduled_candidates=0,
                schedule_details=[],
                venue_assignments={}
            )
        
        # 2. 运行自动排班算法
        algorithm_result = auto_schedule_algorithm(
            candidates, 
            request.base_date, 
            request.max_candidates_per_slot
        )
        print(algorithm_result['schedule_results'])
        
        print(f"算法结果: 成功排班 {len(algorithm_result['schedule_results'])} 人，未排班 {len(algorithm_result['unscheduled'])} 人")
        
        # 3. 创建面试排班记录
        created_schedules = []
        for schedule_info in algorithm_result['schedule_results']:
            # 检查是否已存在面试排班
            existing_schedule = db.query(Interview).filter(
                Interview.uid == schedule_info['uid']
            ).first()
            
            if existing_schedule:
                print(f"跳过已存在的排班: {schedule_info['uid']}")
                continue  # 跳过已存在的排班
            
            # 获取纳新者的当前面试阶段
            recruit = db.query(Recruitment).filter(Recruitment.uid == schedule_info['uid']).first()
            current_stage = recruit.interview_status if recruit else "first_round"
            
            # 解析时间段信息
            slot_parts = schedule_info['time_slot'].split('_week_')
            
            if len(slot_parts) != 2:
                print(f"Error: Invalid time_slot format: {schedule_info['time_slot']}")
                continue
                
            original_slot = slot_parts[0]  # 如 "周一 19:00-20:00"
            week_num = int(slot_parts[1])  # 0 或 1
            
            # 解析时间段
            slot_name_parts = original_slot.split(' ')
            if len(slot_name_parts) != 2:
                print(f"Error: Invalid original_slot format: {original_slot}")
                continue
                
            day_name = slot_name_parts[0]  # 如 "周一"
            time_range = slot_name_parts[1]  # 如 "19:00-20:00"
            
            time_parts = time_range.split('-')
            if len(time_parts) != 2:
                print(f"Error: Invalid time_range format: {time_range}")
                continue
                
            start_time, end_time = time_parts
            
            # 获取或创建时间段
            time_slot = get_or_create_time_slot(db, original_slot, day_name, start_time, end_time, week_num)
            
            # 创建新的面试排班记录
            new_schedule = Interview(
                uid=schedule_info['uid'],
                stage=current_stage,  # 使用当前面试阶段
                interview_date=schedule_info['interview_date'],
                interview_format="one_to_one",  # 默认一对一面试
                interview_duration=40,  # 默认40分钟
                location=schedule_info['venue'],
                notes=f"自动排班 - {schedule_info['time_slot']} - 第{schedule_info['candidate_index']}位",
                status="scheduled",
                notification_sent=False,
                time_slot_id=time_slot.id  # 关联时间段ID
            )
            
            db.add(new_schedule)
            created_schedules.append(new_schedule)
            
            # 更新时间段的人数统计
            time_slot.current_count += 1
            
            # 更新纳新记录的面试状态和完成状态
            recruit = db.query(Recruitment).filter(Recruitment.uid == schedule_info['uid']).first()
            if recruit:
                recruit.interview_status = current_stage
                recruit.interview_completed = False  # 设置为未完成状态
        
        # 4. 提交数据库事务
        db.commit()
        print(f"成功创建 {len(created_schedules)} 个面试排班记录")
        
        # 5. 统计结果
        total_candidates = len(candidates)
        scheduled_candidates = len(algorithm_result['schedule_results'])
        unscheduled_candidates = len(algorithm_result['unscheduled'])
        
        # 6. 生成排班详情
        schedule_details = []
        for schedule_info in algorithm_result['schedule_results']:
            schedule_details.append({
                'uid': schedule_info['uid'],
                'name': schedule_info['name'],
                'time_slot': schedule_info['time_slot'],
                'display_slot': schedule_info['display_slot'],
                'interview_date': schedule_info['interview_date'].isoformat(),
                'venue': schedule_info['venue'],
                'position': f"{schedule_info['candidate_index']}/{schedule_info['total_in_slot']}",
                'week': schedule_info['week']
            })
        
        # 7. 生成时间段统计
        time_slot_stats = []
        for time_slot, count in algorithm_result['time_slot_counts'].items():
            venues = algorithm_result['venue_assignments'].get(time_slot, [])
            time_slot_stats.append({
                'time_slot': time_slot,
                'candidate_count': count,
                'venues': venues
            })
        
        # 8. 生成CSV文件
        csv_file_path = generate_schedule_csv(algorithm_result['schedule_results'], request.base_date)
        
        return AutoScheduleResponse(
            success=True,
            message=f"自动排班完成！成功排班 {scheduled_candidates} 人，未排班 {unscheduled_candidates} 人",
            total_candidates=total_candidates,
            scheduled_candidates=scheduled_candidates,
            unscheduled_candidates=unscheduled_candidates,
            schedule_details=schedule_details,
            venue_assignments=algorithm_result['venue_assignments'],
            csv_file_path=csv_file_path
        )
        
    except Exception as e:
        db.rollback()
        print(f"自动排班失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"自动排班时发生错误: {e}"
        )


@router.get("/schedule-statistics", tags=["interview"])
def get_schedule_statistics(
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """获取排班统计信息"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 获取所有纳新记录
        total_recruits = db.query(Recruitment).count()
        
        # 获取有面试时间段的记录
        recruits_with_slots = db.query(Recruitment).filter(
            Recruitment.interview_time_slots.isnot(None),
            Recruitment.interview_time_slots != ""
        ).count()
        
        # 获取已排班的记录
        scheduled_recruits = db.query(Recruitment).filter(
            Recruitment.interview_status.in_(["screening", "first_round", "second_round"])
        ).count()
        
        # 获取未排班的记录
        unscheduled_recruits = recruits_with_slots - scheduled_recruits
        
        # 获取各时间段的排班统计
        time_slot_stats = {}
        interviews = db.query(Interview).filter(Interview.status == "scheduled").all()
        
        for interview in interviews:
            # 从面试日期反推时间段
            day_name = interview.interview_date.strftime("%A")
            day_mapping = {
                "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"
            }
            chinese_day = day_mapping.get(day_name, "未知")
            time_part = interview.interview_date.strftime("%H:%M")
            
            # 构建时间段字符串
            time_slot = f"{chinese_day} {time_part}"
            
            if time_slot not in time_slot_stats:
                time_slot_stats[time_slot] = {
                    'count': 0,
                    'venues': set()
                }
            
            time_slot_stats[time_slot]['count'] += 1
            if interview.location:
                time_slot_stats[time_slot]['venues'].add(interview.location)
        
        # 转换venues为列表
        for slot in time_slot_stats:
            time_slot_stats[slot]['venues'] = list(time_slot_stats[slot]['venues'])
        
        return {
            "total_recruits": total_recruits,
            "recruits_with_time_slots": recruits_with_slots,
            "scheduled_recruits": scheduled_recruits,
            "unscheduled_recruits": unscheduled_recruits,
            "time_slot_statistics": time_slot_stats
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取排班统计时发生错误: {e}"
        )


@router.get("/interviews/{uid}", tags=["interview"])
def get_interviews_by_uid(
    uid: str,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    # """获取指定用户的面试记录"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    interviews = db.query(Interview).filter(
        Interview.uid == uid
    ).order_by(Interview.stage, Interview.interview_date.desc()).all()
    
    return interviews





@router.get("/schedule", tags=["interview"])
def get_interview_schedules(
    page: int = 1,
    size: int = 100,  # 增加默认分页大小
    uid: Optional[str] = None,
    stage: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """获取面试排班列表"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    query = db.query(Interview)
    
    # 应用筛选条件
    if uid:
        query = query.filter(Interview.uid.like(f"%{uid}%"))
    if stage:
        query = query.filter(Interview.stage == stage)
    if status:
        query = query.filter(Interview.status == status)
    
    # 获取总数
    total = query.count()
    
    # 应用分页
    schedules = query.order_by(Interview.interview_date.asc()).offset((page - 1) * size).limit(size).all()
    
    # 构建响应数据
    result_list = []
    for schedule in schedules:
        result_list.append({
            "id": schedule.id,
            "uid": schedule.uid,
            "stage": schedule.stage,
            "interview_date": schedule.interview_date,
            "interview_format": schedule.interview_format,
            "interviewer": get_interview_format_label(schedule.interview_format),  # 添加面试官字段
            "interview_duration": schedule.interview_duration,
            "location": schedule.location,
            "notes": schedule.notes,
            "status": schedule.status,
            "notification_sent": schedule.notification_sent,
            "created_at": schedule.created_at,
            "updated_at": schedule.updated_at
        })
    
    return {
        "schedules": result_list,
        "total": total,
        "page": page,
        "size": size
    }


@router.put("/schedule/{schedule_id}", tags=["interview"])
def update_interview_schedule(
    schedule_id: int,
    schedule_data: InterviewScheduleUpdate,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """更新面试排班"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    schedule = db.query(Interview).filter(Interview.id == schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="面试排班记录未找到"
        )
    
    try:
        # 更新字段
        update_data = schedule_data.dict(exclude_unset=True)
        for field, value in update_data.items():
            setattr(schedule, field, value)
        
        schedule.updated_at = datetime.utcnow()
        
        db.commit()
        db.refresh(schedule)
        
        return schedule
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新面试排班时发生错误: {e}"
        )


@router.delete("/schedule/{schedule_id}", tags=["interview"])
def delete_interview_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """删除面试排班"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    schedule = db.query(Interview).filter(Interview.id == schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="面试排班记录未找到"
        )
    
    try:
        db.delete(schedule)
        db.commit()
        
        return {"message": "面试排班删除成功"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除面试排班时发生错误: {e}"
        )


@router.get("/recruit_time_slots/{uid}", tags=["interview"])
def get_recruit_time_slots(
    uid: str,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """获取纳新者的面试时间段信息"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == uid).first()
        if not recruit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="纳新记录未找到"
            )
        
        # 解析面试时间段
        time_slots = []
        if recruit.interview_time_slots:
            try:
                time_slots = json.loads(recruit.interview_time_slots)
            except json.JSONDecodeError:
                time_slots = []
        
        return {
            "uid": recruit.uid,
            "name": recruit.name,
            "time_slots": time_slots,
            "formatted_slots": format_time_slots(time_slots)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取面试时间段信息时发生错误: {e}"
        )


def format_time_slots(time_slots):
    """格式化时间段显示"""
    if not time_slots:
        return []
    
    formatted = []
    for slot_id in time_slots:
        # 解析时间段ID，格式如：周一_19, 周六_10
        if '_' in slot_id:
            day, hour = slot_id.split('_')
            time_str = f"{hour}:00-{int(hour)+1}:00"
            formatted.append(f"{day} {time_str}")
        else:
            formatted.append(slot_id)
    
    return formatted


@router.get("/recruit_info/{uid}", tags=["interview"])
def get_recruit_info(
    uid: str,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """获取纳新者基本信息"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == uid).first()
        if not recruit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="纳新记录未找到"
            )
        
        return {
            "uid": recruit.uid,
            "name": recruit.name,
            "phone": recruit.phone,
            "major_name": recruit.major_name,
            "college_name": recruit.college_name,
            "grade": recruit.grade,
            "degree": recruit.degree,
            "introduction": recruit.introduction,
            "skill": recruit.skill,
            "interview_status": recruit.interview_status,
            "interview_completed": recruit.interview_completed,
            "first_round_passed": recruit.first_round_passed,
            "second_round_passed": recruit.second_round_passed,
            "assigned_department": recruit.assigned_department
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取纳新者信息时发生错误: {e}"
        )


@router.get("/schedule_stats", tags=["interview"])
def get_schedule_statistics(
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    # """获取面试排班统计信息"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 各阶段排班数量
        screening_count = db.query(Interview).filter(Interview.stage == "screening").count()
        first_round_count = db.query(Interview).filter(Interview.stage == "first_round").count()
        second_round_count = db.query(Interview).filter(Interview.stage == "second_round").count()
        
        # 各状态数量
        scheduled_count = db.query(Interview).filter(Interview.status == "scheduled").count()
        completed_count = db.query(Interview).filter(Interview.status == "completed").count()
        cancelled_count = db.query(Interview).filter(Interview.status == "cancelled").count()
        
        # 今日面试数量
        from datetime import date
        today = date.today()
        today_count = db.query(Interview).filter(
            db.func.date(Interview.interview_date) == today
        ).count()
        
        return {
            "stage_counts": {
                "screening": screening_count,
                "first_round": first_round_count,
                "second_round": second_round_count
            },
            "status_counts": {
                "scheduled": scheduled_count,
                "completed": completed_count,
                "cancelled": cancelled_count
            },
            "today_count": today_count
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取面试排班统计信息时发生错误: {e}"
        )


class BatchInterviewUpdate(BaseModel):
    interview_ids: List[int]
    result: str = Field(..., pattern="^(pass|fail|pending|recommended)$")


@router.post("/batch_update_interviews", tags=["interview"])
def batch_update_interviews(
    data: BatchInterviewUpdate,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """批量更新面试结果"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        for interview_id in data.interview_ids:
            interview = db.query(Interview).filter(Interview.id == interview_id).first()
            if interview:
                interview.result = data.result
                interview.updated_at = datetime.utcnow()
        
        db.commit()
        return {"message": f"成功更新 {len(data.interview_ids)} 条面试记录"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量更新面试记录时发生错误: {e}"
        )


class ScheduleNotification(BaseModel):
    schedule_id: int
    custom_message: Optional[str] = None


@router.post("/send_schedule_notification", tags=["interview"])
def send_schedule_notification(
    notification_data: ScheduleNotification,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """发送面试排班通知"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 获取面试排班信息
        schedule = db.query(Interview).filter(Interview.id == notification_data.schedule_id).first()
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="面试排班记录未找到"
            )
        
        # 获取纳新者信息
        recruit = db.query(Recruitment).filter(Recruitment.uid == schedule.uid).first()
        if not recruit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="纳新记录未找到"
            )
        
        # 构建通知消息
        stage_labels = {
            "screening": "简历筛选",
            "first_round": "第一轮面试",
            "second_round": "第二轮面试"
        }
        
        stage_label = stage_labels.get(schedule.stage, schedule.stage)
        interview_date = schedule.interview_date.strftime("%Y年%m月%d日 %H:%M")
        
        title = f"CSA面试通知 - {stage_label}"
        description = f"亲爱的 {recruit.name} 同学！\n\n您的面试已安排如下：\n\n面试阶段：{stage_label}\n面试时间：{interview_date}\n面试形式：{get_interview_format_label(schedule.interview_format)}\n面试时长：{schedule.interview_duration}分钟"
        
        if schedule.location:
            description += f"\n面试地点：{schedule.location}"
        
        if schedule.notes:
            description += f"\n注意事项：{schedule.notes}"
        
        if notification_data.custom_message:
            description += f"\n\n补充说明：{notification_data.custom_message}"
        
        description += "\n\n请准时参加面试，祝您面试顺利！"
        
        # 发送钉钉通知
        from misc.dingtalk import send_dingtalk_message_to_user
        success = send_dingtalk_message_to_user(
            user_id=schedule.uid,
            title=title,
            description=description
        )
        
        if success:
            # 更新通知状态
            schedule.notification_sent = True
            schedule.updated_at = datetime.utcnow()
            db.commit()
            return {"message": "面试通知发送成功"}
        else:
            return {"message": "面试通知发送失败"}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"发送面试通知时发生错误: {e}"
        )


# @router.get("/debug/status", tags=["interview"])
# def get_debug_status(
#     db: Session = Depends(get_db),
#     # aid: str = Depends(get_current_admin),
# ):
#     """获取调试状态信息"""
#     # if not is_manager(db, aid):
#     #     raise HTTPException(
#     #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
#     #     )
    
#     try:
#         # 获取所有纳新记录
#         total_recruits = db.query(Recruitment).count()
        
#         # 获取有面试时间段的记录
#         recruits_with_slots = db.query(Recruitment).filter(
#             Recruitment.interview_time_slots.isnot(None),
#             Recruitment.interview_time_slots != ""
#         ).count()
        
#         # 获取各状态的记录数量
#         not_started = db.query(Recruitment).filter(
#             Recruitment.interview_status == "not_started"
#         ).count()
        
#         screening = db.query(Recruitment).filter(
#             Recruitment.interview_status == "screening"
#         ).count()
        
#         first_round = db.query(Recruitment).filter(
#             Recruitment.interview_status == "first_round"
#         ).count()
        
#         second_round = db.query(Recruitment).filter(
#             Recruitment.interview_status == "second_round"
#         ).count()
        
#         # 获取面试排班记录数量
#         total_schedules = db.query(Interview).count()
#         scheduled_schedules = db.query(Interview).filter(
#             Interview.status == "scheduled"
#         ).count()
        
#         # 获取一些示例数据
#         sample_recruits = db.query(Recruitment).limit(5).all()
#         sample_schedules = db.query(Interview).limit(5).all()
        
#         return {
#             "total_recruits": total_recruits,
#             "recruits_with_time_slots": recruits_with_slots,
#             "interview_status_counts": {
#                 "not_started": not_started,
#                 "screening": screening,
#                 "first_round": first_round,
#                 "second_round": second_round
#             },
#             "schedule_counts": {
#                 "total": total_schedules,
#                 "scheduled": scheduled_schedules
#             },
#             "sample_recruits": [
#                 {
#                     "uid": r.uid,
#                     "name": r.name,
#                     "interview_status": r.interview_status,
#                     "interview_time_slots": r.interview_time_slots
#                 } for r in sample_recruits
#             ],
#             "sample_schedules": [
#                 {
#                     "uid": s.uid,
#                     "stage": s.stage,
#                     "status": s.status,
#                     "interview_date": s.interview_date.isoformat() if s.interview_date else None
#                 } for s in sample_schedules
#             ]
#         }
        
#     except Exception as e:
#         raise HTTPException(
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
#             detail=f"获取调试状态时发生错误: {e}"
#         )


def generate_schedule_csv(schedule_results: List[Dict[str, Any]], base_date: str) -> str:
    """生成面试排班CSV文件"""
    # 创建uploads目录（如果不存在）
    uploads_dir = "uploads"
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    # 生成文件名
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interview_schedule_{timestamp}.csv"
    file_path = os.path.join(uploads_dir, filename)
    
    # 写入CSV文件
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = [
            '序号', '学号', '姓名', '面试阶段', '面试日期', '面试时间', 
            '时间段', '场地', '面试官', '面试时长(分钟)', '备注'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # 写入表头
        writer.writeheader()
        
        # 写入数据
        for i, schedule in enumerate(schedule_results, 1):
            # 格式化面试日期和时间
            interview_date = schedule['interview_date']
            if isinstance(interview_date, datetime):
                date_str = interview_date.strftime('%Y-%m-%d')
                time_str = interview_date.strftime('%H:%M')
            else:
                # 如果是字符串，尝试解析
                try:
                    dt = datetime.fromisoformat(interview_date.replace('Z', '+00:00'))
                    date_str = dt.strftime('%Y-%m-%d')
                    time_str = dt.strftime('%H:%M')
                except:
                    date_str = str(interview_date)
                    time_str = ""
            
            writer.writerow({
                '序号': i,
                '学号': schedule['uid'],
                '姓名': schedule['name'],
                '面试阶段': '简历筛选',  # 默认为简历筛选
                '面试日期': date_str,
                '面试时间': time_str,
                '时间段': schedule['display_slot'],
                '场地': schedule['venue'],
                '面试官': '待分配',
                '面试时长(分钟)': 40,
                '备注': f"第{schedule['candidate_index']}位，共{schedule['total_in_slot']}人"
            })
    
    return file_path


@router.get("/time-slots", tags=["interview"])
def get_interview_time_slots(
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """获取所有已排班的面试时间段"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 获取所有已排班的时间段
        time_slots = db.query(InterviewTimeSlot).filter(
            InterviewTimeSlot.is_active == True,
            InterviewTimeSlot.current_count > 0
        ).all()
        
        # 转换为前端需要的格式
        time_slots_list = []
        for slot in time_slots:
            time_slots_list.append({
                "id": slot.id,
                "name": slot.slot_name,
                "day_of_week": slot.day_of_week,
                "start_time": slot.start_time,
                "end_time": slot.end_time,
                "week_number": slot.week_number,
                "venue": slot.venue,
                "current_count": slot.current_count,
                "max_capacity": slot.max_capacity
            })
        
        # 按时间段名称排序
        time_slots_list.sort(key=lambda x: x["name"])
        
        return {
            "success": True,
            "time_slots": time_slots_list
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取面试时间段时发生错误: {e}"
        )


@router.get("/download-schedule-csv/{filename}", tags=["interview"])
def download_schedule_csv(
    filename: str,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """下载面试排班CSV文件"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    file_path = os.path.join("uploads", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在"
        )
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )


# 新增的面试管理功能

class CompleteInterviewRequest(BaseModel):
    time_slot: str  # 时间段，如 "周一 19:00-20:00 (本周)"
    week: int  # 周数，0为本周，1为下周


@router.post("/complete-interview", tags=["interview"])
def complete_interview(
    request: CompleteInterviewRequest,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """完成指定时间段的面试，将所有面试者的状态改为已完成"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 解析时间段
        print(f"接收到的时间段: {request.time_slot}")
        print(f"周数: {request.week}")
        
        # 如果时间段包含日期，去掉日期部分
        base_time_slot = request.time_slot
        if ' ' in base_time_slot:
            # 分割并重新组合，去掉日期部分
            parts = base_time_slot.split()
            if len(parts) >= 3:
                # 格式: "周一 08/22 19:00-20:00" -> "周一 19:00-20:00"
                base_time_slot = f"{parts[0]} {parts[2]}"
        
        print(f"处理后的基础时间段: {base_time_slot}")
        
        # 查找该时间段的所有面试记录
        interviews = db.query(Interview).filter(
            Interview.stage.in_(['first_round', 'second_round'])
        ).all()
        
        print(f"找到 {len(interviews)} 个面试记录")
        print(f"目标时间段: {base_time_slot}")
        print(f"目标周数: {request.week}")
        
        # 根据时间段和周数筛选
        target_interviews = []
        for interview in interviews:
            # 使用matchTimeSlotFromDate函数匹配时间段
            matched_slot = matchTimeSlotFromDate(interview.interview_date)
            print(f"面试 {interview.uid}: 日期={interview.interview_date}, 匹配时间段={matched_slot}")
            
            if matched_slot == base_time_slot:
                # 检查周数
                interview_date = interview.interview_date
                base_date = datetime.now().date()
                days_diff = (interview_date.date() - base_date).days
                interview_week = 1 if days_diff >= 7 else 0
                
                print(f"  周数检查: days_diff={days_diff}, interview_week={interview_week}")
                
                if interview_week == request.week:
                    target_interviews.append(interview)
                    print(f"  匹配成功，添加到目标列表")
                else:
                    print(f"  周数不匹配")
            else:
                print(f"  时间段不匹配")
        
        # 更新所有纳新者的排班状态为已完成，并发送面试完成通知
        for interview in target_interviews:
            # 获取纳新者信息
            recruit = db.query(Recruitment).filter(Recruitment.uid == interview.uid).first()
            if recruit:
                # 更新纳新者的面试完成状态
                recruit.interview_completed = True  # 当前阶段面试已完成
                
                # 发送面试完成通知
                stage_label = "第一轮" if interview.stage == 'first_round' else "第二轮"
                title = f"浙江大学学生网络空间安全协会（CSA）{stage_label}面试完成通知"
                description = f"""亲爱的 {recruit.name} 同学！

你的{stage_label}面试已经完成！

【面试信息】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：{stage_label}面试
• 面试时间：{interview.interview_date.strftime('%Y年%m月%d日 %H:%M')}
• 完成时间：{datetime.now().strftime('%Y年%m月%d日')}

【后续安排】
面试结果将在近期通过钉钉OA通知，请保持关注。

【重要提醒】
• 请继续关注钉钉OA消息
• 如有任何疑问，请及时联系我们
• 保持手机畅通

【联系方式】
如有任何疑问，请通过以下方式联系我们：
• 邮箱：csa@zju.edu.cn

感谢你参加CSA的面试，我们期待与你再次相见！

连心为网，筑梦为安！
浙江大学学生网络空间安全协会（CSA）"""
                
                try:
                    from misc.dingtalk import send_dingtalk_message_to_user
                    success = send_dingtalk_message_to_user(
                        user_id=recruit.uid,
                        title=title,
                        description=description
                    )
                    if success:
                        print(f"面试完成通知发送成功: {recruit.uid}")
                    else:
                        print(f"面试完成通知发送失败: {recruit.uid}")
                except Exception as e:
                    print(f"发送面试完成通知时出错: {e}")
        
        # 删除该场次的所有面试记录
        for interview in target_interviews:
            db.delete(interview)
        
        db.commit()
        
        return {
            "success": True,
            "message": f"成功完成 {len(target_interviews)} 个面试",
            "completed_count": len(target_interviews)
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"完成面试时发生错误: {e}"
        )


class PassInterviewRequest(BaseModel):
    uid: str
    round_type: str  # 'first_round' 或 'second_round'


@router.post("/pass-interview", tags=["interview"])
def pass_interview(
    request: PassInterviewRequest,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """面试通过处理"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 查找纳新者
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="纳新者不存在")
        
        if request.round_type == 'first_round':
            # 一面通过
            recruit.first_round_passed = True
            recruit.interview_status = 'second_round'  # 进入二面
            recruit.interview_completed = False  # 重置为未完成状态，准备二面
            
            # 更新面试记录状态
            interview = db.query(Interview).filter(
                Interview.uid == request.uid,
                Interview.stage == 'first_round'
            ).first()
            if interview:
                interview.result = 'pass'
                interview.status = 'completed'
            
        elif request.round_type == 'second_round':
            # 二面通过
            recruit.second_round_passed = True
            recruit.interview_status = 'completed'  # 面试完成
            recruit.interview_completed = True  # 面试完成
            
            # 更新面试记录状态
            interview = db.query(Interview).filter(
                Interview.uid == request.uid,
                Interview.stage == 'second_round'
            ).first()
            if interview:
                interview.result = 'pass'
                interview.status = 'completed'
            
            # 删除该纳新者的所有面试记录（从面试管理处删除）
            db.query(Interview).filter(Interview.uid == request.uid).delete()
        
        db.commit()
        
        return {
            "success": True,
            "message": f"{request.round_type}面试通过处理成功"
        }
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"面试通过处理时发生错误: {e}"
        )


def matchTimeSlotFromDate(interview_date: datetime) -> str:
    """从面试日期匹配时间段"""
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    day_of_week = interview_date.weekday()  # 0=周一, 1=周二, ..., 6=周日
    hour = interview_date.hour
    
    day_name = weekdays[day_of_week]
    
    # 根据小时数匹配时间段
    if hour >= 19 and hour < 20:
        return f"{day_name} 19:00-20:00"
    elif hour >= 20 and hour < 21:
        return f"{day_name} 20:00-21:00"
    elif hour >= 21 and hour < 22:
        return f"{day_name} 21:00-22:00"
    elif hour >= 10 and hour < 11:
        return f"{day_name} 10:00-11:00"
    elif hour >= 11 and hour < 12:
        return f"{day_name} 11:00-12:00"
    elif hour >= 14 and hour < 15:
        return f"{day_name} 14:00-15:00"
    elif hour >= 15 and hour < 16:
        return f"{day_name} 15:00-16:00"
    elif hour >= 16 and hour < 17:
        return f"{day_name} 16:00-17:00"
    
    return f"{day_name} {hour:02d}:00-{(hour+1):02d}:00"


def get_or_create_time_slot(db: Session, slot_name: str, day_of_week: str, start_time: str, end_time: str, week_number: int = 0) -> InterviewTimeSlot:
    """获取或创建时间段"""
    # 查找现有时间段
    time_slot = db.query(InterviewTimeSlot).filter(
        InterviewTimeSlot.slot_name == slot_name,
        InterviewTimeSlot.week_number == week_number
    ).first()
    
    if time_slot:
        return time_slot
    
    # 创建新时间段
    time_slot = InterviewTimeSlot(
        slot_name=slot_name,
        day_of_week=day_of_week,
        start_time=start_time,
        end_time=end_time,
        week_number=week_number,
        venue="场地A",
        max_capacity=10,
        current_count=0,
        is_active=True
    )
    
    db.add(time_slot)
    db.commit()
    db.refresh(time_slot)
    
    return time_slot


def create_interview_with_time_slot(db: Session, candidate, slot_key: str, base_date: datetime, current_stage: str) -> Interview:
    """创建面试记录并关联时间段"""
    # 解析时间段信息
    slot_parts = slot_key.split('_week_')
    original_slot = slot_parts[0]  # 如 "周一 19:00-20:00"
    week_num = int(slot_parts[1])  # 0 或 1
    
    # 解析时间段
    day_name = original_slot.split(' ')[0]  # 如 "周一"
    time_range = original_slot.split(' ')[1]  # 如 "19:00-20:00"
    start_time, end_time = time_range.split('-')
    
    # 计算面试日期
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    target_day_index = weekdays.index(day_name)
    
    # 计算目标日期
    base_weekday = base_date.weekday()
    days_ahead = target_day_index - base_weekday
    if days_ahead <= 0:  # 如果目标日期在本周已经过了，则安排在下周
        days_ahead += 7
    days_ahead += week_num * 7  # 加上周数偏移
    
    interview_date = base_date + timedelta(days=days_ahead)
    
    # 设置面试时间
    hour = int(start_time.split(':')[0])
    minute = int(start_time.split(':')[1])
    interview_date = interview_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    # 获取或创建时间段
    time_slot = get_or_create_time_slot(db, original_slot, day_name, start_time, end_time, week_num)
    
    # 创建面试记录
    new_schedule = Interview(
        uid=candidate.uid,
        stage=current_stage,
        interview_date=interview_date,
        interview_format="one_to_one",  # 默认一对一面试
        interview_duration=40,
        location=time_slot.venue,
        status='scheduled',
        time_slot_id=time_slot.id  # 关联时间段ID
    )
    
    db.add(new_schedule)
    
    # 更新时间段的人数统计
    time_slot.current_count += 1
    
    # 更新纳新记录的面试状态和完成状态
    recruit = db.query(Recruitment).filter(Recruitment.uid == candidate.uid).first()
    if recruit:
        recruit.interview_status = current_stage
        recruit.interview_completed = False  # 设置为未完成状态
    
    db.commit()
    
    return new_schedule


def update_time_slot_count(db: Session, time_slot_id: int, increment: bool = True):
    """更新时间段的人数统计"""
    time_slot = db.query(InterviewTimeSlot).filter(InterviewTimeSlot.id == time_slot_id).first()
    if time_slot:
        if increment:
            time_slot.current_count += 1
        else:
            time_slot.current_count = max(0, time_slot.current_count - 1)
        db.commit()



