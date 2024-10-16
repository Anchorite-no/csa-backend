import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from misc.auth import get_current_user
from models import get_db
from models.event import Event
from models.news import News

router = APIRouter()


class EditNews(BaseModel):
    nid: Optional[int] = None
    title: str
    tag: str
    content: str


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
    news.last_update = int(time.time())

    if not data.nid:
        news.first_publish = int(time.time())
        news.publisher = user
        db.add(news)

    db.commit()

    return news.nid


class EditEvent(BaseModel):
    eid: Optional[int] = None
    title: str
    tag: str
    description: str
    start_time: int
    end_time: int
    place: str


@router.post("/event")
def edit_event(
    data: EditEvent,
    db: Session = Depends(get_db),
    user: str = Depends(get_current_user),
):
    if data.eid:
        event = db.query(Event).filter_by(eid=data.eid).first()
        if not event:
            raise HTTPException(status_code=404, detail="活动未找到")
    else:
        event = Event()

    event.title = data.title
    event.tag = data.tag
    event.description = data.description
    event.start_time = data.start_time - data.start_time % 60
    event.end_time = data.end_time - data.end_time % 60
    event.place = data.place
    event.last_update = int(time.time())

    if not data.eid:
        event.first_publish = int(time.time())
        event.publisher = user
        db.add(event)

    db.commit()

    return event.eid
