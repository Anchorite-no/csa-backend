from sqlalchemy import Column, Integer, Boolean, String, ForeignKey
from sqlalchemy.orm import relationship
from . import Base


class Admin(Base):
    __tablename__ = "admins"

    aid = Column(Integer, primary_key=True, autoincrement=True, index=True)
    uid = Column(String(36), ForeignKey("users.uid"), unique=True)
    is_active = Column(Boolean, default=True)

    role_id = Column(Integer, default=7)
