from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from models import get_db
from models.relation.user_event import user_event
from models.event import Event
from models.user import User

router = APIRouter()


class ConciseEvent(BaseModel):
    eid: int
    title: str
    start_time: int
    end_time: int
    tag: str
    place: str
    first_publish: int
    last_update: int
    summary: str
    ecid: int
    event_category: str
    image: str


class EventCount(BaseModel):
    count: int


@router.get("/count", response_model=EventCount)
def get_events_count(
    category: int = None,
    db: Session = Depends(get_db)
):
    count = db.query(Event)
    count = count.filter_by(category=category) if category else count
    count = count.count()

    return EventCount(count=count)


@router.get("/list", response_model=list[ConciseEvent])
def get_events_list(
    page: int = 1,
    size: int = 8,
    category: int = None,
    db: Session = Depends(get_db)
):
    events = db.query(Event)
    if category:
        events = events.filter_by(category=category)
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

    events = [ConciseEvent(**vars(event_item)) for event_item in events]

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
    category: int
    image: str
    publisher: str


@router.get("/detail", response_model=EventDetail)
def get_event_detail(
    eid: str,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(status_code=404, detail="活动未找到")

    event = EventDetail(**vars(event))
    event.publisher = db.query(User).filter_by(
        uid=event.publisher).first().nick

    return event


# todo: which type? signin or signup participation has been defined. refer to it.


class ParticipationItem(BaseModel):
    uid: int
    # username: str unnecessary for uid available
    eid: int
    # event_title: str unnecessary for eid available
    # participation_time: datetime
    place: str


@router.get("/participations", response_model=list[ParticipationItem])
def get_participations(
    eid: int,
    page: int = 1,
    size: int = 8,
    db: Session = Depends(get_db)
):
    participations = db.query(user_event).join(User).join(Event).filter_by(
        eid=eid).order_by(user_event.participation_time.desc())
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
