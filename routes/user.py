import time
from datetime import timedelta
from hashlib import sha256
from typing import Annotated

import requests
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

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
    old: Annotated[str, Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_-]+$")]
    new: Annotated[str, Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_-]+$")]


class UserRegister(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    nick: Annotated[
        str, Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_-]+$")
    ]
    code: str
    email: EmailStr


class ParticipationItem(BaseModel):
    uid: str
    username: str
    eid: int
    event_title: str
    place: str


class WxUserLogin(BaseModel):
    code: str


class AdminLogin(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    # aid: Annotated[str, Field(pattern=r'^\d+$')]
    passwd: Annotated[
        str, Field(min_length=64, max_length=64, pattern=r"^[a-zA-Z0-9_-]+$")
    ]


class AdminToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


@router.post("/login/admin", response_model=AdminToken, tags=["admin"])
def login(
    data: AdminLogin,
    db: Session = Depends(get_db),
):
    user = db.query(User).filter_by(uid=data.uid).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户未找到")

    if not verify_passwd(data.passwd, user.passwd.encode("utf-8")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")

    admin = db.query(Admin).filter_by(aid=data.uid).first()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="管理员未找到",
        )

    if not admin.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="该管理员账号未激活",
        )

    admin_token = create_access_token_admin(
        aid=admin.aid, uid=user.uid, expires_delta=timedelta(hours=2), nick=user.nick
    )

    return AdminToken(access_token=admin_token)


@router.post("/wxlogin", response_model=UserToken, tags=["user"])
def wxlogin(data: WxUserLogin, db: Session = Depends(get_db)):
    # submit code to miniapp
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
        raise HTTPException(status_code=400, detail="Invalid code")

    user = db.query(User).filter_by(openid=openid).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)

    user.last_login = int(time.time())

    return UserToken(access_token=token)


@router.post("/login", response_model=UserToken, tags=["user"])
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(uid=data.uid).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户未找到"
        )

    if not verify_passwd(data.passwd, user.passwd):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")

    token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)

    user.last_login = int(time.time())

    return UserToken(access_token=token)


@router.post("/token", response_model=UserToken, tags=["user"])
def token(data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(uid=data.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户未找到"
        )

    if not verify_passwd(sha256(data.password.encode()).hexdigest(), user.passwd):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")

    token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)

    user.last_login = int(time.time())

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
            status_code=status.HTTP_401_UNAUTHORIZED, detail="原密码错误"
        )

    if data.old == data.new:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="新密码不能与旧密码相同"
        )

    user.passwd = hash_passwd(data.new)

    db.commit()

    return {"result": "PasswdReset Successfully"}


@router.post("/register", response_model=UserToken, tags=["user"])
def register(data: UserRegister, db: Session = Depends(get_db)):

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
        raise HTTPException(status_code=400, detail="Invalid code")

    user = db.query(User).filter_by(uid=data.uid).first()
    if user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="用户已存在"
        )

    email = db.query(User).filter_by(email=data.email).first()
    if email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册"
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
        .filter_by(uid=uid)
        .order_by(Participation.signup_time.desc())
    )

    count = participations.count()

    participations = participations.offset((page - 1) * size)
    participations = participations.limit(size)
    participations = participations.all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            username=user.nick,
            eid=participation.eid,
            event_title=event.title,
            participation_time=participation.signin_time,  # 签到时间
            place=participation.signin_location,  # 签到地点
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
