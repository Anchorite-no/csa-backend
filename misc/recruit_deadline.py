"""Recruitment settings shared by every worker through the database."""

import argparse
import re
from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import get_config
from models import SessionLocal, engine
from models.site_setting import SiteSetting

BEIJING = timezone(timedelta(hours=8))
DEADLINE_KEY = "recruit_deadline"


def parse_deadline(value: str) -> datetime:
    value = value.strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        # Keep date-only clients working, with an explicit end-of-day minute.
        day = datetime.strptime(value, "%Y-%m-%d").date()
        return datetime.combine(day, time(23, 59), tzinfo=BEIJING)
    if not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}"
        r"(?::\d{2}(?:\.\d{1,6})?)?(?:Z|[+-]\d{2}:\d{2})?",
        value,
    ):
        raise ValueError("请使用 YYYY-MM-DD 或 ISO 8601 日期时间（北京时间）")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        result = result.replace(tzinfo=BEIJING)
    return result.astimezone(BEIJING)


def get_recruit_deadline(db: Session) -> datetime:
    # Select the scalar on every request, bypassing both process caches and
    # SQLAlchemy's ORM identity map.
    value = db.execute(
        select(SiteSetting.value).where(SiteSetting.key == DEADLINE_KEY)
    ).scalar_one_or_none()
    if value is None:
        legacy = parse_deadline(get_config().RECRUIT_DEADLINE).isoformat()
        db.add(SiteSetting(key=DEADLINE_KEY, value=legacy))
        try:
            db.commit()
        except IntegrityError:
            # Another worker seeded the same key first; keep its value.
            db.rollback()
        value = db.execute(
            select(SiteSetting.value).where(SiteSetting.key == DEADLINE_KEY)
        ).scalar_one()
    return parse_deadline(value)


def set_recruit_deadline(db: Session, value: str) -> datetime:
    deadline = parse_deadline(value)
    stored = deadline.isoformat()
    result = db.execute(
        update(SiteSetting)
        .where(SiteSetting.key == DEADLINE_KEY)
        .values(value=stored)
    )
    if not result.rowcount:
        db.add(SiteSetting(key=DEADLINE_KEY, value=stored))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        db.execute(
            update(SiteSetting)
            .where(SiteSetting.key == DEADLINE_KEY)
            .values(value=stored)
        )
        db.commit()
    return deadline


def deadline_status(db: Session) -> dict:
    deadline = get_recruit_deadline(db)
    now = datetime.now(BEIJING)
    return {
        "deadline": deadline.isoformat(),
        "timezone": "Asia/Shanghai",
        "server_time": now.isoformat(),
        "is_open": now < deadline,
    }


def require_recruitment_open(db: Session) -> None:
    deadline = get_recruit_deadline(db)
    if datetime.now(BEIJING) >= deadline:
        raise HTTPException(
            status_code=403,
            detail=f"纳新已于 {deadline.strftime('%Y-%m-%d %H:%M')}（北京时间）截止",
        )


def initialize_recruit_deadline() -> None:
    with SessionLocal() as db:
        get_recruit_deadline(db)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--set", dest="deadline", help="Set an ISO 8601 deadline")
    args = parser.parse_args()
    # Run once before starting multiple workers on the first deployment.
    SiteSetting.__table__.create(bind=engine, checkfirst=True)
    with SessionLocal() as db:
        value = (
            set_recruit_deadline(db, args.deadline)
            if args.deadline
            else get_recruit_deadline(db)
        )
        print(value.isoformat())
