from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db
from models.event import Event
from models.news import News
import time

router = APIRouter()

class CreateNews(BaseModel):
    title: str
    tag: str
    content: str
    publisher: str

class CreateEvent(BaseModel):
    title: str
    tag: str
    description: str
    start_time: str
    end_time: str
    place: str
    publisher: str


@router.post("/news")
def create_news(
    data: CreateNews,
    db: Session = Depends(get_db),
):
    try:
        new_news = News(
            title=data.title,
            tag=data.tag,
            content=data.content,
            first_publish=int(time.time()),
            last_update=int(time.time()),
            publisher=data.publisher
        )

        db.add(new_news)
        db.commit()
        db.refresh(new_news)
        return {"result" : "Create News Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"An error occurred when creating news: {e}")


@router.post("/event")
def create_event(data: CreateEvent, db: Session = Depends(get_db)):
    try:
        new_event = Event(
            title=data.title,
            tag=data.tag,
            description=data.description,
            start_time=data.start_time,
            end_time=data.end_time,
            place=data.place,
            publisher=data.publisher,
            first_publish=int(time.time()),
            last_update=int(time.time())
        )
        db.add(new_event)
        db.commit()
        db.refresh(new_event)
        return {"result" : f"Create Event Successfull"}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"An error occurred when creating event: {e}")
