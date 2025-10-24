from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime

from misc.auth import get_current_admin
from models import get_db
from models.member import Member
from models.recruit import Recruitment

router = APIRouter()


class MemberCreate(BaseModel):
    uid: str
    name: str
    render: bool
    major_id: Optional[str] = None
    major_name: Optional[str] = None
    college_id: Optional[str] = None
    college_name: Optional[str] = None
    grade: Optional[int] = None
    phone: Optional[str] = None
    degree: Optional[int] = None
    department: str
    position: str = "干事"
    bank_card: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    email: Optional[str] = None
    wechat: Optional[str] = None
    qq: Optional[str] = None
    notes: Optional[str] = None
    skills: Optional[str] = None

class MemberUpdate(BaseModel):
    name: Optional[str] = None
    render: Optional[bool] = None
    major_id: Optional[str] = None
    major_name: Optional[str] = None
    college_id: Optional[str] = None
    college_name: Optional[str] = None
    grade: Optional[int] = None
    phone: Optional[str] = None
    degree: Optional[int] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
    bank_card: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    work_hours: Optional[float] = None
    performance_score: Optional[float] = None
    email: Optional[str] = None
    wechat: Optional[str] = None
    qq: Optional[str] = None
    notes: Optional[str] = None
    skills: Optional[str] = None

class MemberResponse(BaseModel):
    uid: str
    name: str
    render: bool
    major_name: Optional[str] = None
    college_name: Optional[str] = None
    grade: Optional[int] = None
    phone: Optional[str] = None
    degree: Optional[int] = None
    department: str
    position: str
    join_date: datetime
    is_active: bool
    bank_card: Optional[str] = None
    bank_name: Optional[str] = None
    account_holder: Optional[str] = None
    work_hours: float
    performance_score: float
    evaluation_count: int
    email: Optional[str] = None
    wechat: Optional[str] = None
    qq: Optional[str] = None
    notes: Optional[str] = None
    skills: Optional[str] = None
    created_at: datetime
    updated_at: datetime

@router.get("/members", tags=["member"])
def get_members(
    department: Optional[str] = None,
    is_active: Optional[bool] = None,
    page: int = 1,
    size: int = 20,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    """获取干事列表"""
    query = db.query(Member)
    
    if department:
        query = query.filter(Member.department == department)
    if is_active is not None:
        query = query.filter(Member.is_active == is_active)
    
    total = query.count()
    
    members = query.offset((page - 1) * size).limit(size).all()
    
    result_list = []
    for member in members:
        result_list.append(MemberResponse(
            uid=member.uid,
            name=member.name,
            render=member.render,
            major_name=member.major_name,
            college_name=member.college_name,
            grade=member.grade,
            phone=member.phone,
            degree=member.degree,
            department=member.department,
            position=member.position,
            join_date=member.join_date,
            is_active=member.is_active,
            bank_card=member.bank_card,
            bank_name=member.bank_name,
            account_holder=member.account_holder,
            work_hours=member.work_hours,
            performance_score=member.performance_score,
            evaluation_count=member.evaluation_count,
            email=member.email,
            wechat=member.wechat,
            qq=member.qq,
            notes=member.notes,
            skills=member.skills,
            created_at=member.created_at,
            updated_at=member.updated_at
        ))
    
    return {
        "members": result_list,
        "total": total,
        "page": page,
        "size": size
    }

@router.get("/members/{uid}", tags=["member"])
def get_member_detail(
    uid: str,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    """获取干事详情"""
    member = db.query(Member).filter(Member.uid == uid).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    return MemberResponse(
        uid=member.uid,
        name=member.name,
        render=member.render,
        major_name=member.major_name,
        college_name=member.college_name,
        grade=member.grade,
        phone=member.phone,
        degree=member.degree,
        department=member.department,
        position=member.position,
        join_date=member.join_date,
        is_active=member.is_active,
        bank_card=member.bank_card,
        bank_name=member.bank_name,
        account_holder=member.account_holder,
        work_hours=member.work_hours,
        performance_score=member.performance_score,
        evaluation_count=member.evaluation_count,
        email=member.email,
        wechat=member.wechat,
        qq=member.qq,
        notes=member.notes,
        skills=member.skills,
        created_at=member.created_at,
        updated_at=member.updated_at
    )

@router.post("/members", tags=["member"])
def create_member(
    data: MemberCreate,
    db: Session = Depends(get_db),
    
):
    """创建干事（从纳新者迁移）"""
    existing_member = db.query(Member).filter(Member.uid == data.uid).first()
    if existing_member:
        raise HTTPException(status_code=400, detail="This member already exists")
    
    member = Member(
        uid=data.uid,
        name=data.name,
        render=data.render,
        major_id=data.major_id,
        major_name=data.major_name,
        college_id=data.college_id,
        college_name=data.college_name,
        grade=data.grade,
        phone=data.phone,
        degree=data.degree,
        department=data.department,
        position=data.position,
        bank_card=data.bank_card,
        bank_name=data.bank_name,
        account_holder=data.account_holder,
        email=data.email,
        wechat=data.wechat,
        qq=data.qq,
        notes=data.notes,
        skills=data.skills
    )
    
    try:
        db.add(member)
        db.commit()
        db.refresh(member)
        
        return {"success": True, "message": "干事创建成功", "member": member}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create member: {str(e)}")

@router.put("/members/{uid}", tags=["member"])
def update_member(
    uid: str,
    data: MemberUpdate,
    db: Session = Depends(get_db),
    
):
    """更新干事信息"""
    member = db.query(Member).filter(Member.uid == uid).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    update_data = data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(member, field, value)
    
    member.updated_at = datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(member)
        
        return {"success": True, "message": "干事信息更新成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update member information: {str(e)}")

@router.delete("/members/{uid}", tags=["member"])
def delete_member(
    uid: str,
    db: Session = Depends(get_db),
    
):
    """删除干事"""
    member = db.query(Member).filter(Member.uid == uid).first()
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    try:
        db.delete(member)
        db.commit()
        
        return {"success": True, "message": "干事删除成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete member: {str(e)}")

@router.get("/members/stats", tags=["member"])
def get_member_stats(
    db: Session = Depends(get_db),
    
):
    """获取干事统计信息"""
    department_stats = {}
    departments = ['office', 'competition', 'research', 'activity']
    
    for dept in departments:
        total = db.query(Member).filter(Member.department == dept).count()
        active = db.query(Member).filter(
            Member.department == dept,
            Member.is_active == True
        ).count()
        
        department_stats[dept] = {
            "total": total,
            "active": active,
            "inactive": total - active
        }
    
    total_members = db.query(Member).count()
    active_members = db.query(Member).filter(Member.is_active == True).count()
    
    return {
        "total_members": total_members,
        "active_members": active_members,
        "inactive_members": total_members - active_members,
        "department_stats": department_stats
    }
