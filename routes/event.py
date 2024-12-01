import time
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.auth import get_current_user
from models import get_db
from models.participation import Participation
from models.event_category import EventCategory
from models.relation.user_event import user_event
from models.event import Event
from models.user import User

router = APIRouter()

class ConciseEvent(BaseModel):
    eid: int
    title: str
    start_time: int
    end_time: int
    start_signup_time: int
    end_signup_time: int
    start_signin_time: int
    end_signin_time: int
    signin_location: str
    place: str
    publisher: str
    first_publish: int
    last_update: int
    tag: str
    image: str
    summary: str
    ecid: int
    event_category: str

    class Config:
        orm_mode = True

class EventCount(BaseModel):
    count: int


@router.get("/count", response_model=EventCount)
def get_events_count(
        category: int = None,
        db: Session = Depends(get_db)
):
    query = db.query(Event)
    if category:
        query = query.filter(ecid=category)
    count = query.count()
    return EventCount(count=count)


@router.get("/list", response_model=list[ConciseEvent])
def get_events_list(
        page: int = 1,
        size: int = 8,
        category: int = None,
        db: Session = Depends(get_db)
):
    events = db.query(Event).join(EventCategory, ecid=EventCategory.ecid)

    if category:
        events = events.filter(ecid=category)

    events = events.order_by(Event.first_publish.desc())
    events = events.offset((page - 1) * size).limit(size).all()

    concise_events = []
    for event_item in events:
        html = markdown(event_item.description)
        text_maker = HTML2Text()
        text_maker.ignore_images = True
        text = text_maker.handle(html)
        summary = text[:100] + "..." if len(text) > 100 else text

        concise_event = ConciseEvent(
            eid=event_item.eid,
            title=event_item.title,
            start_time=event_item.start_time,
            end_time=event_item.end_time,
            start_signup_time=event_item.start_signup_time,
            end_signup_time=event_item.end_signup_time,
            start_signin_time=event_item.start_signin_time,
            end_signin_time=event_item.end_signin_time,
            signin_location=event_item.signin_location,
            place=event_item.place,
            publisher=event_item.publisher,
            first_publish=event_item.first_publish,
            last_update=event_item.last_update,
            tag=event_item.tag,
            image=event_item.image,
            summary=summary,
            ecid=event_item.ecid,
            event_category=event_item.event_category.name
        )
        concise_events.append(concise_event)

    return concise_events

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

    class Config:
        orm_mode = True  # 使Pydantic模型能从ORM模型实例中读取数据

@router.get("/detail", response_model=EventDetail)
def get_event_detail(
    eid: int,
    db: Session = Depends(get_db)
):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(status_code=404, detail="活动未找到")

    publisher = db.query(User).filter_by(uid=event.publisher).first()
    if publisher:
        event.publisher = publisher.nick
    else:
        event.publisher = "未知"

    event_detail = EventDetail(**vars(event))
    return event_detail


class ParticipationItem(BaseModel):
    uid: str
    username: str
    signup_time: int
    signin_time: int | None
    signin_location: str | None


@router.get("/participations", response_model=list[ParticipationItem])
def get_participations(
        eid: int,
        page: int = 1,
        size: int = 8,
        db: Session = Depends(get_db)
):
    participations = db.query(Participation).join(User).filter(eid=eid)

    participations = participations.offset((page - 1) * size).limit(size).all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            username=participation.user.nick,
            signup_time=participation.signup_time,
            signin_time=participation.signin_time,
            signin_location=participation.signin_location
        )
        for participation in participations
    ]

    return participation_items

@router.post("/sign-up", response_model=list[ParticipationItem])
def sign_up(
    request: Request,
    eid: int,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    event = db\
        .query(Event)\
        .filter_by(eid=eid)\
        .first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="您报名的活动不存在"
        )

    try:
        new_participation = Participation(
            uid=uid,
            eid=eid,
            signup_time=int(time.time()),
            signup_ip=request.client.host,
            signin_time=None,
            signin_ip=None,
            signin_location=None,
        )

        db.add(new_participation)
        db.commit()
        return {"result": "sign up Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when creating event: {e}"
        )


@router.post("/sign-up", response_model=list[ParticipationItem])
def sign_up(
    request: Request,
    eid: int,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    event = db\
        .query(Event)\
        .filter_by(eid=eid)\
        .first()

    if not event:
        raise HTTPException(
            detail="您报名的活动不存在"
        )

    current_time = int(time.time())

    if (current_time > event.end_signup_time):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="报名已截止"
        )

    try:
        new_participation = Participation(
            uid=uid,
            eid=eid,
            signup_time=current_time,
            signup_ip=request.client.host,
            signin_time=None,
            signin_ip=None,
            signin_location=None,
        )

        db.add(new_participation)
        db.commit()
        return {"result": "sign up Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when creating event: {e}"
        )


@router.post("/sign-in", response_model=list[ParticipationItem])
def sign_in(
    request: Request,
    eid: int,
    uid: str = Depends(get_current_user),
    location: str = Form(...),
    db: Session = Depends(get_db)
):
    participation, event = db\
        .query(Participation, Event)\
        .join(Event, eid=Event.eid)\
        .filter_by(eid=eid, uid=uid)\
        .first()

    if not participation or not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="您签到的活动不存在，或者未成功报名"
        )

    current_time = int(time.time())

    if current_time > event.end_signin_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="签到已截止"
        )

    participation.signin_time = current_time
    participation.signin_ip = request.client.host
    participation.signin_location = location

    try:
        db.commit()
        return {"result": "sign in Successfully"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when signing up: {e}"
        )