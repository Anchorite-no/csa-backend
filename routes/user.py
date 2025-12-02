import time
from datetime import timedelta
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
    """
    统一登录接口，自动判断用户身份
    - 如果是管理员，返回 AdminToken
    - 如果是普通用户，返回 UserToken
    """
    user = db.query(User).filter_by(uid=data.uid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if not verify_passwd(data.passwd, user.passwd.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

    admin = db.query(Admin).filter_by(aid=data.uid).first()
    
    if admin and admin.is_active:
        # 管理员登录，返回 AdminToken
        admin_token = create_access_token_admin(
            aid=admin.aid, uid=user.uid, expires_delta=timedelta(hours=2), nick=user.nick
        )
        user.last_login = int(time.time())
        db.commit()
        return AdminToken(access_token=admin_token)
    else:
        # 普通用户登录，返回 UserToken
        user_token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)
        user.last_login = int(time.time())
        db.commit()
        return UserToken(access_token=user_token)
# 使用 /login 统一登录接口
# @router.post("/login/admin", response_model=AdminToken, tags=["admin"])
# def login(
#     data: AdminLogin,
#     db: Session = Depends(get_db),
# ):
#     user = db.query(User).filter_by(uid=data.uid).first()

#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

#     if not verify_passwd(data.passwd, user.passwd.encode("utf-8")):
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

#     admin = db.query(Admin).filter_by(aid=data.uid).first()

#     if not admin:
#         raise HTTPException(
#             status_code=status.HTTP_404_NOT_FOUND,
#             detail="Administrator not found",
#         )

#     if not admin.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="This administrator account is not activated",
#         )

#     admin_token = create_access_token_admin(
#         aid=admin.aid, uid=user.uid, expires_delta=timedelta(hours=2), nick=user.nick
#     )

#     user.last_login = int(time.time())
#     db.commit()

#     return AdminToken(access_token=admin_token)


# @router.post("/login/user", response_model=UserToken, tags=["user"])
# def login_user(
#     data: AdminLogin,  # 使用同样的验证模型
#     db: Session = Depends(get_db),
# ):
#     """普通用户登录接口"""
#     user = db.query(User).filter_by(uid=data.uid).first()

#     if not user:
#         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

#     if not verify_passwd(data.passwd, user.passwd.encode("utf-8")):
#         raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect password")

#     # 检查是否为管理员
#     admin = db.query(Admin).filter_by(aid=data.uid).first()
#     if admin and admin.is_active:
#         raise HTTPException(
#             status_code=status.HTTP_403_FORBIDDEN,
#             detail="You are an administrator, right? Please use the admin login endpoint",
#         )

#     # 生成普通用户 Token
#     user_token = create_access_token(
#         uid=user.uid, expires_delta=timedelta(hours=2), nick=user.nick
#     )

#     user.last_login = int(time.time())
#     db.commit()

#     return UserToken(access_token=user_token)


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
    uid: str = Depends(get_current_user),
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
    uid: str = Depends(get_current_user),
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
    uid: str = Depends(get_current_user),
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
    uid: str = Depends(get_current_user),
    eid: int = 0,
    db: Session = Depends(get_db),
):
    participation = db.query(Participation).filter_by(uid=uid, eid=eid).first()

    if not participation:
        return {"msg": False}

    return {"msg": True}


class UserProfile(BaseModel):
    uid: str
    nick: str
    email: Optional[str] = None
    name: Optional[str] = None
    gender: Optional[str] = None  # '男' or '女'
    phone: Optional[str] = None
    wechat: Optional[str] = None
    qq: Optional[str] = None
    major_name: Optional[str] = None
    college_name: Optional[str] = None
    grade: Optional[int] = None
    department: Optional[str] = None
    position: Optional[str] = None
    is_active: Optional[bool] = None
    skills: Optional[str] = None
    user_type: str = "会员"  # 用户类型：会员、干事


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
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """获取用户个人资料"""
    user = db.query(User).filter_by(uid=uid).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 根据 role_id 判断用户类型；下面只是我假定的，具体后续添加权限表后按实际修改，暂时只考虑会员和干事的展示逻辑
    # 1=会员, 2=干事, 7=管理员
    role_names = {1: "会员", 2: "干事"}
    user_type = role_names.get(user.role_id, "会员")
    
    # 基础资料来自User表（所有用户都有）
    profile_data = {
        "uid": user.uid,
        "nick": user.nick,
        "email": user.email,
        "user_type": user_type,
    }
    # 如果是干事，尝试从Member表获取信息
    if user.role_id == 2:
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
        else:
            # TODO: 在 member 表中添加一条新记录？待确认
            pass
    # 如果member不存在，这些字段为None，前端会显示为"-"
    return UserProfile(**profile_data)


@router.put("/profile", tags=["user"])
def update_user_profile(
    data: UpdateUserProfile,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    更新用户个人资料
    - 所有用户可编辑 User 表字段（email）
    - 干事可额外编辑 Member 表字段（phone, wechat, qq, skills）
    - 姓名、学号、性别、专业不可编辑
    """
    user = db.query(User).filter_by(uid=uid).first()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    # 更新 User 表字段（目前只有在对应表中确实存在的字段编辑后才可真正成功）
    if data.email is not None:
        # 检查邮箱是否被占用
        existing = db.query(User).filter(User.email == data.email, User.uid != uid).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use"
            )
        user.email = data.email
    
    # 检查是否为干事，如果是则可以更新 Member 表字段
    if user.role_id == 2:
        member = db.query(Member).filter_by(uid=uid).first()
        if member:
            if data.phone is not None:
                member.phone = data.phone
            if data.wechat is not None:
                member.wechat = data.wechat
            if data.qq is not None:
                member.qq = data.qq
            if data.skills is not None:
                member.skills = data.skills
        else:
            # 在 member 表中添加一条新记录？待确认
            pass
    
    db.commit()
    return {"msg": "Profile updated successfully"}
