from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from models import get_db
from models.news import News
from models.user import User

router = APIRouter()


class NewsItem(BaseModel):
    nid: int
    title: str
    tag: str
    first_publish: int
    last_update: int


class Count(BaseModel):
    count: int


@router.get("/count", response_model=Count)
def get_news_count(db: Session = Depends(get_db)):
    count = db.query(News).count()

    return Count(count=count)


@router.get("/list", response_model=list[NewsItem])
def get_news_list(page: int, size: int, db: Session = Depends(get_db)):
    news = db.query(News)
    news = news.order_by(News.first_publish.desc())
    news = news.offset((page - 1) * size)
    news = news.limit(size)
    news = news.all()

    news = [NewsItem(**vars(news_item)) for news_item in news]

    return news


class NewsDetail(BaseModel):
    title: str
    tag: str
    content: str
    last_update: int
    first_publish: int
    publisher: str


@router.get("/detail", response_model=NewsDetail)
def get_news_detail(nid: str, db: Session = Depends(get_db)):
    news = db.query(News).filter_by(nid=nid).first()

    if not news:
        raise HTTPException(status_code=404, detail="新闻未找到")

    news = NewsDetail(**vars(news))
    news.publisher = db.query(User).filter_by(uid=news.publisher).first().nick

    return news
