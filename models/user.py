from sqlalchemy import Column, String, Integer

from . import Base


class User(Base):
    __tablename__ = "users"

    uid = Column(String(36), primary_key=True, index=True)
    nick = Column(String(32))
    passwd = Column(String(64))
    email = Column(String(64), unique=True)
    last_login = Column(Integer)