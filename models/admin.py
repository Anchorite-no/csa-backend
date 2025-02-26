from sqlalchemy import Column, Integer, Boolean, String, ForeignKey
from sqlalchemy.orm import relationship
from . import Base

class Admin(Base):
    __tablename__ = 'admins'

    aid = Column(Integer, primary_key=True, autoincrement=True, index=True)
    uid = Column(String(36), ForeignKey('users.uid'), unique=True)
    is_active = Column(Boolean, default=True)
    uid = Column(Integer, ForeignKey('users.uid'), primary_key=True),

    role_id = Column(Integer, ForeignKey('roles.rid'))
    role = relationship("Role")
