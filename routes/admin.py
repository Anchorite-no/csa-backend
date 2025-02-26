from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, constr, EmailStr, Field
from typing import Annotated
from sqlalchemy.orm import Session

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


router = APIRouter()


class AdminAuthorization(BaseModel):
    # aid_author: Annotated[str, Field(pattern=r'^\d+$')]
    uid_authored: Annotated[str, Field(pattern=r"^\d+$")]
    rid_authored: Annotated[str, Field(pattern=r"^\d+$")]


class AdminDeauthorization(BaseModel):
    uid_deauthored: Annotated[str, Field(pattern=r"^\d+$")]
    rid_deauthored: Annotated[str, Field(pattern=r"^\d+$")]


class UserItem(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    nick: Annotated[
        str, Field(min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_-]+$")
    ]
    email: EmailStr
    last_login: int


class UserRoleUpdate(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]
    rid: Annotated[int, Field(gt=0)]  #


class UserDelete(BaseModel):
    uid: Annotated[str, Field(pattern=r"^\d+$")]  # 用户 ID


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
            status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
        )
    try:
        user = db.query(User).filter(uid=data.uid_authored).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="目标用户未找到"
            )

        admin_role = db.query(Admin_Role).filter(rid=data.rid_authored).first()
        if not admin_role:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="管理员角色未找到"
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

    return {"msg": "用户已成功授权为管理员"}


@router.post("/deauthor", tags=["admin"])
def admin_deauthorization(
    data: AdminDeauthorization,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
        )

    user = db.query(User).filter(uid=data.uid_deauthored).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="目标用户未找到"
        )
    try:
        if data.rid_deauthored:
            admin_role = db.query(Admin_Role).filter(rid=data.rid_deauthored).first()
            if not admin_role:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="管理员角色未找到"
                )

            existing_admin = db.query(Admin).filter(uid=data.uid_deauthored).first()
            if not existing_admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="该用户不是管理员"
                )

            existing_admin.role = admin_role
            db.commit()

        else:
            existing_admin = db.query(Admin).filter(uid=data.uid_deauthored).first()
            if not existing_admin:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="该用户不是管理员"
                )

            db.delete(existing_admin)
            db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"An error occurred when deauthorizing user: {e}"
        )

    return {"msg": "用户管理员权限已成功撤销或修改"}


@router.post("/user_list", response_model=list[UserItem], tags=["admin"])
def show_user_list(db: Session = Depends(get_db)):
    users = db.query(User).all()

    user_list = [
        {
            "uid": user.uid,
            "nick": user.nick,
            "email": user.email,
            "last_login": user.last_login,
        }
        for user in users
    ]

    return {"user_list": user_list}


@router.post("/delete_user", tags=["admin"])
def delete_user(
    data: UserDelete,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
        )

    user = db.query(User).filter(uid=data.uid).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户未找到")

    try:
        admin = db.query(Admin).filter(uid=data.uid).first()
        if admin:
            db.delete(admin)
            db.commit()

        db.query(user_role_association).filter(uid=data.uid).delete()
        db.commit()

        db.query(admin_role_association).filter(uid=data.uid).delete()
        db.commit()

        db.query(user_event).filter(uid=data.uid).delete()
        db.commit()

        db.delete(user)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"删除用户时发生错误: {e}")

    return {"msg": "用户已成功删除"}


@router.post("/update_user_role", tags=["admin"])
def update_user_role(
    data: UserRoleUpdate,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="当前管理员没有权限进行此操作"
        )

    user = db.query(User).filter(uid=data.uid).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="目标用户未找到"
        )

    role = db.query(User_Role).filter(rid=data.rid).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="目标角色未找到"
        )
    try:
        db.query(user_role_association).filter(
            user_role_association.c.uid == data.uid
        ).delete()

        new_role_association = user_role_association.insert().values(
            uid=data.uid, rid=data.rid
        )
        db.execute(new_role_association)
        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"更改用户角色时发生错误: {e}")

    return {"msg": "用户角色已成功更改"}
