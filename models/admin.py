from sqlalchemy import Column, Integer, Boolean, String, ForeignKey
from sqlalchemy.orm import relationship
from . import Base  # 假设这是你的基类

class Admin(Base):
    __tablename__ = 'admins'

    aid = Column(Integer, primary_key=True, autoincrement=True, index=True)
    is_active = Column(Boolean, default=True)

    role_id = Column(Integer, ForeignKey('roles.rid'))
    role = relationship("Role")
