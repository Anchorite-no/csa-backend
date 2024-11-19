import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from misc.auth import get_current_admin, get_current_user
from models import get_db
from models.event import Event
from models.event_category import EventCategory
from models.news import News
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
    data: EditNews, db: Session = Depends(get_db), user: str = Depends(get_current_user)
):
    if data.nid:
        news = db.query(News).filter_by(nid=data.nid).first()
        if not news:
            raise HTTPException(status_code=404, detail="新闻未找到")
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
            news.publisher = user
            db.add(news)

        db.commit()
        return news.nid
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=400, detail=f"An error occurred when editing news: {e}")

    return None


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
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户没有权限进行此操作"
        )

    if data.ecid:
        event_category = db.query(EventCategory).filter_by(
            ecid=data.ecid).first()
        if not event_category:
            raise HTTPException(status_code=404, detail="活动类型未找到")

        event_category.description = data.description

        try:
            db.commit()
            db.refresh(event_category)
            return data.eid
        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred when editing event: {e}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="您的输入不合法！"
        )


class EditEvent(BaseModel):
    eid: Optional[int] = None
    title: str
    tag: str
    image: str
    description: str
    ecid: int
    start_time: int
    end_time: int
    start_signup_time: int
    end_signup_time: int
    start_signin_time: int
    end_signin_time: int
    signin_location: str
    place: str
    publisher: str


@router.post("/event")
def edit_event(
    data: EditEvent,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
    aid: str = Depends(get_current_admin),
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户没有权限进行此操作"
        )

    if data.eid:
        event = db.query(Event).filter_by(eid=data.eid).first()
        if not event:
            raise HTTPException(
                status_code=404,
                detail="活动未找到"
            )

        event.title = data.title
        event.tag = data.tag
        event.image = data.image
        event.description = data.description
        event.ecid = data.ecid
        event.start_time = data.start_time - data.start_time % 60
        event.end_time = data.end_time - data.end_time % 60
        event.start_signup_time = data.start_signup_time
        event.end_signup_time = data.end_signup_time
        event.start_signin_time = data.start_signin_time
        event.end_signin_time = data.end_signin_time
        event.place = data.place
        event.publisher = data.publisher  # 这个需要修改吗？
        event.last_update = int(time.time())

        try:
            # if not data.eid:
            #     event.first_publish = int(time.time())
            #     event.publisher = user
            #     db.add(event)

            db.commit()
            db.refresh(event)
            return data.eid

        except Exception as e:
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred when editing event: {e}"
            )
    else:
        raise HTTPException(
            status_code=400,
            detail="您的输入不合法！"
        )
