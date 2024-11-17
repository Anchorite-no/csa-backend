from sqlalchemy import Table, Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from models import Base

user_event = Table(
    'user_event',
    Base.metadata,
    Column('uid', Integer, ForeignKey('users.uid'), primary_key=True),
    Column('eid', Integer, ForeignKey('event.eid'), primary_key=True),
    Column('participation_time', DateTime, default=func.now()),
    Column('place', String, index=True),
)