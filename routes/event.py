from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from models import get_db
from models.event import Event
from models.user import User

router = APIRouter()


class EventItem(BaseModel):
    eid: int
    title: str
    start_time: int
    end_time: int
    tag: str
    place: str
    first_publish: int
    last_update: int
    summary: str

class Count(BaseModel):
    count: int

@router.get("/count", response_model=Count)
def get_events_count(db: Session = Depends(get_db)):
    count = db.query(Event).count()

    return Count(count=count)


@router.get("/list", response_model=list[EventItem])
def get_events_list(page: int = 1, size: int = 8, db: Session = Depends(get_db)):
    events = db.query(Event)
    events = events.order_by(Event.first_publish.desc())
    events = events.offset((page - 1) * size)
    events = events.limit(size)
    events = events.all()

    for event_item in events:
        html = markdown(event_item.description)
        text_maker = HTML2Text()
        text_maker.ignore_images = True
        text = text_maker.handle(html)
        event_item.summary = text[:100] + "..." if len(text) > 100 else text

    events = [EventItem(**vars(event_item)) for event_item in events]

    return events


class EventDetail(BaseModel):
    title: str
    tag: str
    description: str
    start_time: int
    end_time: int
    last_update: int
    first_publish: int
    place: str
    publisher: str


@router.get("/detail", response_model=EventDetail)
def get_event_detail(eid: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(status_code=404, detail="活动未找到")

    event = EventDetail(**vars(event))
    event.publisher = db.query(User).filter_by(uid=event.publisher).first().nick

    return event



