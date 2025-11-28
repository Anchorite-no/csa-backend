import pandas as pd
import hashlib
import os
import json
from pathlib import Path
from typing import Optional, List, Annotated
from io import BytesIO
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status, UploadFile, File
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.model import aid_to_nick
from misc.auth import get_current_user, get_current_admin, login_required_admin, hash_passwd
from models import get_db
from models.participation import Participation
from models.relation.user_event import user_event
from models.event import Event
from models.user import User
from models.recruit import Recruitment
from models.interview import Interview
from models.recruit import Evaluation
from models.admin import Admin
from datetime import datetime
from misc.dingtalk import send_dingtalk_message_to_user
from routes.admin import is_manager

router = APIRouter()


def matchTimeSlotFromDate(interview_date: datetime) -> str:
    """Match time slot from interview date"""
    weekdays = ['周一', '周二', '周三', '周四', '周五', '周六', '周日']
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
    major_name: str
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
    interview_time_slots: List[str] = Field(default_factory=list, description="Interview time slot selection")

@router.post("/recruit_confirm")
def confirm_recruit(data: RecruitItem, db: Session = Depends(get_db)):
    existing_recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if existing_recruit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This student ID has already submitted application information")
    
    if data.degree == 0:
        csv_file_path = f"major/specialties_data_20{data.grade}.csv"
        df = pd.read_csv(csv_file_path, dtype=str)
        
        if data.major_name not in df['major_name'].values:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Major does not exist")
        
        major_id = df[df['major_name'] == data.major_name]['major_id'].values[0]
        college_id = df[df['major_name'] == data.major_name]['college_id'].values[0]
        college_name = df[df['major_name'] == data.major_name]['college_name'].values[0]
        
        if data.major_id != major_id or data.college_id != college_id or data.college_name != college_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Major or college information does not match")
    else:
        major_id = data.major_id if data.major_id else "DEFAULT_MASTER_PHD"
        college_id = data.college_id if data.college_id else "DEFAULT_COLLEGE"
        college_name = data.college_name if data.college_name else "默认学院"

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
        skill=data.skill,
        evaluation_status="pending",
        evaluation_time=datetime.now(),
        evaluator_id="",
        assigned_department=""
    )
    try:   
        db.add(new_recruit)
        db.commit()
        title = "浙江大学学生网络空间安全协会（ZJUCSA）招新报名成功通知"

        description = f"""亲爱的 {data.name} 同学！\n你已成功提交浙江大学学生网络空间安全协会（ZJUCSA）的招新报名申请。\n\n首先，衷心感谢你对CSA的关注与认可。我们非常期待能有更多像你一样对网络空间安全充满热情的同学加入我们，一同探索未知的技术领域。\n我们已经收到了你的申请，并会尽快进行筛选。面试安排将通过钉钉OA、短信或电话形式通知你，请务必保持手机畅通，以便及时获取最新信息。\n在面试中，我们希望有机会能更深入地了解你，听听你对网络安全的热爱与见解。无论你对Web安全、二进制安全还是其他方向感兴趣，我们都鼓励你勇敢展示自己，分享你的思考。\nCSA不仅是一个学习技术、共同进步的平台，更是一个充满活力、互帮互助的大家庭。我们期待与你携手，共同探索网络世界的无限可能，在CSA的大家庭中共同成长。\n注意！ 招新报名表一旦提交不可修改或重复提交，如有任何疑问，请发送邮件至csa@zju.edu.cn\n连心为网，筑梦为安，期待你的加入！
        """

        try:
            success = send_dingtalk_message_to_user(
                user_id=data.uid,
                title=title,
                description=description,
            )
            if success:
                print(f"DingTalk notification sent successfully: {data.uid}")
            else:
                print(f"DingTalk notification failed: {data.uid}")
        except Exception as e:
            print(f"Error sending DingTalk notification: {e}")
        
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
    if not uid or not uid.isdigit() or len(uid) > 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid student ID format")
    
    existing_recruit = db.query(Recruitment).filter(Recruitment.uid == uid).first()
    if not existing_recruit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Please submit application information first")
    
    if not resume_file.content_type == "application/pdf":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only PDF format files are supported")
    
    if resume_file.size and resume_file.size > MAX_FILE_SIZE:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File size cannot exceed 10MB")
    
    try:
        file_hash = hashlib.sha256(uid.encode()).hexdigest()
        filename = f"{file_hash}.pdf"
        file_path = RESUME_UPLOAD_DIR / filename
        
        content = await resume_file.read()
        
        if not content.startswith(b'%PDF'):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is not a valid PDF format")
        
        with open(file_path, "wb") as f:
            f.write(content)
        
        return {"message": "简历上传成功", "filename": filename}
        
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"File upload failed: {str(e)}")


class RecruitItem(BaseModel):
    name: str
    uid: str
    render: bool
    degree: int
    grade: int
    major_name: str
    college_name: str
    phone: str
    office_department_willing: int
    competition_department_willing: int
    activity_department_willing: int
    research_department_willing: int
    if_agree_to_be_reassigned: bool
    if_be_member: bool
    introduction: str
    skill: str
    status: str
    assigned_department: str
    interview_status: str = "first_round"
    interview_completed: bool = False
    first_round_passed: bool = False
    second_round_passed: bool = False
    is_admitted: bool = False
    admission_time: Optional[datetime] = None
    evaluation_status: str = "pending"

class RecruitResponse(BaseModel):
    recruits: list[RecruitItem]
    total: int

@router.get("/recruits", response_model=RecruitResponse, tags=["admin"])
def show_recruit_list(
    page: int = 1, size: int = 8, name: str = None, uid: str = None, degree: str = None, grade: str = None, major_name: str = None, status: str = None, department: str = None, all: bool = False,
    db: Session = Depends(get_db),
):
    recruitments = db.query(Recruitment)
    if name:
        recruitments = recruitments.filter(Recruitment.name.like(f"%{name}%"))
    if uid:
        recruitments = recruitments.filter(Recruitment.uid.like(f"%{uid}%"))
    if degree:
        recruitments = recruitments.filter(Recruitment.degree == int(degree))
    if grade:
        recruitments = recruitments.filter(Recruitment.grade == int(grade))
    if major_name:
        recruitments = recruitments.filter(Recruitment.major_name.like(f"%{major_name}%"))
    if status and status != 'all':
        if status == '待面试':
            recruitments = recruitments.filter(Recruitment.interview_status != 'first_round')
        elif status == '已通过一面':
            recruitments = recruitments.filter(
                Recruitment.interview_status == 'first_round',
                Recruitment.first_round_passed == False
            )
        elif status == '已通过二面':
            recruitments = recruitments.filter(
                Recruitment.first_round_passed == True,
                Recruitment.second_round_passed == False
            )
        elif status == '待录取':
            recruitments = recruitments.filter(
                Recruitment.second_round_passed == True,
                Recruitment.is_admitted == False
            )
        elif status == '已录取':
            recruitments = recruitments.filter(Recruitment.is_admitted == True)
    if department and department != 'all':
        recruitments = recruitments.filter(Recruitment.assigned_department == department)
    
    total = recruitments.count()
    
    if not all:
        recruitments = recruitments.offset((page - 1) * size).limit(size)
    
    result_list = []
    for recruit in recruitments:
        result_list.append(RecruitItem(
            name=recruit.name,
            uid=recruit.uid,
            render=recruit.render,
            degree=recruit.degree,
            grade=recruit.grade,
            major_name=recruit.major_name,
            college_name=recruit.college_name,
            phone=recruit.phone,
            office_department_willing=recruit.office_department_willing,
            competition_department_willing=recruit.competition_department_willing,
            activity_department_willing=recruit.activity_department_willing,
            research_department_willing=recruit.research_department_willing,
            if_agree_to_be_reassigned=recruit.if_agree_to_be_reassigned,
            if_be_member=recruit.if_be_member,
            introduction=recruit.introduction or '',
            skill=recruit.skill or '',
            status=recruit.evaluation_status or 'pending',
            assigned_department=recruit.assigned_department or '',
            interview_status=recruit.interview_status or 'first_round',
            interview_completed=recruit.interview_completed or False,
            first_round_passed=recruit.first_round_passed or False,
            second_round_passed=recruit.second_round_passed or False,
            is_admitted=recruit.is_admitted or False,
            evaluation_status=recruit.evaluation_status or 'pending',
            admission_time=recruit.admission_time,
        ))
    
    return RecruitResponse(recruits=result_list, total=total)


class EvaluationAdd(BaseModel):
    uid: str
    comment: str
    department: str = ""
    technical_skills: Optional[float] = None
    communication_skills: Optional[float] = None
    problem_solving: Optional[float] = None
    teamwork: Optional[float] = None
    learning_ability: Optional[float] = None
    motivation: Optional[float] = None
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    result: Optional[str] = "pending"
    recommended_department: Optional[str] = None


@router.post("/add_evaluation", tags=["admin"])
def add_evaluation(
    data: EvaluationAdd,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Current administrator does not have permission to perform this operation"
        )
    
    recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recruit not found"
        )
    
    admin = db.query(Admin).filter(Admin.aid == int(aid)).first()
    if admin and admin.uid:
        user = db.query(User).filter(User.uid == admin.uid).first()
        evaluator_name = user.nick if user else f"管理员{aid}"
    else:
        evaluator_name = f"管理员{aid}"
    
    try:
        new_evaluation = Evaluation(
            uid=data.uid,
            evaluator_id=aid,
            evaluator_name=evaluator_name,
            evaluation_comment=data.comment,
            department=data.department,
            technical_skills=data.technical_skills,
            communication_skills=data.communication_skills,
            problem_solving=data.problem_solving,
            teamwork=data.teamwork,
            learning_ability=data.learning_ability,
            motivation=data.motivation,
            strengths=data.strengths,
            weaknesses=data.weaknesses,
            result=data.result,
            recommended_department=data.recommended_department
        )
        
        overall_score = new_evaluation.calculate_overall_score()
        if overall_score is not None:
            new_evaluation.overall_score = overall_score
        
        db.add(new_evaluation)
        db.commit()
        
        return {"message": "评价添加成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error occurred when adding evaluation: {e}"
        )


class EvaluationListResponse(BaseModel):
    evaluations: list[dict]
    total: int


@router.get("/evaluations/{uid}", response_model=EvaluationListResponse, tags=["admin"])
def get_evaluations(
    uid: str,
    db: Session = Depends(get_db),
):
    
    evaluations = db.query(Evaluation).filter(Evaluation.uid == uid).order_by(Evaluation.evaluation_time.desc()).all()
    
    evaluation_list = []
    for eval in evaluations:
        evaluation_list.append({
            "id": eval.id,
            "evaluator_name": eval.evaluator_name,
            "evaluation_comment": eval.evaluation_comment,
            "evaluation_time": eval.evaluation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "department": eval.department,
            "technical_skills": eval.technical_skills,
            "communication_skills": eval.communication_skills,
            "problem_solving": eval.problem_solving,
            "teamwork": eval.teamwork,
            "learning_ability": eval.learning_ability,
            "motivation": eval.motivation,
            "overall_score": eval.overall_score,
            "strengths": eval.strengths,
            "weaknesses": eval.weaknesses,
            "result": eval.result,
            "recommended_department": eval.recommended_department
        })
    
    return EvaluationListResponse(evaluations=evaluation_list, total=len(evaluation_list))




class InterviewPassRequest(BaseModel):
    uid: str


@router.post("/interview-pass", tags=["recruit"])
def interview_pass(
    request: InterviewPassRequest,
    db: Session = Depends(get_db),
):
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="Recruit not found")
        
        if request.round_type == 'first_round':
            recruit.first_round_passed = True
            recruit.interview_status = 'second_round'
            recruit.interview_completed = False
            title = "浙江大学学生网络空间安全协会（ZJUCSA）第一轮面试通过"
            description = f"""亲爱的 {recruit.name} 同学！

恭喜你！你已成功通过浙江大学学生网络空间安全协会（ZJUCSA）的第一轮面试！

【面试结果】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：第一轮面试
• 面试结果：通过

【后续安排】
你将进入第二轮面试环节。第二轮面试的具体时间、地点和形式将通过钉钉OA另行通知，请保持关注。

【面试建议】
• 请继续关注网络安全相关知识
• 准备第二轮面试的相关材料
• 保持手机畅通，及时查看钉钉OA消息

【联系方式】
如有任何疑问，请通过以下方式联系我们：
• 邮箱：csa@zju.edu.cn
• 钉钉OA：CSA官方账号

再次恭喜你通过第一轮面试！我们期待在第二轮面试中与你再次相见！

连心为网，筑梦为安！
浙江大学学生网络空间安全协会（ZJUCSA）"""
            
        elif request.round_type == 'second_round':
            recruit.second_round_passed = True
            recruit.interview_status = 'completed'  
            recruit.interview_completed = True  
            
            
            title = "浙江大学学生网络空间安全协会（ZJUCSA）第二轮面试通过"
            description = f"""亲爱的 {recruit.name} 同学！

恭喜你！你已成功通过浙江大学学生网络空间安全协会（ZJUCSA）的第二轮面试！

【面试结果】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：第二轮面试
• 面试结果：通过

【后续安排】
你的面试流程已经完成，接下来将进入部门分配和最终录取环节。具体安排将通过钉钉OA另行通知，请保持关注。

【重要提醒】
• 请继续关注钉钉OA消息
• 如有任何疑问，请及时联系我们
• 保持手机畅通

【联系方式】
如有任何疑问，请通过以下方式联系我们：
• 邮箱：csa@zju.edu.cn

恭喜你成功完成所有面试环节！我们期待你成为ZJUCSA大家庭的一员！

连心为网，筑梦为安！
浙江大学学生网络空间安全协会（ZJUCSA）"""
        
        try:
            success = send_dingtalk_message_to_user(
                user_id=recruit.uid,
                title=title,
                description=description
            )
            if success:
                print(f"Interview pass notification sent successfully: {recruit.uid}")
            else:
                print(f"Interview pass notification failed: {recruit.uid}")
        except Exception as e:
            print(f"Error sending interview pass notification: {e}")
        
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





@router.get("/recruit-detail/{uid}", tags=["recruit"])
def get_recruit_detail(
    uid: str,
    db: Session = Depends(get_db),
):
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
        "assigned_department": recruit.assigned_department,
        "evaluation_status": recruit.evaluation_status,
        "evaluator_id": recruit.evaluator_id,
        "evaluation_time": recruit.evaluation_time,
        "is_admitted": recruit.is_admitted,
        "office_department_willing": recruit.office_department_willing,
        "competition_department_willing": recruit.competition_department_willing,
        "activity_department_willing": recruit.activity_department_willing,
        "research_department_willing": recruit.research_department_willing,
        "if_agree_to_be_reassigned": recruit.if_agree_to_be_reassigned,
        "if_be_member": recruit.if_be_member,
        "render": recruit.render
    }


class FinalAcceptRequest(BaseModel):
    uid: str
    department: str


@router.post("/final-accept", tags=["recruit"])
def final_accept(
    request: FinalAcceptRequest,
    db: Session = Depends(get_db),
):
    vx_number = {
        'office' : 's1764958267',
        'competition' : 'zsh15258751891',
        'research' : 'king_back123',
        'activity' : 'JXCzszszs'
    }
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="Recruit not found")
        
        if not recruit.first_round_passed:
            raise HTTPException(status_code=400, detail="Must pass first round first")
        
        if not recruit.second_round_passed:
            raise HTTPException(status_code=400, detail="Must pass second round first")
        
        if not request.department:
            raise HTTPException(status_code=400, detail="Must assign department first")
        
        recruit.is_admitted = True
        recruit.evaluation_status = 'accepted'
        recruit.admission_time = datetime.utcnow()
        recruit.assigned_department = request.department
        
        from models.member import Member
        
        existing_member = db.query(Member).filter(Member.uid == recruit.uid).first()

        if not existing_member:
            print(recruit.uid)
            member = Member(
                uid=recruit.uid,
                name=recruit.name,
                render=recruit.render,
                major_id=recruit.major_id,
                major_name=recruit.major_name,
                college_id=recruit.college_id,
                college_name=recruit.college_name,
                grade=recruit.grade,
                phone=recruit.phone,
                degree=recruit.degree,
                department=request.department,
                position="干事",
                skills=recruit.skill
            )
            db.add(member)
        
        raw_password = f"{recruit.uid[1:3]}CSA@{recruit.uid[-4:]}"
        pre_hashed_password = hashlib.sha256(raw_password.encode()).hexdigest() 
        db_stored_password = hash_passwd(pre_hashed_password)
        
        existing_user = db.query(User).filter_by(uid=recruit.uid).first()

        if not existing_user:
            user = User(
                uid = recruit.uid,
                nick = recruit.name,
                passwd = db_stored_password,
                email = recruit.email if hasattr(recruit, 'email') else "",
                last_login = 0,
                role_id = 1
            )
            db.add(user)
        else:
            existing_user.passwd = db_stored_password
            existing_user.role_id = 1
        
        
        db.commit()
        
        department_labels = {
            'office': '办公室部',
            'competition': '竞赛部', 
            'research': '科研部',
            'activity': '活动部'
        }
        
        department_name = department_labels.get(request.department, request.department)
        
        title = "浙江大学学生网络空间安全协会（ZJUCSA）录取通知"
        
        description = f"""亲爱的 {recruit.name} 同学！

恭喜你！我们很高兴地通知你，你已被浙江大学学生网络空间安全协会（ZJUCSA）正式录用为干事！

【录取信息】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 录取部门：{department_name}

【关于CSA】
浙江大学学生网络空间安全协会（ZJUCSA）是一个专注于网络空间安全技术学习、研究和实践的学术社团。我们致力于为对网络安全感兴趣的同学提供一个学习交流的平台，通过技术分享、竞赛培训、项目实践等多种形式，帮助成员提升专业技能。
•协会官网: csa.zju.edu.cn
•你的账号: {recruit.uid}
•你的密码: {raw_password}

【后续安排】
请添加部门部长微信: {vx_number[request.department]}

【联系方式】
如有任何疑问，请通过以下方式联系我们：
• 邮箱：csa@zju.edu.cn

再次恭喜你成为ZJUCSA大家庭的一员！我们期待与你一起在网络安全领域探索、学习、成长！

连心为网，筑梦为安！
浙江大学学生网络空间安全协会（ZJUCSA）
        """
        
        try:
            success = send_dingtalk_message_to_user(
                user_id=recruit.uid,
                title=title,
                description=description
            )
            if success:
                print(f"Admission notification sent successfully: {recruit.uid}")
            else:
                print(f"Admission notification failed: {recruit.uid}")
        except Exception as e:
            print(f"Error sending admission notification: {e}")
        
        return {"success": True, "message": "录取成功，录取通知已发送"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Admission operation failed: {str(e)}"
        )

@router.post("/final-reject", tags=["recruit"])
def final_reject_candidate(
    request: FinalAcceptRequest,
    db: Session = Depends(get_db),
):
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="Recruit not found")
        
        if recruit.is_admitted:
            raise HTTPException(status_code=400, detail="Cannot reject already admitted candidate")
        
        reject_stage = ""
        reject_message = ""
        
        if recruit.first_round_passed and not recruit.second_round_passed:
            reject_stage = "二面"
            reject_message = f"很遗憾，您在第二轮面试中未能通过。感谢您对ZJUCSA的关注，希望您继续努力！"
        elif recruit.first_round_passed and recruit.second_round_passed:
            reject_stage = "最终录取"
            reject_message = f"很遗憾，您在最终录取阶段未能通过。感谢您对ZJUCSA的关注，希望您继续努力！"
        elif not recruit.first_round_passed:
            reject_stage = "一面"
            reject_message = f"很遗憾，您在第一轮面试中未能通过。感谢您对ZJUCSA的关注，希望您继续努力！"
        else:
            reject_stage = "面试"
            reject_message = f"很遗憾，您在面试中未能通过。感谢您对ZJUCSA的关注，希望您继续努力！"
        
        recruit.evaluation_status = "rejected"
        recruit.is_admitted = False
        try:
            title = "浙江大学学生网络空间安全协会（ZJUCSA）面试结果通知"
            
            description = f"""亲爱的 {recruit.name} 同学：

{reject_message}

【面试信息】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：{reject_stage}
• 通知时间：{datetime.now().strftime('%Y年%m月%d日')}

【关于ZJUCSA】
浙江大学学生网络空间安全协会（ZJUCSA）是一个专注于网络空间安全技术学习、研究和实践的学术社团。

【后续建议】
虽然本次面试未能通过，但我们鼓励您继续关注网络安全领域的学习和发展。ZJUCSA会定期举办技术分享和培训活动，欢迎您继续参与。

【联系方式】
如有任何疑问，请通过以下方式联系我们：
• 邮箱：csa@zju.edu.cn

感谢您对ZJUCSA的关注和支持！

连心为网，筑梦为安！
浙江大学学生网络空间安全协会（ZJUCSA）
            """
            
            success = send_dingtalk_message_to_user(
                user_id=recruit.uid,
                title=title,
                description=description
            )
            if success:
                print(f"Rejection notification sent successfully: {recruit.uid}")
            else:
                print(f"Rejection notification failed: {recruit.uid}")
        except Exception as e:
            print(f"Error sending rejection notification: {e}")
        
        db.commit()
        
        return {"success": True, "message": f"拒绝成功！{reject_stage}失败通知已通过钉钉OA发送"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Rejection operation failed: {str(e)}"
        )
    
    


class AssignDepartment(BaseModel):
    uid: str
    department: str


class DeleteRecruit(BaseModel):
    uid: str


@router.post("/assign_department", tags=["admin"])
def assign_department(
    data: AssignDepartment,
    db: Session = Depends(get_db),
):
    recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recruit not found"
        )
    
    try:
        recruit.assigned_department = data.department
        db.commit()
        return {"message": "部门分配成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error occurred when assigning department: {e}"
        )


@router.post("/delete_recruit", tags=["admin"])
def delete_recruit(
    data: DeleteRecruit,
    db: Session = Depends(get_db),
):
    recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Recruitment record not found"
        )
    
    try:
        from models.interview import Interview
        
        interviews = db.query(Interview).filter(Interview.uid == data.uid).all()
        for interview in interviews:
            db.delete(interview)
        
        evaluations = db.query(Evaluation).filter(Evaluation.uid == data.uid).all()
        for evaluation in evaluations:
            db.delete(evaluation)
        
        db.delete(recruit)
        db.commit()
        
        return {"message": "纳新记录及相关数据删除成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error occurred when deleting recruitment record: {e}"
        )


@router.post("/delete_all_recruits", tags=["admin"])
def delete_all_recruits(
    db: Session = Depends(get_db),
):
    try:
        total_recruits = db.query(Recruitment).count()
        
        if total_recruits == 0:
            return {"message": "没有纳新记录需要删除", "deleted_count": 0}
        
        from models.interview import Interview
        
        interviews_deleted = db.query(Interview).delete()
        
        evaluations_deleted = db.query(Evaluation).delete()
        
        recruits_deleted = db.query(Recruitment).delete()
        
        db.commit()
        
        return {
            "message": f"成功删除所有纳新记录及相关数据",
            "deleted_count": recruits_deleted,
            "evaluations_deleted": evaluations_deleted,
            "interviews_deleted": interviews_deleted
        }
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error occurred when deleting all recruitment records: {e}"
        )


from urllib.parse import quote

@router.get("/export_recruits", tags=["admin"])
def export_recruits(
    db: Session = Depends(get_db),
    include_basic_info: str = "true",
    include_contact: str = "true",
    include_department_preference: str = "true",
    include_introduction: str = "true",
    include_evaluation: str = "true",
    export_format: str = "excel"
):
    try:
        include_basic_info_bool = include_basic_info.lower() == "true"
        include_contact_bool = include_contact.lower() == "true"
        include_department_preference_bool = include_department_preference.lower() == "true"
        include_introduction_bool = include_introduction.lower() == "true"
        include_evaluation_bool = include_evaluation.lower() == "true"
        
        recruitments = db.query(Recruitment).all()
        
        if not recruitments:
            data = []
        else:
            data = []
            for recruit in recruitments:
                try:
                    evaluations = db.query(Evaluation).filter(Evaluation.uid == recruit.uid).all()
                    evaluation_comments = [eval.evaluation_comment for eval in evaluations if eval.evaluation_comment]
                    
                    row_data = {}
                    
                    if include_basic_info_bool:
                        row_data.update({
                            '姓名': recruit.name or '',
                            '学号': recruit.uid or '',
                            '性别': '女' if recruit.render else '男',
                            '学位': {
                                0: '学士',
                                1: '硕士', 
                                2: '博士',
                                3: '博士后'
                            }.get(recruit.degree, '学士'),
                            '年级': f"{recruit.grade}级" if recruit.grade else '',
                            '专业': recruit.major_name or '',
                            '学院': recruit.college_name or '',
                        })
                    
                    if include_contact_bool:
                        row_data['手机号'] = recruit.phone or ''
                    
                    if include_department_preference_bool:
                        row_data.update({
                            '办公室部意愿': recruit.office_department_willing or 0,
                            '竞赛部意愿': recruit.competition_department_willing or 0,
                            '科研部意愿': recruit.research_department_willing or 0,
                            '活动部意愿': recruit.activity_department_willing or 0,
                            '同意调剂': '是' if recruit.if_agree_to_be_reassigned else '否',
                            '愿意成为会员': '是' if recruit.if_be_member else '否',
                        })
                    
                    if include_introduction_bool:
                        row_data.update({
                            '自我介绍': recruit.introduction or '',
                            '特长技能': recruit.skill or '',
                        })
                    
                    if include_evaluation_bool:
                        row_data.update({
                            '评价状态': {
                                'pending': '待评价',
                                'accepted': '已通过',
                                'rejected': '已拒绝'
                            }.get(recruit.evaluation_status, '待评价'),
                            '分配部门': {
                                'office': '办公室部',
                                'competition': '竞赛部',
                                'research': '科研部',
                                'activity': '活动部'
                            }.get(recruit.assigned_department, '未分配'),
                            '评价时间': recruit.evaluation_time.strftime('%Y-%m-%d %H:%M:%S') if recruit.evaluation_time else '',
                            '评价意见': '; '.join(evaluation_comments) if evaluation_comments else '',
                            '面试状态': {
                                'first_round': '一面',
                                'second_round': '二面',
                                'completed': '已完成'
                            }.get(recruit.interview_status, '一面'),
                            '面试完成': '是' if recruit.interview_completed else '否',
                            '一面通过': '是' if recruit.first_round_passed else '否',
                            '二面通过': '是' if recruit.second_round_passed else '否',
                            '是否录取': '是' if recruit.is_admitted else '否',
                            '录取时间': recruit.admission_time.strftime('%Y-%m-%d %H:%M:%S') if recruit.admission_time else ''
                        })
                    
                    data.append(row_data)
                except Exception as e:
                    print(f"Error processing record {recruit.uid}: {e}")
                    continue
        
        df = pd.DataFrame(data)

        filename_base = "纳新者数据"
        filename_encoded = quote(filename_base)
        
        if export_format.lower() == "csv":
            output = BytesIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)
            
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}.csv"
            }
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type="text/csv",
                headers=headers
            )
        else:
            try:
                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    df.to_excel(writer, sheet_name='纳新者数据', index=False)
                    
                    worksheet = writer.sheets['纳新者数据']
                    for column in worksheet.columns:
                        max_length = 0
                        column_letter = column[0].column_letter
                        for cell in column:
                            try:
                                if len(str(cell.value)) > max_length:
                                    max_length = len(str(cell.value))
                            except:
                                pass
                        adjusted_width = min(max_length + 2, 50)
                        worksheet.column_dimensions[column_letter].width = adjusted_width
                
                output.seek(0)
                
                headers = {
                    "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}.xlsx"
                }
                return StreamingResponse(
                    BytesIO(output.getvalue()),
                    media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers=headers
                )
            except ImportError:
                output = BytesIO()
                df.to_csv(output, index=False, encoding='utf-8-sig')
                output.seek(0)
                
                headers = {
                    "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}.csv"
                }
                return StreamingResponse(
                    BytesIO(output.getvalue()),
                    media_type="text/csv",
                    headers=headers
                )
        
    except Exception as e:
        import traceback
        print(f"Error occurred while exporting data: {e}")
        print(f"Error details: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Error occurred when exporting data: {str(e)}"
        )