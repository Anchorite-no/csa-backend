import time
from datetime import timedelta, datetime
from hashlib import sha256
from typing import Annotated, Optional
import smtplib
from email.mime.text import MIMEText
from email.header import Header

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session
import csv

from config import get_config
from misc.auth import (
    create_access_token,
    get_current_user,
    get_current_user_flexible,
    hash_passwd,
    verify_passwd,
    create_access_token_admin,
)
from models import get_db
from models.event import Event
from models.participation import Participation
from models.user import User
from models.admin import Admin
from models.member import Member
from models.role import User_Role, Admin_Role

router = APIRouter()


class UserLogin(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    passwd: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    ]


class UserToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPasswd(BaseModel):
    old: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    ]
    new: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    ]


class UserRegister(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    nick: Annotated[str, Field(min_length=2, max_length=30)]
    code: str
    email: EmailStr
    verify_code: str


class ConciseEvent(BaseModel):
    eid: int
    title: str
    start_time: int
    end_time: int
    place: str
    image: str


class ParticipationItem(BaseModel):
    uid: str
    nick: str
    signin_time: Optional[int] = None
    event: ConciseEvent


class WxUserLogin(BaseModel):
    code: str


class AdminLogin(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    
    passwd: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    ]


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"

@router.post("/login", tags=["user", "admin"])
def login(data: UserLogin, db: Session = Depends(get_db)):

    user = db.query(User).filter_by(uid=data.uid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not verify_passwd(data.passwd, user.passwd.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    admin = db.query(Admin).filter_by(uid=data.uid).first()
    
    if admin and admin.is_active:
        admin_token = create_access_token_admin(
            aid=admin.aid, uid=user.uid, expires_delta=timedelta(hours=2), nick=user.nick
        )
        user.last_login = int(time.time())
        db.commit()
        return AdminToken(access_token=admin_token)
    else:
        user_token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)
        user.last_login = int(time.time())
        db.commit()
        return UserToken(access_token=user_token)


@router.post("/wxlogin", response_model=UserToken, tags=["user"])
def wxlogin(data: WxUserLogin, db: Session = Depends(get_db)):
    
    miniapp_url = "https://api.weixin.qq.com/sns/jscode2session"
    miniapp_params = {
        "appid": get_config("WEIXIN_APP_ID"),
        "secret": get_config("WEIXIN_APP_SECRET"),
        "js_code": data.code,
        "grant_type": "authorization_code",
    }

    miniapp_resp = requests.get(miniapp_url, params=miniapp_params)

    if miniapp_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Miniapp server error")

    miniapp_resp_json = miniapp_resp.json()
    openid = miniapp_resp_json.get("openid")

    if not openid:
        raise HTTPException(status_code=400, detail="WeChat login error")

    user = db.query(User).filter_by(openid=openid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)

    user.last_login = int(time.time())
    db.commit()

    return UserToken(access_token=token)
    

@router.post("/token", response_model=UserToken, tags=["user"])
def token(data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(uid=data.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User not found"
        )

    if not verify_passwd(sha256(data.password.encode()).hexdigest(), user.passwd):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)

    user.last_login = int(time.time())
    db.commit()

    return UserToken(access_token=token)


@router.post("/passwd", tags=["user"])
def passwd(
    data: UserPasswd,
    db: Session = Depends(get_db),
    uid: str = Depends(get_current_user_flexible),
):
    user = db.query(User).filter_by(uid=uid).first()

    if not verify_passwd(data.old, user.passwd):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect original password"
        )

    if data.old == data.new:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="New password cannot be the same as old password"
        )

    user.passwd = hash_passwd(data.new)

    db.commit()

    return {"result": "PasswdReset Successfully"}


class UserID(BaseModel):
    uid: str


@router.post("/verify_code", tags=["user"])
def verify(data: UserID):
    host = get_config("SMTP_HOST")
    port = get_config("SMTP_PORT")
    user = get_config("SMTP_USER")
    passwd = get_config("SMTP_PASSWD")

    token = get_config("CSA_SECRET_KEY")
    date = time.strftime("%Y-%m-%d", time.localtime())

    verify_code = sha256(f"{data.uid}{token}{date}".encode()).hexdigest()
    verify_code = int(verify_code, 16) % 1000000
    verify_code = str(verify_code).zfill(6)

    title = "验证码 - 浙江大学学生网络空间安全协会"
    content = f"""亲爱的同学:

感谢您选择加入浙江大学学生网络空间安全协会！
您的验证码是: {verify_code}

浙江大学学生网络空间安全协会
    """
    
    message = MIMEText(content, 'plain', 'utf-8')
    message['From'] = Header("ZJUCSA", 'ascii')
    message['To'] =  Header(data.uid, 'ascii')
    message['Subject'] = Header(title, 'utf-8')
    
    if not data.uid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Please check student ID",
        )
    
    target = data.uid + "@zju.edu.cn"

    try:
        server = smtplib.SMTP_SSL(host, port)
        server.login(user, passwd)
        server.sendmail(user, target, message.as_string())
        server.quit()
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Verification code sending failed",
        )
    
    return {"msg": "success"}


@router.post("/register", tags=["user"])
def register(data: UserRegister, db: Session = Depends(get_db)):

    miniapp_url = "https://api.weixin.qq.com/sns/jscode2session"
    miniapp_params = {
        "appid": get_config("WEIXIN_APP_ID"),
        "secret": get_config("WEIXIN_APP_SECRET"),
        "js_code": data.code,
        "grant_type": "authorization_code",
    }

    miniapp_resp = requests.get(miniapp_url, params=miniapp_params)

    print(miniapp_resp.json())

    if miniapp_resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Miniapp server error")

    miniapp_resp_json = miniapp_resp.json()
    openid = miniapp_resp_json.get("openid")

    if not openid:
        raise HTTPException(status_code=400, detail="Invalid code")

    user = db.query(User).filter_by(uid=data.uid).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User already exists"
        )

    email = db.query(User).filter_by(email=data.email).first()
    if email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    existed = db.query(User).filter_by(openid=openid).first()
    if existed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="This WeChat is already bound"
        )

    token = get_config("CSA_SECRET_KEY")
    date = time.strftime("%Y-%m-%d", time.localtime())
    verify_code = sha256(f"{data.uid}{token}{date}".encode()).hexdigest()
    verify_code = int(verify_code, 16) % 1000000
    verify_code = str(verify_code).zfill(6)

    if verify_code != data.verify_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect verification code"
        )

    try:
        new_user = User(
            uid=data.uid,
            nick=data.nick,
            openid=openid,
            email=data.email,
            last_login=0,
            role_id=1,
        )

        db.add(new_user)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"An error occurred when registering: {e}",
        )

    return {"msg": "success"}


class ParticipationResponse(BaseModel):
    count: int
    result: list[ParticipationItem]


@router.get("/participations", response_model=ParticipationResponse)
def get_participations(
    uid: str = Depends(get_current_user_flexible),
    page: int = 1,
    size: int = 8,
    db: Session = Depends(get_db),
):
    participations = (
        db.query(Participation, User, Event)
        .join(User, Participation.uid == User.uid)
        .join(Event, Participation.eid == Event.eid)
        .filter(Participation.uid == uid)
        .order_by(Participation.signup_time.desc())
    )

    count = participations.count()

    participations = participations.offset((page - 1) * size)
    participations = participations.limit(size)
    participations = participations.all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            nick=user.nick,
            signin_time=participation.signin_time,  # 签到时间
            event=ConciseEvent(
                eid=event.eid,
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                place=event.place,
                image=event.image,
            ),
        )
        for participation, user, event in participations
    ]

    return ParticipationResponse(count=count, result=participation_items)


@router.get("/available_event", response_model=ParticipationResponse)
def get_available_event(
    uid: str = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    participations = (
        db.query(Participation, User, Event)
        .join(User, Participation.uid == User.uid)
        .join(Event, Participation.eid == Event.eid)
        .filter(Participation.uid == uid)
        .filter(Event.end_signin_time > int(time.time()))
        .filter(Event.start_signin_time < int(time.time()))
        .order_by(Participation.signup_time.desc())
    )

    count = participations.count()
    participations = participations.all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            nick=user.nick,
            signin_time=participation.signin_time,  # 签到时间
            event=ConciseEvent(
                eid=event.eid,
                title=event.title,
                start_time=event.start_time,
                end_time=event.end_time,
                place=event.place,
                image=event.image,
            ),
        )
        for participation, user, event in participations
    ]

    return ParticipationResponse(count=count, result=participation_items)


@router.get("/check_participation")
def check_participation(
    uid: str = Depends(get_current_user_flexible),
    eid: int = 0,
    db: Session = Depends(get_db),
):
    participation = db.query(Participation).filter_by(uid=uid, eid=eid).first()

    if not participation:
        return {"msg": False}

    return {"msg": True}


class UserProfile(BaseModel):
    # === 基础信息（所有用户） ===
    nick: str                         # 昵称
    uid: str                          # 学号
    email: Optional[str] = None       # 邮箱
    role_name: str = "会员"           # 角色名称，通过 rid 映射
    
    # === 详细信息（仅Member） ===
    name: Optional[str] = None        # 姓名
    gender: Optional[str] = None      # 性别（男/女）
    major_name: Optional[str] = None  # 专业
    college_name: Optional[str] = None # 学院
    grade: Optional[int] = None       # 年级
    # 工作信息
    department: Optional[str] = None  # 部门
    position: Optional[str] = None    # 职位
    is_active: Optional[bool] = None  # 在职状态
    # 联系方式
    phone: Optional[str] = None       # 电话
    wechat: Optional[str] = None      # 微信
    qq: Optional[str] = None          # QQ

    skills: Optional[str] = None      # 技能特长


class UpdateUserProfile(BaseModel):
    # User表字段（所有用户可编辑）
    email: Optional[str] = None
    # Member表字段（仅干事可编辑）
    phone: Optional[str] = None
    wechat: Optional[str] = None
    qq: Optional[str] = None
    skills: Optional[str] = None
    # 注意：姓名、学号、性别、专业不可编辑


@router.get("/profile", response_model=UserProfile, tags=["user"])
def get_user_profile(
    uid: str = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """获取用户个人资料"""
    user = db.query(User).filter_by(uid=uid).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 通过 role_id 映射角色名称
    admin = db.query(Admin).filter_by(uid=uid).first()
    if admin and admin.is_active:
        admin_roles = {
            7: Admin_Role.ADMIN["role_name"],
            8: Admin_Role.PUBLISHER["role_name"],
            9: Admin_Role.OPERATOR["role_name"]
        }
        role_name = admin_roles.get(admin.role_id, "管理员")
    else:
        user_roles = {
            1: User_Role.MEMBER["role_name"],
            2: User_Role.OFFICER["role_name"],
            3: User_Role.VICE_MINISTER["role_name"],
            4: User_Role.MINISTER["role_name"],
            5: User_Role.FINANCIAL_RESPONSIBLE["role_name"],
            6: User_Role.PRESIDENT["role_name"]
        }
        role_name = user_roles.get(user.role_id, "会员")
    
    # 基础信息
    profile_data = {
        "uid": user.uid,
        "nick": user.nick,
        "email": user.email,
        "role_name": role_name,
    }
    
    # 获取Member信息
    member = db.query(Member).filter_by(uid=uid).first()
    if member:
        profile_data.update({
            "name": member.name,
            "gender": "女" if member.render else "男",
            "phone": member.phone,
            "wechat": member.wechat,
            "qq": member.qq,
            "major_name": member.major_name,
            "college_name": member.college_name,
            "grade": member.grade,
            "department": member.department,
            "position": member.position,
            "is_active": member.is_active,
            "skills": member.skills,
        })
    
    return UserProfile(**profile_data)


@router.put("/profile", tags=["user"])
def update_user_profile(
    data: UpdateUserProfile,
    uid: str = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """
    更新用户个人资料
    - 姓名、学号、性别、专业不可编辑
    - 所有用户可编辑 User 表字段（email）
    - 干事可额外编辑 Member 表字段（phone, wechat, qq, skills）
    """
    user = db.query(User).filter_by(uid=uid).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 更新邮箱
    if data.email is not None and data.email != "":
        # 检查邮箱是否被占用
        existing = db.query(User).filter(User.email == data.email, User.uid != uid).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="邮箱已被使用"
            )
        user.email = data.email

    # 更新 Member 表字段
    has_member_fields = any([
        data.phone is not None and data.phone != "",
        data.wechat is not None and data.wechat != "",
        data.qq is not None and data.qq != "",
        data.skills is not None and data.skills != ""
    ])
    
    if has_member_fields:
        member = db.query(Member).filter_by(uid=uid).first()
        
        if not member:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="部分字段没能在对应数据库表中找到，请联系管理员"
            )

        if data.phone is not None and data.phone != "":
            member.phone = data.phone
        if data.wechat is not None and data.wechat != "":
            member.wechat = data.wechat
        if data.qq is not None and data.qq != "":
            member.qq = data.qq
        if data.skills is not None and data.skills != "":
            member.skills = data.skills
        member.updated_at = datetime.utcnow()
    
    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"更新失败：{e}"
        )
    
    return {"msg": "个人资料更新成功"}


class AdminStatusResponse(BaseModel):
    is_admin: bool
    admin_role_id: Optional[int] = None
    admin_role_name: Optional[str] = None
    admin_token: Optional[str] = None


@router.get("/admin_status", response_model=AdminStatusResponse, tags=["user"])
def check_admin_status(
    uid: str = Depends(get_current_user_flexible),
    db: Session = Depends(get_db),
):
    """检查当前用户是否是管理员，如果是则返回管理员token"""
    user = db.query(User).filter_by(uid=uid).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 查询是否是管理员
    admin = db.query(Admin).filter_by(uid=uid).first()
    
    if admin and admin.is_active:
        # 角色名称映射
        role_names = {
            7: "管理员",
            8: "发布者",
            9: "运维"
        }
        
        # 生成管理员token
        admin_token = create_access_token_admin(
            aid=admin.aid, uid=user.uid, expires_delta=timedelta(hours=2), nick=user.nick
        )
        
        return AdminStatusResponse(
            is_admin=True,
            admin_role_id=admin.role_id,
            admin_role_name=role_names.get(admin.role_id, "未知角色"),
            admin_token=admin_token
        )
    else:
        return AdminStatusResponse(is_admin=False)
