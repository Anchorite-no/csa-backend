import pandas as pd
import hashlib
import os
import json
from pathlib import Path
from typing import Optional, List, Annotated
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status, UploadFile, File
from pydantic import BaseModel, Field, StringConstraints
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.model import aid_to_nick
from misc.auth import get_current_user, get_current_admin, login_required_admin
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
    interview_time_slots: List[str] = Field(default_factory=list, description="面试时间段选择")

@router.post("/recruit_confirm")
def confirm_recruit(data: RecruitItem, db: Session = Depends(get_db)):
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
        skill=data.skill,
        interview_time_slots=json.dumps(data.interview_time_slots),  # 将列表转换为JSON字符串
        evaluation_status="pending",
        evaluation_time=datetime.now(),
        evaluator_id="",
        assigned_department=""
    )
    try:   
        db.add(new_recruit)
        db.commit()
        
        # 发送钉钉通知消息
        # 恭喜 {data.name} 同学！

        # 你已成功提交浙江大学学生网络空间安全协会（ZJUCSA）的招新报名申请。

        # 首先，衷心感谢你对CSA的关注与认可。我们非常期待能有更多像你一样对网络空间安全充满热情的同学加入我们，一同探索未知的技术领域。

        # 我们已经收到了你的申请，并会尽快进行筛选。面试安排将通过钉钉OA、短信或电话形式通知你，请务必保持手机畅通，以便及时获取最新信息。

        # 在面试中，我们希望有机会能更深入地了解你，听听你对网络安全的热爱与见解。无论你对Web安全、二进制安全还是其他方向感兴趣，我们都鼓励你勇敢展示自己，分享你的思考。

        # CSA不仅是一个学习技术、共同进步的平台，更是一个充满活力、互帮互助的大家庭。我们期待与你携手，共同探索网络世界的无限可能，在CSA的大家庭中共同成长。

        # 主要注意！ 招新报名表一旦提交不可修改或重复提交，如有任何疑问，请发送邮件至csa@zju.edu.cn

        # 最后期待你的加入！连心为网，筑梦为安，让我们在新的一年里携手共进，共创辉煌！
        
        title = "浙江大学学生网络空间安全协会（ZJUCSA）招新报名成功通知"

        description = f"""亲爱的 {data.name} 同学！\n你已成功提交浙江大学学生网络空间安全协会（ZJUCSA）的招新报名申请。\n\n首先，衷心感谢你对CSA的关注与认可。我们非常期待能有更多像你一样对网络空间安全充满热情的同学加入我们，一同探索未知的技术领域。\n我们已经收到了你的申请，并会尽快进行筛选。面试安排将通过钉钉OA、短信或电话形式通知你，请务必保持手机畅通，以便及时获取最新信息。\n在面试中，我们希望有机会能更深入地了解你，听听你对网络安全的热爱与见解。无论你对Web安全、二进制安全还是其他方向感兴趣，我们都鼓励你勇敢展示自己，分享你的思考。\nCSA不仅是一个学习技术、共同进步的平台，更是一个充满活力、互帮互助的大家庭。我们期待与你携手，共同探索网络世界的无限可能，在CSA的大家庭中共同成长。\n注意！ 招新报名表一旦提交不可修改或重复提交，如有任何疑问，请发送邮件至csa@zju.edu.cn\n连心为网，筑梦为安，期待你的加入！
        """

        try:
            success = send_dingtalk_message_to_user(
                user_id=data.uid,
                title=title,
                description=description,
                # link="https://csa.zju.edu.cn"
            )
            if success:
                print(f"钉钉通知发送成功: {data.uid}")
            else:
                print(f"钉钉通知发送失败: {data.uid}")
        except Exception as e:
            print(f"发送钉钉通知时出错: {e}")
        
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
    page: int = 1, size: int = 8, name: str = None, uid: str = None, degree: str = None, grade: str = None, major_name: str = None, status: str = None, department: str = None,
    db: Session = Depends(get_db),
        # aid: str = Depends(get_current_admin),
):
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
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
        # 根据新的状态进行筛选
        if status == '待面试':
            # 面试状态不是first_round的
            recruitments = recruitments.filter(Recruitment.interview_status != 'first_round')
        elif status == '已通过一面':
            # 面试状态是first_round但还没通过一面的
            recruitments = recruitments.filter(
                Recruitment.interview_status == 'first_round',
                Recruitment.first_round_passed == False
            )
        elif status == '已通过二面':
            # 已通过一面但还没通过二面的
            recruitments = recruitments.filter(
                Recruitment.first_round_passed == True,
                Recruitment.second_round_passed == False
            )
        elif status == '待录取':
            # 已通过二面但还没录取的
            recruitments = recruitments.filter(
                Recruitment.second_round_passed == True,
                Recruitment.is_admitted == False
            )
        elif status == '已录取':
            # 已录取的
            recruitments = recruitments.filter(Recruitment.is_admitted == True)
    if department and department != 'all':
        recruitments = recruitments.filter(Recruitment.assigned_department == department)
    
    # 获取总数
    total = recruitments.count()
    
    # 应用分页
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
    # 评分项目（1-10分）
    technical_skills: Optional[float] = None
    communication_skills: Optional[float] = None
    problem_solving: Optional[float] = None
    teamwork: Optional[float] = None
    learning_ability: Optional[float] = None
    motivation: Optional[float] = None
    # 总体评价
    strengths: Optional[str] = None
    weaknesses: Optional[str] = None
    # 评价结果
    result: Optional[str] = "pending"
    # 推荐部门
    recommended_department: Optional[str] = None


@router.post("/add_evaluation", tags=["admin"])
def add_evaluation(
    data: EvaluationAdd,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
        )
    
    recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="纳新者未找到"
        )
    
    # 获取评价人信息
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
            # 评分项目
            technical_skills=data.technical_skills,
            communication_skills=data.communication_skills,
            problem_solving=data.problem_solving,
            teamwork=data.teamwork,
            learning_ability=data.learning_ability,
            motivation=data.motivation,
            # 总体评价
            strengths=data.strengths,
            weaknesses=data.weaknesses,
            # 评价结果
            result=data.result,
            # 推荐部门
            recommended_department=data.recommended_department
        )
        
        # 计算总体评分
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
            detail=f"添加评价时发生错误: {e}"
        )


class EvaluationListResponse(BaseModel):
    evaluations: list[dict]
    total: int


@router.get("/evaluations/{uid}", response_model=EvaluationListResponse, tags=["admin"])
def get_evaluations(
    uid: str,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    evaluations = db.query(Evaluation).filter(Evaluation.uid == uid).order_by(Evaluation.evaluation_time.desc()).all()
    
    evaluation_list = []
    for eval in evaluations:
        evaluation_list.append({
            "id": eval.id,
            "evaluator_name": eval.evaluator_name,
            "evaluation_comment": eval.evaluation_comment,
            "evaluation_time": eval.evaluation_time.strftime("%Y-%m-%d %H:%M:%S"),
            "department": eval.department,
            # 评分项目
            "technical_skills": eval.technical_skills,
            "communication_skills": eval.communication_skills,
            "problem_solving": eval.problem_solving,
            "teamwork": eval.teamwork,
            "learning_ability": eval.learning_ability,
            "motivation": eval.motivation,
            # 总体评分
            "overall_score": eval.overall_score,
            # 总体评价
            "strengths": eval.strengths,
            "weaknesses": eval.weaknesses,
            # 评价结果
            "result": eval.result,
            # 推荐部门
            "recommended_department": eval.recommended_department
        })
    
    return EvaluationListResponse(evaluations=evaluation_list, total=len(evaluation_list))




class InterviewPassRequest(BaseModel):
    uid: str
    round_type: str  # 'first_round' 或 'second_round'


@router.post("/interview-pass", tags=["recruit"])
def interview_pass(
    request: InterviewPassRequest,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """面试通过处理（纳新管理页面）"""
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
            
            # 发送一面通过通知
            title = "浙江大学学生网络空间安全协会（ZJUCSA）第一轮面试通过"
            description = f"""亲爱的 {recruit.name} 同学！

恭喜你！你已成功通过浙江大学学生网络空间安全协会（ZJUCSA）的第一轮面试！

【面试结果】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：第一轮面试
• 面试结果：通过
• 通过时间：{datetime.now().strftime('%Y年%m月%d日')}

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
            # 二面通过
            recruit.second_round_passed = True
            recruit.interview_status = 'completed'  # 面试完成
            recruit.interview_completed = True  # 面试完成
            
            # 发送二面通过通知
            title = "浙江大学学生网络空间安全协会（ZJUCSA）第二轮面试通过"
            description = f"""亲爱的 {recruit.name} 同学！

恭喜你！你已成功通过浙江大学学生网络空间安全协会（ZJUCSA）的第二轮面试！

【面试结果】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：第二轮面试
• 面试结果：通过
• 通过时间：{datetime.now().strftime('%Y年%m月%d日')}

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
        
        # 发送钉钉通知
        try:
            success = send_dingtalk_message_to_user(
                user_id=recruit.uid,
                title=title,
                description=description
            )
            if success:
                print(f"面试通过通知发送成功: {recruit.uid}")
            else:
                print(f"面试通过通知发送失败: {recruit.uid}")
        except Exception as e:
            print(f"发送面试通过通知时出错: {e}")
        
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





@router.get("/recruit-detail/{uid}", tags=["recruit"])
def get_recruit_detail(
    uid: str,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    # """获取纳新者详细信息（包含面试通过状态）"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
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
        "assigned_department": recruit.assigned_department,
        "evaluation_status": recruit.evaluation_status,
        "evaluator_id": recruit.evaluator_id,
        "evaluation_time": recruit.evaluation_time,
        "is_admitted": recruit.is_admitted,
    }


class FinalAcceptRequest(BaseModel):
    uid: str
    department: str


@router.post("/final-accept", tags=["recruit"])
def final_accept(
    request: FinalAcceptRequest,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    vx_number = {
        'office' : 's1764958267',
        'competition' : 'zsh15258751891',
        'research' : 'king_back123',
        'activity' : 'JXCzszszs'
    }
    """最终录取并发送钉钉通知"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="纳新者不存在")
        
        # 检查前置条件
        if not recruit.first_round_passed:
            raise HTTPException(status_code=400, detail="必须先通过一面")
        
        if not recruit.second_round_passed:
            raise HTTPException(status_code=400, detail="必须先通过二面")
        
        if not request.department:
            raise HTTPException(status_code=400, detail="必须先分配部门")
        
        # 更新状态为录取
        recruit.is_admitted = True
        recruit.evaluation_status = 'accepted'
        recruit.admission_time = datetime.utcnow()
        recruit.assigned_department = request.department
        
        # 创建干事记录（数据迁移）
        from models.member import Member
        
        # 检查是否已存在干事记录
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
        
        db.commit()
        
        # 发送钉钉录取通知
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
• 录取时间：{datetime.now().strftime('%Y年%m月%d日')}

【关于CSA】
浙江大学学生网络空间安全协会（ZJUCSA）是一个专注于网络空间安全技术学习、研究和实践的学术社团。我们致力于为对网络安全感兴趣的同学提供一个学习交流的平台，通过技术分享、竞赛培训、项目实践等多种形式，帮助成员提升专业技能。

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
                print(f"录取通知发送成功: {recruit.uid}")
            else:
                print(f"录取通知发送失败: {recruit.uid}")
        except Exception as e:
            print(f"发送录取通知时出错: {e}")
        
        return {"success": True, "message": "录取成功，录取通知已发送"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"录取操作失败: {str(e)}"
        )

# 最终拒绝API
@router.post("/final-reject", tags=["recruit"])
def final_reject_candidate(
    request: FinalAcceptRequest,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """最终拒绝候选人"""
    try:
        # 查找纳新者
        recruit = db.query(Recruitment).filter(Recruitment.uid == request.uid).first()
        if not recruit:
            raise HTTPException(status_code=404, detail="纳新者不存在")
        
        # 检查是否已经录取
        if recruit.is_admitted:
            raise HTTPException(status_code=400, detail="已录取的候选人不能拒绝")
        

        
        # 确定拒绝阶段和消息
        reject_stage = ""
        reject_message = ""
        
        if recruit.first_round_passed and not recruit.second_round_passed:
            # 已通过一面，拒绝二面
            reject_stage = "二面"
            reject_message = f"很遗憾，您在第二轮面试中未能通过。感谢您对CSA的关注，希望您继续努力！"
        elif recruit.first_round_passed and recruit.second_round_passed:
            # 已通过一面和二面，拒绝最终录取
            reject_stage = "最终录取"
            reject_message = f"很遗憾，您在最终录取阶段未能通过。感谢您对CSA的关注，希望您继续努力！"
        elif not recruit.first_round_passed:
            # 未通过一面，拒绝一面
            reject_stage = "一面"
            reject_message = f"很遗憾，您在第一轮面试中未能通过。感谢您对CSA的关注，希望您继续努力！"
        else:
            # 其他情况
            reject_stage = "面试"
            reject_message = f"很遗憾，您在面试中未能通过。感谢您对CSA的关注，希望您继续努力！"
        
        # 更新状态为拒绝
        recruit.evaluation_status = "rejected"
        recruit.is_admitted = False
        
        # 发送钉钉通知
        try:
            title = "浙江大学学生网络空间安全协会（ZJUCSA）面试结果通知"
            
            description = f"""亲爱的 {recruit.name} 同学：

{reject_message}

【面试信息】
• 姓名：{recruit.name}
• 学号：{recruit.uid}
• 面试阶段：{reject_stage}
• 通知时间：{datetime.now().strftime('%Y年%m月%d日')}

【关于CSA】
浙江大学学生网络空间安全协会（ZJUCSA）是一个专注于网络空间安全技术学习、研究和实践的学术社团。

【后续建议】
虽然本次面试未能通过，但我们鼓励您继续关注网络安全领域的学习和发展。CSA会定期举办技术分享和培训活动，欢迎您继续参与。

【联系方式】
如有任何疑问，请通过以下方式联系我们：
• 邮箱：csa@zju.edu.cn

感谢您对CSA的关注和支持！

连心为网，筑梦为安！
浙江大学学生网络空间安全协会（ZJUCSA）
            """
            
            success = send_dingtalk_message_to_user(
                user_id=recruit.uid,
                title=title,
                description=description
            )
            if success:
                print(f"拒绝通知发送成功: {recruit.uid}")
            else:
                print(f"拒绝通知发送失败: {recruit.uid}")
        except Exception as e:
            print(f"发送拒绝通知时出错: {e}")
        
        db.commit()
        
        return {"success": True, "message": f"拒绝成功！{reject_stage}失败通知已通过钉钉OA发送"}
        
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"拒绝操作失败: {str(e)}"
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
    # aid: str = Depends(get_current_admin),
):
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="纳新者未找到"
        )
    
    try:
        recruit.assigned_department = data.department
        db.commit()
        return {"message": "部门分配成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"分配部门时发生错误: {e}"
        )


@router.post("/delete_recruit", tags=["admin"])
def delete_recruit(
    data: DeleteRecruit,
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """删除纳新记录"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    recruit = db.query(Recruitment).filter(Recruitment.uid == data.uid).first()
    if not recruit:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="纳新记录未找到"
        )
    
    try:
        # 需要导入Interview模型
        from models.interview import Interview
        
        # 先删除相关的面试记录
        interviews = db.query(Interview).filter(Interview.uid == data.uid).all()
        for interview in interviews:
            db.delete(interview)
        
        # 删除相关的评价记录
        evaluations = db.query(Evaluation).filter(Evaluation.uid == data.uid).all()
        for evaluation in evaluations:
            db.delete(evaluation)
        
        # 删除纳新记录
        db.delete(recruit)
        db.commit()
        
        return {"message": "纳新记录及相关数据删除成功"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"删除纳新记录时发生错误: {e}"
        )


@router.post("/delete_all_recruits", tags=["admin"])
def delete_all_recruits(
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
):
    """删除所有纳新记录"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 获取所有纳新记录数量
        total_recruits = db.query(Recruitment).count()
        
        if total_recruits == 0:
            return {"message": "没有纳新记录需要删除", "deleted_count": 0}
        
        # 需要导入Interview模型
        from models.interview import Interview
        
        # 先删除所有相关的面试记录
        interviews_deleted = db.query(Interview).delete()
        
        # 删除所有相关的评价记录
        evaluations_deleted = db.query(Evaluation).delete()
        
        # 删除所有纳新记录
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
            detail=f"删除所有纳新记录时发生错误: {e}"
        )


from urllib.parse import quote

@router.get("/export_recruits", tags=["admin"])
def export_recruits(
    db: Session = Depends(get_db),
    # aid: str = Depends(get_current_admin),
    include_basic_info: str = "true",
    include_contact: str = "true",
    include_department_preference: str = "true",
    include_introduction: str = "true",
    include_evaluation: str = "true",
    export_format: str = "excel"
):
    """导出纳新者数据为Excel文件"""
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
    #     )
    
    try:
        # 转换字符串参数为布尔值
        include_basic_info_bool = include_basic_info.lower() == "true"
        include_contact_bool = include_contact.lower() == "true"
        include_department_preference_bool = include_department_preference.lower() == "true"
        include_introduction_bool = include_introduction.lower() == "true"
        include_evaluation_bool = include_evaluation.lower() == "true"
        
        # 获取所有纳新者数据
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
                            '学位': '硕士' if recruit.degree == 1 else '博士',
                            '年级': recruit.grade or '',
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
                            '状态': {
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
                            '评价意见': '; '.join(evaluation_comments) if evaluation_comments else ''
                        })
                    
                    data.append(row_data)
                except Exception as e:
                    print(f"处理记录 {recruit.uid} 时出错: {e}")
                    continue
        
        df = pd.DataFrame(data)

        # 核心改动：对文件名进行URL编码
        filename_base = "纳新者数据"
        filename_encoded = quote(filename_base)
        
        if export_format.lower() == "csv":
            output = BytesIO()
            df.to_csv(output, index=False, encoding='utf-8-sig')
            output.seek(0)
            
            # 使用编码后的文件名
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}.csv"
            }
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type="text/csv",
                headers=headers
            )
        else:
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
            
            # 使用编码后的文件名
            headers = {
                "Content-Disposition": f"attachment; filename*=UTF-8''{filename_encoded}.xlsx"
            }
            return StreamingResponse(
                BytesIO(output.getvalue()),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers=headers
            )
        
    except Exception as e:
        import traceback
        print(f"导出数据时发生错误: {e}")
        print(f"错误详情: {traceback.format_exc()}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"导出数据时发生错误: {str(e)}"
        )