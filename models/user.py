from sqlalchemy import Column, String, Integer, ForeignKey
from sqlalchemy.orm import relationship

from models.participation import Participation
from . import Base  # 假设这是你的基类


class User(Base):
    __tablename__ = "users"

    uid = Column(String(36), primary_key=True, index=True)
    nick = Column(String(32))
    passwd = Column(String(64))
    email = Column(String(64), unique=True)
    last_login = Column(Integer)

    events = relationship(
        "Event",
        secondary=Participation.__tablename__,
        back_populates="users"
    )

    role_id = Column(Integer, ForeignKey('roles.rid'))
    role = relationship("Role")

    def __repr__(self):
        return f"<User(uid={self.uid}, username={self.username}, role_id={self.role_id})>"
