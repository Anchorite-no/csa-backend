import time
from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.model import aid_to_nick
from misc.auth import get_current_user, login_required_admin
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
    start_signin_time: Optional[int]
    end_signin_time: Optional[int]
    start_signup_time: Optional[int]
    end_signup_time: Optional[int]


@router.get("/detail", response_model=EventDetail)
def get_event_detail(eid: str, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(eid=eid).first()

    if not event:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")

    event = vars(event)

    event["publisher"] = aid_to_nick(db, event["publisher"])
    event["category"] = event["ecid"]

    event_detail = EventDetail(**event)

    return event_detail




class ParticipationItem(BaseModel):
    uid: str
    nick: str
    eid: int
    participation_time: int


class ParticipationResponse(BaseModel):
    result: list[ParticipationItem]
    count: int


@router.get(
    "/participations",
    response_model=ParticipationResponse,
    dependencies=[Depends(login_required_admin)],
)
def get_participations(
    eid: int, page: int = 1, size: int = 8, db: Session = Depends(get_db)
):
    participations = (
        db.query(Participation, User)
        .join(User, Participation.uid == User.uid)
        .filter(Participation.eid == eid)
        .filter(Participation.signin_time != None)
        .order_by(Participation.signup_time.desc())
    )

    count = participations.count()

    if size != 0:
        participations = participations.offset((page - 1) * size)
        participations = participations.limit(size)
        
    participations = participations.all()

    participation_items = [
        ParticipationItem(
            uid=participation.uid,
            nick=user.nick,
            eid=participation.eid,
            participation_time=participation.signin_time,
        )
        for participation, user in participations
    ]

    return ParticipationResponse(result=participation_items, count=count)


class SignupItem(BaseModel):
    eid: int


@router.post("/sign-up")
def sign_up(
    request: Request,
    data: SignupItem,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    event = db.query(Event).filter_by(eid=data.eid).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="The event you registered for does not exist"
        )

    current_time = int(time.time())

    if current_time > event.end_signup_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Registration has closed"
        )

    try:
        new_participation = Participation(
            uid=uid,
            eid=data.eid,
            signup_time=current_time,
            signup_ip=request.client.host,
            signin_time=None,
            signin_ip=None,
        )

        db.add(new_participation)
        db.commit()
        return {"msg": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when creating event: {e}",
        )


class SignInItem(BaseModel):
    eid: int
    signin_code: str


@router.post("/sign-in")
def sign_in(
    request: Request,
    data: SignInItem,
    uid: str = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    participation, event = (
        db.query(Participation, Event)
        .join(Event, Participation.eid == Event.eid)
        .filter(Participation.eid == data.eid)
        .filter(Participation.uid == uid)
        .first()
    )

    if not participation or not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The event you are checking in does not exist, or you have not successfully registered",
        )

    current_time = int(time.time())

    if current_time > event.end_signin_time:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Check-in has closed"
        )

    if event.signin_code != data.signin_code:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect check-in code"
        )

    participation.signin_time = current_time
    participation.signin_ip = request.client.host

    try:
        db.commit()
        return {"msg": "success"}
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when signing up: {e}",
        )
