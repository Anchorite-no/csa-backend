import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from misc.auth import get_current_admin, get_current_user
from misc.image_manager import cleanup_unused_images
from models import get_db
from models.event import Event
from models.event_category import EventCategory
from models.news import News
from models.participation import Participation
from routes.admin import is_manager

router = APIRouter()


class EditNews(BaseModel):
    nid: Optional[int] = None
    title: str
    tag: str
    content: str
    category: int
    image: str


@router.post("/news")
def edit_news(
    data: EditNews, db: Session = Depends(get_db), aid: str = Depends(get_current_admin)
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="当前用户没有权限进行此操作"
        )

    old_content = ""
    old_image = ""
    
    if data.nid:
        news = db.query(News).filter_by(nid=data.nid).first()
        if not news:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="新闻未找到"
            )
        # 保存旧内容用于图片清理
        old_content = news.content or ""
        old_image = news.image or ""
    else:
        news = News()

    news.title = data.title
    news.tag = data.tag
    news.content = data.content
    news.category = data.category
    news.image = data.image
    news.last_update = int(time.time())

    try:
        if not data.nid:
            news.first_publish = int(time.time())
            news.publisher = aid
            db.add(news)

        db.commit()
        
        # 如果是编辑操作，清理不再使用的图片
        if data.nid:
            deleted_count = cleanup_unused_images(
                old_content=old_content,
                new_content=data.content,
                old_image=old_image,
                new_image=data.image
            )
            if deleted_count > 0:
                print(f"清理了 {deleted_count} 个不再使用的图片文件")

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when editing news: {e}",
        )

    return news.nid


class EditEventCategory(BaseModel):
    ecid: int
    description: str


@router.post("/event_category")
def edit_event_category(
    data: EditEventCategory,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="当前用户没有权限进行此操作"
        )

    if data.ecid:
        event_category = db.query(EventCategory).filter_by(ecid=data.ecid).first()
        if not event_category:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="活动类型未找到"
            )
    else:
        event_category = EventCategory()

    event_category.description = data.description

    try:
        if not data.ecid:
            db.add(event_category)

        db.commit()

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when editing event: {e}",
        )

    return data.eid


class EditEvent(BaseModel):
    eid: Optional[int] = None
    title: str
    tag: str
    image: str
    description: str
    category: int
    start_time: int
    end_time: int
    place: str
    start_signup_time: Optional[int] = None
    end_signup_time: Optional[int] = None


@router.post("/event")
def edit_event(
    data: EditEvent,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
):
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="当前用户没有权限进行此操作"
    #     )
    first_publish = 0

    old_content = ""
    old_image = ""
    
    if data.eid:
        event = db.query(Event).filter_by(eid=data.eid).first()
        if not event:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="活动未找到"
            )
        # 保存旧内容用于图片清理
        old_content = event.description or ""
        old_image = event.image or ""
    else:
        event = Event()

    event.title = data.title
    event.tag = data.tag
    event.image = data.image
    event.description = data.description
    event.ecid = data.category
    event.start_time = data.start_time - data.start_time % 60
    event.end_time = data.end_time - data.end_time % 60
    event.start_signup_time = data.start_signup_time
    event.end_signup_time = data.end_signup_time
    event.place = data.place
    event.last_update = int(time.time())

    try:
        if not data.eid:
            event.first_publish = int(time.time())
            event.publisher = aid
            db.add(event)

        db.commit()
        
        # 如果是编辑操作，清理不再使用的图片
        if data.eid:
            deleted_count = cleanup_unused_images(
                old_content=old_content,
                new_content=data.description,
                old_image=old_image,
                new_image=data.image
            )
            if deleted_count > 0:
                print(f"清理了 {deleted_count} 个不再使用的图片文件")

    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when editing event: {e}",
        )

    return data.eid


class EditSignin(BaseModel):
    eid: int
    start_signin_time: int
    end_signin_time: int
    signin_code: str


@router.post("/signin")
def edit_signin(
    data: EditSignin,
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter_by(eid=data.eid).first()
    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="活动未找到")

    event.start_signin_time = data.start_signin_time
    event.end_signin_time = data.end_signin_time
    event.signin_code = data.signin_code

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when editing event: {e}",
        )

    return {"msg": "success"}
