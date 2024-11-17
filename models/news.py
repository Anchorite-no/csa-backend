from sqlalchemy import Column, String, Integer, Text

from . import Base

class News(Base):
    __tablename__ = "news"

    nid = Column(Integer, primary_key=True, index=True, autoincrement=True)
    title = Column(Text)
    tag = Column(Text)
    content = Column(Text)
    first_publish = Column(Integer)
    last_update = Column(Integer)
    publisher = Column(String(36))