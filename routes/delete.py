from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db
from models.event import Event
from models.news import News

router = APIRouter()


class DeleteNews(BaseModel):
    nid: int


@router.post("/news")
def delete_news(
    data: DeleteNews,
    db: Session = Depends(get_db),
):
    news = db.query(News).filter_by(nid=data.nid).first()

    if not news:
        raise HTTPException(status_code=404, detail="新闻未找到")

    db.delete(news)
    db.commit()

    return None


@router.post("/event")
def delete_event(data: DeleteNews, db: Session = Depends(get_db)):
    event = db.query(Event).filter_by(eid=data.eid).first()

    if not event:
        raise HTTPException(status_code=404, detail="活动未找到")

    db.delete(event)
    db.commit()

    return None
