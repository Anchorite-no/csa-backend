from sqlalchemy import Column, String, Integer, Text, ForeignKey
from sqlalchemy.orm import relationship

from models.participation import Participation
from . import Base


class Event(Base):
    __tablename__ = "event"

    eid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(Text)
    tag = Column(Text)
    image = Column(Text)
    description = Column(Text)
    # ecid = Column(Integer, ForeignKey('event_category.ecid'))
    ecid = Column(Integer)
    start_time = Column(Integer)
    end_time = Column(Integer)
    start_signup_time = Column(Integer)
    end_signup_time = Column(Integer)
    start_signin_time = Column(Integer)
    end_signin_time = Column(Integer)
    signin_code = Column(String(16))
    place = Column(Text)
    publisher = Column(String(36))
    first_publish = Column(Integer)
    last_update = Column(Integer)

    # users = relationship(
    #     "User",
    #     secondary=Participation.__tablename__,
    #     back_populates="events"
    # )
