from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from misc.auth import get_current_admin
from misc.image_manager import cleanup_all_images
from models import get_db
from models.event import Event
from models.event_category import EventCategory
from models.news import News
from routes.admin import is_manager

router = APIRouter()


class DeleteNews(BaseModel):
    nid: int


class DeleteEventCategory(BaseModel):
    ecid: int


class DeleteEvent(BaseModel):
    eid: int


@router.post("/news")
def delete_news(
    data: DeleteNews,
    db: Session = Depends(get_db)
):

    news = db.query(News).filter_by(nid=data.nid).first()

    if not news:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="新闻未找到"
        )

    content = news.content or ""
    image = news.image or ""

    try:
        db.delete(news)
        db.commit()
        
        deleted_count = cleanup_all_images(content, image)
        if deleted_count > 0:
            print(f"删除新闻时清理了 {deleted_count} 个图片文件")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when deleting news: {e}"
        )

    return None


@router.post("/event_category")
def delete_event(
    data: DeleteEventCategory,
    db: Session = Depends(get_db),
    aid: str = Depends(get_current_admin)
):
    if not is_manager(db, aid):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="当前管理员没有权限进行此操作"
        )

    event_category = db.query(EventCategory).filter_by(ecid=data.ecid).first()
    if not event_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="活动类型未找到"
        )

    try:
        db.delete(event_category)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除活动类型时发生错误: {e}"
        )

    return None


@router.post("/event")
def delete_event(
        data: DeleteEvent,
        db: Session = Depends(get_db),
        
):
    
    
    
    
    #     )

    event = db.query(Event).filter_by(eid=data.eid).first()

    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="活动未找到"
        )

    content = event.description or ""
    image = event.image or ""

    try:
        db.delete(event)
        db.commit()
        
        deleted_count = cleanup_all_images(content, image)
        if deleted_count > 0:
            print(f"删除活动时清理了 {deleted_count} 个图片文件")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除活动时发生错误: {e}"
        )

    return None
