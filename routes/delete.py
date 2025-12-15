import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from misc.auth import get_current_user_flexible
from misc.image_manager import cleanup_all_images
from models import get_db
from models.event import Event
from models.event_category import EventCategory
from models.news import News
from routes.admin import is_manager

router = APIRouter()
IMAGES_DIR = Path("uploads/images")


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
        
        news_img_dir_new = IMAGES_DIR / 'news' / str(data.nid)
        if news_img_dir_new.exists() and news_img_dir_new.is_dir():
            try:
                shutil.rmtree(news_img_dir_new)
                print(f"Deleted new image directory: {news_img_dir_new}")
            except Exception as e:
                print(f"Failed to delete new image directory {news_img_dir_new}: {e}")

        news_img_dir_legacy = IMAGES_DIR / str(data.nid)
        if news_img_dir_legacy.exists() and news_img_dir_legacy.is_dir():
            try:
                shutil.rmtree(news_img_dir_legacy)
                print(f"Deleted legacy image directory: {news_img_dir_legacy}")
            except Exception as e:
                print(f"Failed to delete legacy image directory {news_img_dir_legacy}: {e}")

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
):
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
    db: Session = Depends(get_db)
):
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
        
        # Try to delete the entire directory for this event
        event_img_dir = IMAGES_DIR / 'event' / str(data.eid)
        if event_img_dir.exists() and event_img_dir.is_dir():
            try:
                shutil.rmtree(event_img_dir)
                print(f"Deleted image directory: {event_img_dir}")
            except Exception as e:
                print(f"Failed to delete image directory {event_img_dir}: {e}")

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
