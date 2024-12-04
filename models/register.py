from sqlalchemy import Column, String, Integer

from . import Base  # 假设这是你的基类


class Register(Base):
    __tablename__ = "regesiter"

    seid = Column(String(24), primary_key=True, index=True)
    uid = Column(String(36), unique=True)
    nick = Column(String(32))
    openid = Column(String(64), unique=True)
    start_time = Column(Integer)

    def __repr__(self):
        return f"<Register(seid={self.seid}, uid={self.uid}, openid={self.openid})>"
