from fastapi import APIRouter, Depends, Body, HTTPException, status
from pydantic import BaseModel, constr, EmailStr, Field
from typing import Annotated, Optional
from sqlalchemy.orm import Session
from datetime import datetime
import pandas as pd
from io import BytesIO
from fastapi.responses import StreamingResponse

from misc.auth import (
    get_current_admin,
    login_required_admin,
)
from models import get_db
from models.user import User
from models.event import Event
from models.admin import Admin
from models.role import Admin_Role, User_Role
from models.relation.user_event import user_event
from models.relation.user_roles import user_role_association
from models.relation.admin_roles import admin_role_association
from models.recruit import Recruitment, Evaluation
from config import update_recruit_deadline
router = APIRouter()


class AdminAuthorization(BaseModel):
    
    uid_authored: Annotated[str, Field(pattern=r"^\d+$")]
    rid_authored: int


class AdminDeauthorization(BaseModel):
    uid_deauthored: Annotated[str, Field(pattern=r"^\d+$")]
    rid_deauthored: Optional[int] = None


class UserItem(BaseModel):
    uid: str
    nick: str
    email: str
    rid: Optional[int]
    is_admin: bool
    admin_rid: Optional[int]
    last_login: Optional[int]


class UserRoleUpdate(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    rid: Annotated[int, Field(gt=0)]  #


class UserDelete(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]  

class SetRecruitDeadline(BaseModel):
    deadline: Annotated[str, Field(pattern=r"\d{4}-\d{2}-\d{2}")]


def is_manager(db: Session, aid: str) -> bool:
    admin = db.query(Admin).filter_by(aid=aid).first()
    if admin and admin.role_id and admin.role_id == 7:
        return True
    return False


@router.post("/author", tags=["admin"])
def admin_authorization(
    data: AdminAuthorization,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Current administrator does not have permission to perform this operation"
        )
    try:
        user = db.query(User).filter_by(uid=data.uid_authored).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
            )

        new_admin = Admin(
            uid=data.uid_authored,
            role_id=data.rid_authored,
            is_active=True,
        )
        db.add(new_admin)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"An error occurred when authorizing user: {e}"
        )

    return {"msg": "User has been successfully authorized as an admin"}


@router.post("/deauthor", tags=["admin"])
def admin_deauthorization(
    data: AdminDeauthorization,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Current administrator does not have permission to perform this operation"
        )

    user = db.query(User).filter_by(uid=data.uid_deauthored).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
        )
    try:
        existing_admin = db.query(Admin).filter_by(uid=data.uid_deauthored).first()
        if not existing_admin:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="This user is not an administrator"
            )

        if data.rid_deauthored:
            existing_admin.role_id = data.rid_deauthored
        else:
            db.delete(existing_admin)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"An error occurred when deauthorizing user: {e}"
        )

    return {"msg": "用户管理员权限已成功撤销或修改"}


@router.get("/user_count", tags=["admin"])
def show_user_count(
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Current administrator does not have permission to perform this operation"
        )

    user_count = db.query(User).count()
    return {"user_count": user_count}


@router.get("/user_list", response_model=list[UserItem], tags=["admin"])
def show_user_list(
    page: int = 1, size: int = 8, s: str = None, db: Session = Depends(get_db)
):
    users = db.query(User, Admin)
    users = users.outerjoin(Admin, User.uid == Admin.uid)
    if s:
        users = users.filter((User.uid.like(f"%{s}%")) | (User.nick.like(f"%{s}%")))
    
    users = users.limit(size).offset((page - 1) * size)
    users = users.all()

    user_list = [
        UserItem(
            uid=user[0].uid,
            nick=user[0].nick,
            email=user[0].email,
            rid=user[0].role_id,
            is_admin=user[1] is not None,
            admin_rid=user[1].role_id if user[1] else None,
            last_login=user[0].last_login,
        )
        for user in users
    ]

    return user_list


@router.post("/delete_user", tags=["admin"])
def delete_user(
    data: UserDelete,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Current administrator does not have permission to perform this operation"
        )

    user = db.query(User).filter_by(uid=data.uid).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        admin = db.query(Admin).filter_by(uid=data.uid).first()
        if admin:
            db.delete(admin)
            db.commit()

        db.delete(user)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error occurred when deleting user: {e}")

    return {"msg": "用户已成功删除"}


@router.post("/update_user_role", tags=["admin"])
def update_user_role(
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Current administrator does not have permission to perform this operation"
        )

    user = db.query(User).filter_by(uid=data.uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found"
        )

    try:
        user.role_id = data.rid
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Error occurred when changing user role: {e}")

    return {"msg": "用户角色已成功更改"}

@router.post("/setRecruitDeadline", tags=["admin"])
def set_recruit_deadline(
    data: SetRecruitDeadline
):
    deadline_str = data.deadline  
    
    try:
        datetime.strptime(deadline_str, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="日期格式错误，请使用 YYYY-MM-DD 格式")
    
    update_recruit_deadline(deadline_str)
    
    return {
        "code": 200,
        "message": "招新截止日期设置成功",
        "data": {"deadline": deadline_str}
    }