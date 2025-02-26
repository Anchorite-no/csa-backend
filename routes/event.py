import time
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.model import aid_to_nick
from misc.auth import get_current_user
from models import get_db
from models.participation import Participation
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
    category: int
    image: str


class EventCount(BaseModel):
    count: int


@router.get("/count", response_model=EventCount)
def get_events_count(category: int = None, db: Session = Depends(get_db)):
    count = db.query(Event)
    count = count.filter_by(ecid=category) if category else count
    count = count.count()

    return EventCount(count=count)


@router.get("/list", response_model=list[ConciseEvent])
def get_events_list(
    page: int = 1, size: int = 8, category: int = None, db: Session = Depends(get_db)
):
    events = db.query(Event)
    if category:
        events = events.filter_by(ecid=category)

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
        event_item.category = event_item.ecid

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
def get_event_detail(eid: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="活动未找到")
    
    event = vars(event)

    event["publisher"] = aid_to_nick(db, event["publisher"])
    event["category"] = event["ecid"]

    event_detail = EventDetail(**event)

    return event_detail


# todo: which type? signin or signup participation has been defined. refer to it.


class ParticipationItem(BaseModel):
    uid: str
    # username: str unnecessary for uid available
    eid: int
    # event_title: str unnecessary for eid available
    # participation_time: datetime
    place: str


@router.get("/participations", response_model=list[ParticipationItem])
def get_participations(
    eid: int, page: int = 1, size: int = 8, db: Session = Depends(get_db)
):
    participations = (
        db.query(Participation, User, Event)
        .join(User, Participation.uid == User.uid)
        .join(Event, Participation.eid == Event.eid)
        .filter_by(eid=eid)
        .order_by(Participation.signup_time.desc())
    )
    participations = participations.offset((page - 1) * size)
    participations = participations.limit(size)
    participations = participations.all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            username=user.nick,
            eid=participation.eid,
            event_title=event.title,
            participation_time=participation.signin_time,
            place=participation.signin_location,
        )
        for participation, user, event in participations
    ]

    return participation_items


@router.post("/sign-up", response_model=list[ParticipationItem])
def sign_up(
    request: Request,
    eid: int,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="您报名的活动不存在"
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
            detail=f"An error occurred when creating event: {e}",
        )


@router.post("/sign-up", response_model=list[ParticipationItem])
def sign_up(
    request: Request,
    eid: int,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(detail="您报名的活动不存在")

    current_time = int(time.time())

    if current_time > event.end_signup_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="报名已截止"
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
            detail=f"An error occurred when creating event: {e}",
        )


@router.post("/sign-in", response_model=list[ParticipationItem])
def sign_in(
    request: Request,
    eid: int,
    uid: str = Depends(get_current_user),
    location: str = Form(...),
    db: Session = Depends(get_db),
):
    participation, event = (
        db.query(Participation, Event)
        .join(Event, Participation.eid == Event.eid)
        .filter_by(eid=eid, uid=uid)
        .first()
    )

    if not participation or not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="您签到的活动不存在，或者未成功报名",
        )

    current_time = int(time.time())

    if current_time > event.end_signin_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="签到已截止"
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
            detail=f"An error occurred when signing up: {e}",
        )
