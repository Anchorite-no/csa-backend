from sqlalchemy import Column, String, Integer, Text
from sqlalchemy.orm import relationship
from . import Base

class EventCategory(Base):
    __tablename__ = "event_category"

    ecid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    description = Column(Text)

    
