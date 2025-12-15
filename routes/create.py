from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from misc.auth import get_current_admin, get_current_user_flexible
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
    place: str


@router.post("/news/draft")
def create_news_draft(
    db: Session = Depends(get_db),
    publisher: str = Depends(get_current_user_flexible)
):
    try:
        # Create a draft news with first_publish=0
        new_news = News(
            title="Draft",
            tag="",
            content="",
            first_publish=0,  # 0 indicates draft status
            last_update=int(time.time()),
            publisher=publisher
        )
        db.add(new_news)
        db.commit()
        db.refresh(new_news)
        return {"nid": new_news.nid}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"An error occurred when creating draft: {e}")


@router.post("/news")
def create_news(
    data: CreateNews,
    db: Session = Depends(get_db),
    publisher: str = Depends(get_current_user_flexible)
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


@router.post("/event/draft")
def create_event_draft(
    db: Session = Depends(get_db),
    publisher: str = Depends(get_current_user_flexible)
):
    try:
        # Create a draft event with first_publish=0
        new_event = Event(
            title="Draft",
            tag="",
            image="",
            description="",
            ecid=1,  # Default category
            start_time=0,
            end_time=0,
            place="",
            publisher=publisher,
            first_publish=0,
            last_update=int(time.time())
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {"eid": new_event.eid}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500, detail=f"An error occurred when creating draft event: {e}")


@router.post("/event_category", tags=["admin"])
def create_event_category(
        data: CreateEventCategory,
        db: Session = Depends(get_db),
        aid: str = Depends(get_current_user_flexible)
):
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Current user does not have permission to perform this operation"
    #     )

    try:
        existing_event_category = db.query(EventCategory).filter(
            description=data.description).first()
        if existing_event_category is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This event category already exists"
            )
        else:
            new_event_category = EventCategory(description=data.description)
            db.add(new_event_category)
            db.commit()
            return {"result": "Create EventCategory Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Error occurred when creating event category: {e}")


@router.post("/event")
def create_event(
    data: CreateEvent,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_user_flexible),
    publisher: str = Depends(get_current_user_flexible)
):
    # if not is_manager(db, aid):
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Current user does not have permission to perform this operation"
    #     )
    
    try:
        new_event = Event(
            title=data.title,
            tag=data.tag,
            image=data.image,
            description=data.dscription,
            ecid=data.ecid,
            start_time=data.start_time,
            end_time=data.end_time,
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
