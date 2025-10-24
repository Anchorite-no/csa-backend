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
            detail="News not found"
        )

    content = news.content or ""
    image = news.image or ""

    try:
        db.delete(news)
        db.commit()
        
        deleted_count = cleanup_all_images(content, image)
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} image files when deleting news")
            
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
            detail="Current administrator does not have permission to perform this operation"
        )

    event_category = db.query(EventCategory).filter_by(ecid=data.ecid).first()
    if not event_category:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Event category not found"
        )

    try:
        db.delete(event_category)
        db.commit()
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error occurred when deleting event category: {e}"
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
            detail="Event not found"
        )

    content = event.description or ""
    image = event.image or ""

    try:
        db.delete(event)
        db.commit()
        
        deleted_count = cleanup_all_images(content, image)
        if deleted_count > 0:
            print(f"Cleaned up {deleted_count} image files when deleting event")
            
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred when deleting event: {e}"
        )

    return None
