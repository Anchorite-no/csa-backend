import time
from datetime import timedelta
from hashlib import sha256

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, constr, EmailStr, Field
from typing import Annotated
from sqlalchemy.orm import Session

from misc.auth import create_access_token, get_current_user, hash_passwd, verify_passwd
from models import get_db
from models.user import User
from models.event import Event
from models.relation.user_event import user_event

router = APIRouter()


class UserLogin(BaseModel):
    uid: Annotated[str, Field(pattern=r'^\d+$')]
    passwd: Annotated[str, Field(min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')]


class UserToken(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserPasswd(BaseModel):
    old: Annotated[str, Field(min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')]
    new: Annotated[str, Field(min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')]

class UserRegister(BaseModel):
    uid: Annotated[str, Field(pattern=r'^\d+$')]
    nick: Annotated[str, Field(min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')]
    passwd: Annotated[str, Field(min_length=3, max_length=30, pattern=r'^[a-zA-Z0-9_-]+$')]
    email: EmailStr

class ParticipationItem(BaseModel):
    uid: int
    username: str
    eid: int
    event_title: str
    place: str

@router.post("/login", response_model=UserToken, tags=["user"])
def login(data: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(uid=data.uid).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户未找到")

    if not verify_passwd(data.passwd, user.passwd):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码错误")

    token = create_access_token(user.uid, timedelta(hours=2), nick=user.nick)

    user.last_login = int(time.time())

    return UserToken(access_token=token)


@router.post("/token", response_model=UserToken, tags=["user"])
def token(data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter_by(uid=data.username).first()

    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户未找到")

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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="原密码错误")

    if data.old == data.new:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="新密码不能与旧密码相同")

    user.passwd = hash_passwd(data.new)

    db.commit()

    return {"result": "PasswdReset Successfully"}


@router.post("/register", response_model=UserToken, tags=["user"])
def register(data: UserRegister, db: Session = Depends(get_db)):
    user = db.query(User).filter_by(uid=data.uid).first()
    if user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="用户已存在")

    email = db.query(User).filter_by(email=data.email).first()
    if email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="邮箱已被注册")

    try:
        new_user = User(uid=data.uid, nick=data.nick, passwd=hash_passwd(data.passwd), email=data.email, last_login=0)
        db.add(new_user)
        db.commit()
        generated_token = create_access_token(new_user.uid, timedelta(hours=2), nick=new_user.nick)

        return UserToken(access_token=generated_token)
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"An error occurred when registering: {e}")

    return None

@router.get("/participation", response_model=list[ParticipationItem])
def get_participations(
    uid: int, page: int = 1, size: int = 8, db: Session = Depends(get_db)
):
    participations = db.query(user_event).join(User).join(Event).filter_by(uid=uid).order_by(user_event.participation_time.desc())

    participations = participations.offset((page - 1) * size)
    participations = participations.limit(size)
    participations = participations.all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            username=participation.user.nick,
            eid=participation.eid,
            event_title=participation.event.title,
            participation_time=participation.event.start_time,
            place=participation.place
        )
        for participation in participations
    ]

    return participation_items