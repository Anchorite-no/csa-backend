from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from misc.auth import get_current_admin, get_current_user
from models import get_db
from models.event import Event
from models.event_category import EventCategory
from models.news import News
import time

from routes.admin import is_manager

router = APIRouter()


class CreateNews(BaseModel):
    title: str
    tag: str
    content: str


class CreateEventCategory(BaseModel):
    description: str


class CreateEvent(BaseModel):
    title: str
    tag: str
    image: str
    description: str
    ecid: int
    start_time: int
    end_time: int
    # start_signup_time: int
    # end_signup_time: int
    # start_signin_time: int
    # end_signin_time: int
    # signin_location: str
    place: str


@router.post("/news")
def create_news(
    data: CreateNews,
    db: Session = Depends(get_db),
    publisher: str = Depends(get_current_user)
):
    try:
        new_news = News(
            title=data.title,
            tag=data.tag,
            content=data.content,
            first_publish=int(time.time()),
            last_update=int(time.time()),
            publisher=publisher
        )

        db.add(new_news)
        db.commit()
        db.refresh(new_news)
        return {"result": "Create News Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"An error occurred when creating news: {e}")


@router.post("/event_category", tags=["admin"])
def create_event_category(
        data: CreateEventCategory,
        db: Session = Depends(get_db),
        aid: str = Depends(get_current_admin)
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户没有权限进行此操作"
        )

    try:
        existing_event_category = db.query(EventCategory).filter(
            description=data.description).first()
        if existing_event_category is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="该活动类型已经存在"
            )
        else:
            new_event_category = EventCategory(description=data.description)
            db.add(new_event_category)
            db.commit()
            return {"result": "Create EventCategory Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"创建活动类型时发生错误: {e}")


@router.post("/event")
def create_event(
    data: CreateEvent,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin),
    publisher: str = Depends(get_current_user)
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前用户没有权限进行此操作"
        )
    
    try:
        new_event = Event(
            title=data.title,
            tag=data.tag,
            image=data.image,
            description=data.dscription,
            ecid=data.ecid,
            start_time=data.start_time,
            end_time=data.end_time,
            # start_signup_time=data.start_signup_time,
            # end_signup_time=data.end_signup_time,
            # start_signin_time=data.start_signin_time,
            # end_signin_time=data.end_signin_time,
            # sign_in_location=data.signin_location,
            place=data.place,
            publisher=publisher,
            first_publish=int(time.time()),
            last_update=int(time.time())
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {"result": "Create Event Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"An error occurred when creating event: {e}")
