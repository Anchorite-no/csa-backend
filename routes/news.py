from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from markdown import markdown
from html2text import HTML2Text

from misc.model import aid_to_nick
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
    summary: str
    category: int
    image: str


class Count(BaseModel):
    count: int


@router.get("/count", response_model=Count)
def get_news_count(category: int = None,db: Session = Depends(get_db)):
    count = db.query(News)
    count = count.filter(News.first_publish > 0)  # Filter out drafts
    count = count.filter_by(category=category) if category else count
    count = count.count()

    return Count(count=count)


@router.get("/list", response_model=list[NewsItem])
def get_news_list(
    page: int, size: int, category: int = None, db: Session = Depends(get_db)
):
    news = db.query(News)
    news = news.filter(News.first_publish > 0)  # Filter out drafts
    if category:
        news = news.filter_by(category=category)
    news = news.order_by(News.first_publish.desc())
    news = news.offset((page - 1) * size)
    news = news.limit(size)
    news = news.all()

    for news_item in news:
        html = markdown(news_item.content)
        text_maker = HTML2Text()
        text_maker.ignore_images = True
        text = text_maker.handle(html)
        news_item.summary = text[:100] + "..." if len(text) > 100 else text

    news = [NewsItem(**vars(news_item)) for news_item in news]

    return news


class NewsDetail(BaseModel):
    title: str
    tag: str
    content: str
    category: int
    last_update: int
    first_publish: int
    category: int
    image: str


@router.get("/detail", response_model=NewsDetail)
def get_news_detail(nid: str, db: Session = Depends(get_db)):
    news = db.query(News).filter_by(nid=nid).first()

    if not news:
        raise HTTPException(status_code=404, detail="News not found")

    news = NewsDetail(**vars(news))

    return news
