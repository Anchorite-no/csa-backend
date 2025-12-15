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
import re 

from models import get_db
from models.recruit import Recruitment
from models.interview import Interview, InterviewTimeSlot
from models.admin import Admin
from models.user import User
from misc.auth import get_current_admin
from routes.admin import is_manager

router = APIRouter()


def get_interview_format_label(format_type: str) -> str:
    format_labels = {
        'one_to_one': '一对一',
        'one_to_many': '一对多',
        'many_to_many': '多对多'
    }
    return format_labels.get(format_type, '一对一')

def parse_time_slots(time_slots_json: str) -> List[str]:
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
        print(f"Failed to parse interview time slots: {e}, raw data: {time_slots_json}")
        return []


def calculate_slot_date(base_date: str, time_slot: str, week_offset: int = 0) -> datetime:
    try:
        base = datetime.strptime(base_date, "%Y-%m-%d")
        parts = time_slot.split()
        
        if len(parts) < 2:
            raise ValueError(f"时间段格式错误: {time_slot}")
            
        day_name = parts[0]
        time_part = parts[1]
        
        day_mapping = {
            "周一": 0, "周二": 1, "周三": 2, "周四": 3, 
            "周五": 4, "周六": 5, "周日": 6
        }
        
        target_day = day_mapping.get(day_name)
        if target_day is None:
            raise ValueError(f"无效的星期: {day_name}")
        
        current_day = base.weekday()
        
        days_to_add = target_day - current_day
        if days_to_add < 0:
            days_to_add += 7
        
        target_date = base + timedelta(days=days_to_add)
        
        if week_offset > 0:
            target_date = target_date + timedelta(days=week_offset * 7)
        
        if not re.match(r'^\d{1,2}:\d{2}-\d{1,2}:\d{2}$', time_part):
            raise ValueError(f"时间格式错误: {time_part}")
        
        start_time = time_part.split("-")[0]
        
        if not re.match(r'^\d{1,2}:\d{2}$', start_time):
            raise ValueError(f"开始时间格式错误: {start_time}")
        
        datetime_str = f"{target_date.strftime('%Y-%m-%d')} {start_time}:00"
        return datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        
    except Exception as e:
        print(f"Failed to calculate interview date: {e}, base date: {base_date}, time slot: {time_slot}")
        return datetime.strptime(base_date, "%Y-%m-%d")


def get_available_dates_for_slot(base_date: str, time_slot: str, num_weeks: int = 2) -> List[datetime]:
    dates = []
    for week in range(num_weeks):
        date = calculate_slot_date(base_date, time_slot, week)
        dates.append(date)
    return dates


def auto_schedule_algorithm(candidates: List[Recruitment], base_date: str, max_per_slot: int = 8) -> Dict[str, Any]:
    if not candidates:
        return {
            'allocations': {},
            'schedule_results': [],
            'venue_assignments': {},
            'unscheduled': [],
            'time_slot_counts': {},
            'time_slot_instances': {}
        }
    
    try:
        datetime.strptime(base_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"无效的基准日期格式: {base_date}")
    
    
    time_slot_instances = {}  
    time_slot_counts = defaultdict(int)  
    
    all_time_slots = set()
    valid_candidates = []
    
    for candidate in candidates:
        time_slots = parse_time_slots(candidate.interview_time_slots)
        if time_slots: 
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
    
    
    allocations = defaultdict(list) 
    candidate_to_slot = {} 
    unscheduled = []
    
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
        
        sorted_preferences = sorted(preferences, key=lambda slot: 
            time_slot_instances[slot][0]['date'] if slot in time_slot_instances else datetime.max)
        
        
        best_slot_instance = None
        for slot in sorted_preferences:
            if slot in time_slot_instances:
                instance = time_slot_instances[slot][0]
                if instance['count'] < 7:
                    best_slot_instance = instance
                    break
                
                instance = time_slot_instances[slot][1]
                if instance['count'] < 7:
                    best_slot_instance = instance
                    break
        
        if best_slot_instance:
            allocations[best_slot_instance['slot_key']].append(candidate)
            best_slot_instance['count'] += 1
            time_slot_counts[best_slot_instance['slot_key']] = best_slot_instance['count']
            candidate_to_slot[candidate.uid] = best_slot_instance['slot_key']
        else:
            unscheduled.append(candidate)
    
    
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
                
                if slot_key not in allocations or len(allocations[slot_key]) <= 5:
                    continue
                    
                candidates_list = allocations[slot_key].copy()
                target_count = 5  # 目标人数
                
                for candidate in candidates_list:
                    if slot_key not in allocations or len(allocations[slot_key]) <= target_count:
                        break
                    
                    candidate_preferences = parse_time_slots(candidate.interview_time_slots)
                    alternative_slot = None
                    
                    for pref_slot in candidate_preferences:
                        if pref_slot in time_slot_instances:
                            for week in range(2):
                                instance = time_slot_instances[pref_slot][week]
                                if (instance['slot_key'] != slot_key and 
                                    instance['count'] < 5):
                                    alternative_slot = instance
                                    break
                            if alternative_slot:
                                break
                    
                    if alternative_slot:
                        allocations[slot_key].remove(candidate)
                        original_slot_name = slot_key.split('_week_')[0]
                        original_week = int(slot_key.split('_week_')[1])
                        time_slot_instances[original_slot_name][original_week]['count'] -= 1
                        time_slot_counts[slot_key] -= 1
                        
                        allocations[alternative_slot['slot_key']].append(candidate)
                        alternative_slot['count'] += 1
                        time_slot_counts[alternative_slot['slot_key']] = alternative_slot['count']
                        candidate_to_slot[candidate.uid] = alternative_slot['slot_key']
                        
                        changes_made = True
                        break
            iteration += 1
            if not changes_made or iteration >= max_iterations - 1:
                break
    
    rebalance_overloaded_slots()
    
    
    def optimize_underloaded_slots():
        max_iterations = 200
        for iteration in range(max_iterations):
            changes_made = False
            
            
            underloaded_slots = []
            for slot_key, candidates_list in allocations.items():
                if len(candidates_list) < 4:
                    underloaded_slots.append(slot_key)
            
            
            for slot_key in underloaded_slots:
                if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                    continue
                    
                candidates_list = allocations[slot_key].copy()
                
                for candidate in candidates_list:
                    
                    if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                        break
                        
                    candidate_preferences = parse_time_slots(candidate.interview_time_slots)
                    
                    
                    alternative_slots = []
                    for pref_slot in candidate_preferences:
                        if pref_slot in time_slot_instances:
                            for week in range(2):
                                instance = time_slot_instances[pref_slot][week]
                                if (instance['slot_key'] != slot_key and 
                                    instance['count'] < 4):
                                    alternative_slots.append(instance)
                    
                    if alternative_slots:
                        best_alternative = max(alternative_slots, key=lambda x: x['count'])
                        
                        allocations[slot_key].remove(candidate)
                        original_slot_name = slot_key.split('_week_')[0]
                        original_week = int(slot_key.split('_week_')[1])
                        time_slot_instances[original_slot_name][original_week]['count'] -= 1
                        time_slot_counts[slot_key] -= 1
                        
                        allocations[best_alternative['slot_key']].append(candidate)
                        best_alternative['count'] += 1
                        time_slot_counts[best_alternative['slot_key']] = best_alternative['count']
                        candidate_to_slot[candidate.uid] = best_alternative['slot_key']
                        
                        changes_made = True
                        
                        break
            
            if not changes_made:
                break
    
    optimize_underloaded_slots()
    
    
    def redistribute_underloaded_slots():
        max_iterations = 100
        for iteration in range(max_iterations):
            changes_made = False
            
            
            underloaded_slots = []
            for slot_key, candidates_list in allocations.items():
                if len(candidates_list) < 4:
                    underloaded_slots.append(slot_key)
            
            
            for slot_key in underloaded_slots:
                if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                    continue
                    
                candidates_list = allocations[slot_key].copy()
                
                for candidate in candidates_list:
                    
                    if slot_key not in allocations or len(allocations[slot_key]) >= 4:
                        break
                        
                    candidate_preferences = parse_time_slots(candidate.interview_time_slots)
                    
                    
                    alternative_slots = []
                    for pref_slot in candidate_preferences:
                        if pref_slot in time_slot_instances:
                            for week in range(2):
                                instance = time_slot_instances[pref_slot][week]
                                if (instance['slot_key'] != slot_key and 
                                    instance['count'] <= 7 and instance['count'] >= 4):
                                    alternative_slots.append(instance)
                    
                    if alternative_slots:
                        best_alternative = min(alternative_slots, key=lambda x: x['count'])
                        
                        allocations[slot_key].remove(candidate)
                        original_slot_name = slot_key.split('_week_')[0]
                        original_week = int(slot_key.split('_week_')[1])
                        time_slot_instances[original_slot_name][original_week]['count'] -= 1
                        time_slot_counts[slot_key] -= 1
                        
                        allocations[best_alternative['slot_key']].append(candidate)
                        best_alternative['count'] += 1
                        time_slot_counts[best_alternative['slot_key']] = best_alternative['count']
                        candidate_to_slot[candidate.uid] = best_alternative['slot_key']
                        
                        changes_made = True
                        break
            
            if not changes_made:
                break
    
    redistribute_underloaded_slots()
    
    
    schedule_results = []
    venue_assignments = {}
    
    for slot_key, candidates_list in allocations.items():
        
        
        parts = slot_key.split('_week_')
        original_slot = parts[0]
        week_num = int(parts[1])
        
        interview_date = calculate_slot_date(base_date, original_slot, week_num)
        
        venue = "场地A"
        venue_assignments[slot_key] = ["场地A"]
        
        for i, candidate in enumerate(candidates_list):
            week_label = "本周" if week_num == 0 else "下周"
            display_slot = f"{original_slot} ({week_label})"
            
            schedule_results.append({
                'uid': candidate.uid,
                'name': candidate.name,
                'time_slot': slot_key,  
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
    interview_duration: int = 40  
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
    base_date: str  
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
    csv_file_path: Optional[str] = None  


@router.post("/schedule", tags=["interview"])
def create_interview_schedule(
    schedule_data: InterviewSchedule,
    db: Session = Depends(get_db),
    
):
    
    recruit = db.query(Recruitment).filter(Recruitment.uid == schedule_data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recruitment record not found"
        )
    
    try:
        new_schedule = Interview(**schedule_data.dict())
        
        db.add(new_schedule)
        
        recruit.interview_status = schedule_data.stage
        recruit.interview_completed = False  # 设置为未完成状态
        
        db.commit()
        db.refresh(new_schedule)
        
        return new_schedule
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred when creating interview schedule: {e}"
        )


@router.post("/auto-schedule", tags=["interview"])
def auto_schedule_interviews(
    request: AutoScheduleRequest,
    db: Session = Depends(get_db),
    
):
    try:
        
        candidates = db.query(Recruitment).filter(
            Recruitment.interview_time_slots.isnot(None),
            Recruitment.interview_time_slots != "",
            Recruitment.interview_status.in_(["first_round", "second_round"])  # 排班一面和二面的
        ).all()
        
        print(f"Found {len(candidates)} candidates available for scheduling")
        
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
        
        
        algorithm_result = auto_schedule_algorithm(
            candidates, 
            request.base_date, 
            request.max_candidates_per_slot
        )
        print(algorithm_result['schedule_results'])
        
        print(f"Algorithm result: Successfully scheduled {len(algorithm_result['schedule_results'])} people, unscheduled {len(algorithm_result['unscheduled'])} people")
        
        
        created_schedules = []
        for schedule_info in algorithm_result['schedule_results']:
            existing_schedule = db.query(Interview).filter(
                Interview.uid == schedule_info['uid']
            ).first()
            
            if existing_schedule:
                print(f"Skipping existing schedule: {schedule_info['uid']}")
                continue  # 跳过已存在的排班
            
            recruit = db.query(Recruitment).filter(Recruitment.uid == schedule_info['uid']).first()
            current_stage = recruit.interview_status if recruit else "first_round"
            
            slot_parts = schedule_info['time_slot'].split('_week_')
            
            if len(slot_parts) != 2:
                print(f"Error: Invalid time_slot format: {schedule_info['time_slot']}")
                continue
                
            original_slot = slot_parts[0]  
            week_num = int(slot_parts[1])  
            
            slot_name_parts = original_slot.split(' ')
            if len(slot_name_parts) != 2:
                print(f"Error: Invalid original_slot format: {original_slot}")
                continue
                
            day_name = slot_name_parts[0]  # 如 "周一"
            time_range = slot_name_parts[1]  
            
            time_parts = time_range.split('-')
            if len(time_parts) != 2:
                print(f"Error: Invalid time_range format: {time_range}")
                continue
                
            start_time, end_time = time_parts
            
            time_slot = get_or_create_time_slot(db, original_slot, day_name, start_time, end_time, week_num)
            
            new_schedule = Interview(
                uid=schedule_info['uid'],
                stage=current_stage,  # 使用当前面试阶段
                interview_date=schedule_info['interview_date'],
                interview_format="one_to_one",  # 默认一对一面试
                interview_duration=40,  
                location=schedule_info['venue'],
                notes=f"自动排班 - {schedule_info['time_slot']} - 第{schedule_info['candidate_index']}位",
                status="scheduled",
                notification_sent=False,
                time_slot_id=time_slot.id  
            )
            
            db.add(new_schedule)
            created_schedules.append(new_schedule)
            
            time_slot.current_count += 1
            
            recruit = db.query(Recruitment).filter(Recruitment.uid == schedule_info['uid']).first()
            if recruit:
                recruit.interview_status = current_stage
                recruit.interview_completed = False  # 设置为未完成状态
        
        
        db.commit()
        print(f"Successfully created {len(created_schedules)} interview schedule records")
        
        
        total_candidates = len(candidates)
        scheduled_candidates = len(algorithm_result['schedule_results'])
        unscheduled_candidates = len(algorithm_result['unscheduled'])
        
        
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
        
        
        time_slot_stats = []
        for time_slot, count in algorithm_result['time_slot_counts'].items():
            venues = algorithm_result['venue_assignments'].get(time_slot, [])
            time_slot_stats.append({
                'time_slot': time_slot,
                'candidate_count': count,
                'venues': venues
            })
        
        
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
        print(f"Auto scheduling failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred during auto scheduling: {e}"
        )


@router.get("/schedule-statistics", tags=["interview"])
def get_schedule_statistics(
    db: Session = Depends(get_db),
    
):
    try:
        total_recruits = db.query(Recruitment).count()
        
        recruits_with_slots = db.query(Recruitment).filter(
            Recruitment.interview_time_slots.isnot(None),
            Recruitment.interview_time_slots != ""
        ).count()
        
        scheduled_recruits = db.query(Recruitment).filter(
            Recruitment.interview_status.in_(["screening", "first_round", "second_round"])
        ).count()
        
        unscheduled_recruits = recruits_with_slots - scheduled_recruits
        
        time_slot_stats = {}
        interviews = db.query(Interview).filter(Interview.status == "scheduled").all()
        
        for interview in interviews:
            day_name = interview.interview_date.strftime("%A")
            day_mapping = {
                "Monday": "周一", "Tuesday": "周二", "Wednesday": "周三",
                "Thursday": "周四", "Friday": "周五", "Saturday": "周六", "Sunday": "周日"
            }
            chinese_day = day_mapping.get(day_name, "未知")
            time_part = interview.interview_date.strftime("%H:%M")
            
            time_slot = f"{chinese_day} {time_part}"
            
            if time_slot not in time_slot_stats:
                time_slot_stats[time_slot] = {
                    'count': 0,
                    'venues': set()
                }
            
            time_slot_stats[time_slot]['count'] += 1
            if interview.location:
                time_slot_stats[time_slot]['venues'].add(interview.location)
        
        
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
            detail=f"Error occurred when getting schedule statistics: {e}"
        )


@router.get("/interviews/{uid}", tags=["interview"])
def get_interviews_by_uid(
    uid: str,
    db: Session = Depends(get_db),
    
):
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
    
):
    
    query = db.query(Interview)
    
    if uid:
        query = query.filter(Interview.uid.like(f"%{uid}%"))
    if stage:
        query = query.filter(Interview.stage == stage)
    if status:
        query = query.filter(Interview.status == status)
    
    total = query.count()
    
    schedules = query.order_by(Interview.interview_date.asc()).offset((page - 1) * size).limit(size).all()
    
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
    
):
    
    schedule = db.query(Interview).filter(Interview.id == schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview schedule record not found"
        )
    
    try:
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
            detail=f"Error occurred when updating interview schedule: {e}"
        )


@router.delete("/schedule/{schedule_id}", tags=["interview"])
def delete_interview_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    
):
    
    schedule = db.query(Interview).filter(Interview.id == schedule_id).first()
    if not schedule:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Interview schedule record not found"
        )
    
    try:
        db.delete(schedule)
        db.commit()
        
        return {"message": "面试排班删除成功"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred when deleting interview schedule: {e}"
        )


@router.get("/recruit_time_slots/{uid}", tags=["interview"])
def get_recruit_time_slots(
    uid: str,
    db: Session = Depends(get_db),
):
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == uid).first()
        if not recruit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recruitment record not found"
            )
        
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
            detail=f"Error occurred when getting interview time slot information: {e}"
        )


def format_time_slots(time_slots):
    if not time_slots:
        return []
    
    formatted = []
    for slot_id in time_slots:
        
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
):
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == uid).first()
        if not recruit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recruitment record not found"
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
            detail=f"Error occurred when getting recruit information: {e}"
        )


@router.get("/schedule_stats", tags=["interview"])
def get_schedule_statistics(
    db: Session = Depends(get_db),
):
    
    try:
        screening_count = db.query(Interview).filter(Interview.stage == "screening").count()
        first_round_count = db.query(Interview).filter(Interview.stage == "first_round").count()
        second_round_count = db.query(Interview).filter(Interview.stage == "second_round").count()
        
        scheduled_count = db.query(Interview).filter(Interview.status == "scheduled").count()
        completed_count = db.query(Interview).filter(Interview.status == "completed").count()
        cancelled_count = db.query(Interview).filter(Interview.status == "cancelled").count()
        
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
            detail=f"Error occurred when getting interview schedule statistics: {e}"
        )


class BatchInterviewUpdate(BaseModel):
    interview_ids: List[int]
    result: str = Field(..., pattern="^(pass|fail|pending|recommended)$")


@router.post("/batch_update_interviews", tags=["interview"])
def batch_update_interviews(
    data: BatchInterviewUpdate,
    db: Session = Depends(get_db),
):
    
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
            detail=f"Error occurred when batch updating interview records: {e}"
        )


class ScheduleNotification(BaseModel):
    schedule_id: int
    custom_message: Optional[str] = None


@router.post("/send_schedule_notification", tags=["interview"])
def send_schedule_notification(
    notification_data: ScheduleNotification,
    db: Session = Depends(get_db),
):
    
    try:
        schedule = db.query(Interview).filter(Interview.id == notification_data.schedule_id).first()
        if not schedule:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Interview schedule record not found"
            )
        
        recruit = db.query(Recruitment).filter(Recruitment.uid == schedule.uid).first()
        if not recruit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Recruitment record not found"
            )
        
        stage_labels = {
            "screening": "简历筛选",
            "first_round": "第一轮面试",
            "second_round": "第二轮面试"
        }
        
        stage_label = stage_labels.get(schedule.stage, schedule.stage)
        interview_date = schedule.interview_date.strftime("%Y年%m月%d日 %H:%M")
        
        title = f"ZJUCSA面试通知 - {stage_label}"
        description = f"亲爱的 {recruit.name} 同学！\n\n您的面试已安排如下：\n\n面试阶段：{stage_label}\n面试时间：{interview_date}\n面试形式：{get_interview_format_label(schedule.interview_format)}\n面试时长：{schedule.interview_duration}分钟"
        
        if schedule.location:
            description += f"\n面试地点：{schedule.location}"
        
        if schedule.notes:
            description += f"\n注意事项：{schedule.notes}"
        
        if notification_data.custom_message:
            description += f"\n\n补充说明：{notification_data.custom_message}"
        
        description += "\n\n请准时参加面试，祝您面试顺利！"
        
        from misc.dingtalk import send_dingtalk_message_to_user
        success = send_dingtalk_message_to_user(
            user_id=schedule.uid,
            title=title,
            description=description
        )
        
        if success:
            schedule.notification_sent = True
            schedule.updated_at = datetime.utcnow()
            db.commit()
            return {"message": "面试通知发送成功"}
        else:
            return {"message": "面试通知发送失败"}
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred when sending interview notification: {e}"
        )

def generate_schedule_csv(schedule_results: List[Dict[str, Any]], base_date: str) -> str:
    
    uploads_dir = "uploads"
    if not os.path.exists(uploads_dir):
        os.makedirs(uploads_dir)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"interview_schedule_{timestamp}.csv"
    file_path = os.path.join(uploads_dir, filename)
    
    
    with open(file_path, 'w', newline='', encoding='utf-8-sig') as csvfile:
        fieldnames = [
            '序号', '学号', '姓名', '面试阶段', '面试日期', '面试时间', 
            '时间段', '场地', '面试官', '面试时长(分钟)', '备注'
        ]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        
        for i, schedule in enumerate(schedule_results, 1):
            interview_date = schedule['interview_date']
            if isinstance(interview_date, datetime):
                date_str = interview_date.strftime('%Y-%m-%d')
                time_str = interview_date.strftime('%H:%M')
            else:
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
    base_date: Optional[str] = None,
    db: Session = Depends(get_db),
    
):
    
    try:
        if base_date:
            from datetime import datetime, timedelta
            
            base_date_obj = datetime.strptime(base_date, "%Y-%m-%d")
            weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
            
            base_time_slots = [
                { 'day': 1, 'times': ['19:00-20:00', '20:00-21:00', '21:00-22:00'] }, # 周一
                { 'day': 2, 'times': ['19:00-20:00', '20:00-21:00', '21:00-22:00'] }, # 周二
                { 'day': 3, 'times': ['19:00-20:00', '20:00-21:00', '21:00-22:00'] }, # 周三
                { 'day': 4, 'times': ['19:00-20:00', '20:00-21:00', '21:00-22:00'] }, # 周四
                { 'day': 5, 'times': ['19:00-20:00', '20:00-21:00', '21:00-22:00'] }, # 周五
                { 'day': 6, 'times': ['10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00', '16:00-17:00', '19:00-20:00', '20:00-21:00', '21:00-22:00'] }, # 周六
                { 'day': 0, 'times': ['10:00-11:00', '11:00-12:00', '14:00-15:00', '15:00-16:00', '16:00-17:00', '19:00-20:00', '20:00-21:00', '21:00-22:00'] }  # 周日
            ]
            
            time_slots_list = []
            
            for week in range(2):
                for day_config in base_time_slots:
                    target_day = day_config['day']
                    current_day = base_date_obj.weekday()  
                    days_to_add = target_day - current_day
                    
                    
                    if days_to_add < 0:
                        days_to_add += 7
                    
                    days_to_add += week * 7
                    
                    target_date = base_date_obj + timedelta(days=days_to_add)
                    date_str = target_date.strftime("%m/%d")
                    day_name = weekdays[target_day]
                    week_label = '本周' if week == 0 else '下周'
                    
                    for time_range in day_config['times']:
                        slot_name = f"{day_name} {time_range}"
                        start_hour = int(time_range.split('-')[0].split(':')[0])
                        end_hour = int(time_range.split('-')[1].split(':')[0])
                        
                        start_time = target_date.replace(hour=start_hour, minute=0)
                        end_time = target_date.replace(hour=end_hour, minute=0)
                        
                        scheduled_count = db.query(Interview).filter(
                            Interview.interview_date >= start_time,
                            Interview.interview_date < end_time
                        ).count()
                        
                        time_slots_list.append({
                            "id": f"{slot_name}_{week}",
                            "name": f"{day_name} {date_str} {time_range} ({week_label})",
                            "day_of_week": target_day,
                            "start_time": time_range.split('-')[0],
                            "end_time": time_range.split('-')[1],
                            "week_number": week,
                            "venue": "",
                            "current_count": scheduled_count,
                            "max_capacity": 8
                        })
            
            time_slots_list.sort(key=lambda x: x["name"])
            
            return {
                "success": True,
                "time_slots": time_slots_list
            }
        else:
            time_slots = db.query(InterviewTimeSlot).filter(
                InterviewTimeSlot.is_active == True,
                InterviewTimeSlot.current_count > 0
            ).all()
            
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
            
            time_slots_list.sort(key=lambda x: x["name"])
            
            return {
                "success": True,
                "time_slots": time_slots_list
            }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred when getting interview time slots: {e}"
        )


@router.get("/download-schedule-csv/{filename}", tags=["interview"])
def download_schedule_csv(
    filename: str,
    db: Session = Depends(get_db),
    
):
    file_path = os.path.join("uploads", filename)
    
    if not os.path.exists(file_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="File not found"
        )
    
    return FileResponse(
        path=file_path,
        filename=filename,
        media_type='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )



class CompleteInterviewRequest(BaseModel):
    time_slot: str  
    week: int  


@router.post("/complete-interview", tags=["interview"])
def complete_interview(
    request: CompleteInterviewRequest,
    db: Session = Depends(get_db),
    
):
    
    try:
        print(f"Received time slot: {request.time_slot}")
        print(f"Week number: {request.week}")
        
        base_time_slot = request.time_slot
        if ' ' in base_time_slot:
            parts = base_time_slot.split()
            if len(parts) >= 3:
                
                base_time_slot = f"{parts[0]} {parts[2]}"
        
        print(f"Processed base time slot: {base_time_slot}")
        
        interviews = db.query(Interview).filter(
            Interview.stage.in_(['first_round', 'second_round'])
        ).all()
        
        print(f"Found {len(interviews)} interview records")
        print(f"Target time slot: {base_time_slot}")
        print(f"Target week number: {request.week}")
        
        target_interviews = []
        for interview in interviews:
            
            matched_slot = matchTimeSlotFromDate(interview.interview_date)
            print(f"Interview {interview.uid}: date={interview.interview_date}, matched time slot={matched_slot}")
            
            if matched_slot == base_time_slot:
                interview_date = interview.interview_date
                base_date = datetime.now().date()
                days_diff = (interview_date.date() - base_date).days
                interview_week = 1 if days_diff >= 7 else 0
                
                print(f"  Week check: days_diff={days_diff}, interview_week={interview_week}")
                
                if interview_week == request.week:
                    target_interviews.append(interview)
                    print(f"  Match successful, added to target list")
                else:
                    print(f"  Week number mismatch")
            else:
                print(f"  Time slot mismatch")
        
        for interview in target_interviews:
            recruit = db.query(Recruitment).filter(Recruitment.uid == interview.uid).first()
            if recruit:
                recruit.interview_completed = True  # 当前阶段面试已完成
                
                stage_label = "第一轮" if interview.stage == 'first_round' else "第二轮"
                title = f"浙江大学学生网络空间安全协会（ZJUCSA）{stage_label}面试完成通知"
                description = f"""亲爱的 {recruit.name} 同学！

你的{stage_label}面试已经完成！

【面试信息】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：{stage_label}面试
• 面试时间：{interview.interview_date.strftime('%Y年%m月%d日 %H:%M')}

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
                        print(f"Interview completion notification sent successfully: {recruit.uid}")
                    else:
                        print(f"Interview completion notification failed: {recruit.uid}")
                except Exception as e:
                    print(f"Error sending interview completion notification: {e}")
        
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
            detail=f"Error occurred when completing interview: {e}"
        )


class PassInterviewRequest(BaseModel):
    uid: str
    round_type: str  


@router.post("/pass-interview", tags=["interview"])
def pass_interview(
    request: PassInterviewRequest,
    db: Session = Depends(get_db),
    
):
    """面试通过处理"""
    
    
    
    #     )
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="Recruit not found")
        
        if request.round_type == 'first_round':
            recruit.first_round_passed = True
            recruit.interview_status = 'second_round'  # 进入二面
            recruit.interview_completed = False  # 重置为未完成状态，准备二面
            
            interview = db.query(Interview).filter(
                Interview.uid == request.uid,
                Interview.stage == 'first_round'
            ).first()
            if interview:
                interview.result = 'pass'
                interview.status = 'completed'
            
        elif request.round_type == 'second_round':
            recruit.second_round_passed = True
            recruit.interview_status = 'completed'  # 面试完成
            recruit.interview_completed = True  # 面试完成
            
            interview = db.query(Interview).filter(
                Interview.uid == request.uid,
                Interview.stage == 'second_round'
            ).first()
            if interview:
                interview.result = 'pass'
                interview.status = 'completed'
            
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
            detail=f"Error occurred when processing interview pass: {e}"
        )


def matchTimeSlotFromDate(interview_date: datetime) -> str:
    """从面试日期匹配时间段"""
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    day_of_week = interview_date.weekday()  
    hour = interview_date.hour
    
    day_name = weekdays[day_of_week]
    
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
    time_slot = db.query(InterviewTimeSlot).filter(
        InterviewTimeSlot.slot_name == slot_name,
        InterviewTimeSlot.week_number == week_number
    ).first()
    
    if time_slot:
        return time_slot
    
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
    slot_parts = slot_key.split('_week_')
    original_slot = slot_parts[0]  
    week_num = int(slot_parts[1])  
    
    day_name = original_slot.split(' ')[0]  # 如 "周一"
    time_range = original_slot.split(' ')[1]  
    start_time, end_time = time_range.split('-')
    
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
    target_day_index = weekdays.index(day_name)
    
    base_weekday = base_date.weekday()
    days_ahead = target_day_index - base_weekday
    if days_ahead <= 0:  # 如果目标日期在本周已经过了，则安排在下周
        days_ahead += 7
    days_ahead += week_num * 7  # 加上周数偏移
    
    interview_date = base_date + timedelta(days=days_ahead)
    
    hour = int(start_time.split(':')[0])
    minute = int(start_time.split(':')[1])
    interview_date = interview_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
    
    time_slot = get_or_create_time_slot(db, original_slot, day_name, start_time, end_time, week_num)
    
    new_schedule = Interview(
        uid=candidate.uid,
        stage=current_stage,
        interview_date=interview_date,
        interview_format="one_to_one",  # 默认一对一面试
        interview_duration=40,
        location=time_slot.venue,
        status='scheduled',
        time_slot_id=time_slot.id  
    )
    
    db.add(new_schedule)
    
    time_slot.current_count += 1
    
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



