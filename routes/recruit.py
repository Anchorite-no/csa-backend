import pandas as pd
import hashlib
import os
from pathlib import Path
from typing import Optional, List, Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status, UploadFile, File
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.model import aid_to_nick
from misc.auth import get_current_user, login_required_admin
from models import get_db
from models.participation import Participation
from models.relation.user_event import user_event
from models.event import Event
from models.user import User
from models.recruit import Recruitment

router = APIRouter()

# 创建简历存储目录
RESUME_UPLOAD_DIR = Path("uploads/resumes")
RESUME_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

class FuzzySearchMajor(BaseModel):
    major_name: str
    grade: int

@router.post("/major_search")
def fuzzy_search_major(data: FuzzySearchMajor, db: Session = Depends(get_db)):
    csv_file_path = f"major/specialties_data_20{data.grade}.csv"
    try:
        df = pd.read_csv(csv_file_path, dtype=str)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CSV file not found at {csv_file_path}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading CSV file: {e}"
        )

    search_query = data.major_name

    results_df = df[df['major_name'].str.contains(search_query, case=False, na=False)]

    results_list = results_df.to_dict(orient='records')
    
    return results_list


class ConfirmationMajor(BaseModel):
    major_name: str
    grade: int

@router.post("/major_confirm")
def confirm_major(data: ConfirmationMajor, db: Session = Depends(get_db)):
    csv_file_path = f"major/specialties_data_20{data.grade}.csv"
    print(csv_file_path)
    try:
        df = pd.read_csv(csv_file_path, dtype=str)
    except FileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"CSV file not found at {csv_file_path}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error reading CSV file: {e}"
        )

    search_query = data.major_name

    results_df = df[df['major_name'] == search_query]
    results_list = results_df.to_dict(orient='records')
    
    return results_list

class RecruitItem(BaseModel):
    name: Annotated[str, StringConstraints(max_length=12)]
    render: bool
    uid: Annotated[str, StringConstraints(pattern=r"^\d{1,10}$")]
    major_id: str
    major_name: str
    college_id: str
    college_name: str
    degree: Annotated[int, Field(ge=0, le=4)]
    grade: Annotated[int, Field(ge=21, le=25)]
    phone: Annotated[str, StringConstraints(pattern=r"^1[3-9]\d{9}$")]
    office_department_willing: Annotated[int, Field(ge=1, le=4)]
    competition_department_willing: Annotated[int, Field(ge=1, le=4)]
    activity_department_willing: Annotated[int, Field(ge=1, le=4)]
    research_department_willing: Annotated[int, Field(ge=1, le=4)]
    if_agree_to_be_reassigned: bool
    if_be_member: bool
    introduction: Annotated[str, StringConstraints(max_length=250)]
    skill: Annotated[str, StringConstraints(max_length=250)]

@router.post("/recruit_confirm")
def confirm_recruit(data: RecruitItem, db: Session = Depends(get_db)):
    # 检查是否存在相同 uid 的记录
    existing_recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if existing_recruit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="该学号已提交过报名信息")
    
    csv_file_path = f"major/specialties_data_20{data.grade}.csv"
    df = pd.read_csv(csv_file_path, dtype=str)
    
    if data.major_name not in df['major_name'].values:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="专业不存在")
    
    major_id = df[df['major_name'] == data.major_name]['major_id'].values[0]
    college_id = df[df['major_name'] == data.major_name]['college_id'].values[0]
    college_name = df[df['major_name'] == data.major_name]['college_name'].values[0]
    
    if data.degree == 0:
        if data.major_id != major_id or data.college_id != college_id or data.college_name != college_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="专业或学院信息不匹配")

    # 创建新的报名记录
    new_recruit = Recruitment(
        name=data.name,
        render=data.render,
        uid=data.uid,  
        major_id=major_id,
        major_name=data.major_name,
        college_id=college_id,
        college_name=college_name,
        grade=data.grade,
        phone=data.phone,
        degree=data.degree,
        office_department_willing=data.office_department_willing,
        competition_department_willing=data.competition_department_willing,
        activity_department_willing=data.activity_department_willing,
        research_department_willing=data.research_department_willing,
        if_agree_to_be_reassigned=data.if_agree_to_be_reassigned,
        if_be_member=data.if_be_member,
        introduction=data.introduction,
        skill=data.skill
    )
    try:   
        db.add(new_recruit)
        db.commit()
        return {"message": "Recruit information submitted successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"An error occurred when submitting recruit information: {e}")

@router.post("/upload_resume")
async def upload_resume(
    uid: str = Form(...),
    resume_file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    # 验证学号格式
    if not uid or not uid.isdigit() or len(uid) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="学号格式不正确")
    
    existing_recruit = db.query(Recruitment).filter(Recruitment.uid == uid).first()
    if not existing_recruit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请先提交报名信息")
    
    if not resume_file.content_type == "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只支持PDF格式文件")
    
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
    if resume_file.size and resume_file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件大小不能超过10MB")
    
    try:
        file_hash = hashlib.sha256(uid.encode()).hexdigest()
        filename = f"{file_hash}.pdf"
        file_path = RESUME_UPLOAD_DIR / filename
        
        content = await resume_file.read()
        
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件不是有效的PDF格式")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return {"message": "简历上传成功", "filename": filename}
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"文件上传失败: {str(e)}")
    
    