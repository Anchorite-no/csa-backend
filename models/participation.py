from sqlalchemy import Column, String, Integer, Text

from . import Base

class Participation(Base):
    __tablename__ = "participation"

    uid = Column(String(36), primary_key=True, index=True)
    eid = Column(Integer, primary_key=True, index=True)
    signup_time = Column(Integer)
    signup_ip = Column(String(64))
    signin_time = Column(Integer) # null if not signing in
    signin_ip = Column(String(64))
    signin_location = Column(String(64))