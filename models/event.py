from sqlalchemy import Column, String, Integer, Text

from . import Base


class Event(Base):
    __tablename__ = "event"

    eid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(Text)
    tag = Column(Text)
    image = Column(Text)
    description = Column(Text)
    category = Column(Integer)
    start_time = Column(Integer)
    end_time = Column(Integer)
    place = Column(Text)
    publisher = Column(String(36))
    first_publish = Column(Integer)
    last_update = Column(Integer)