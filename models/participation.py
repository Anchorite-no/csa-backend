from sqlalchemy import Column, String, Integer, Text, ForeignKey, UniqueConstraint

from . import Base


class Participation(Base):
    __tablename__ = "participation"

    pid = Column(Integer, primary_key=True, autoincrement=True)
    uid = Column(
        String(36),
        ForeignKey('users.uid'),
    )
    eid = Column(
        Integer,
        ForeignKey('event.eid'),
    )
    signup_time = Column(Integer)
    signup_ip = Column(String(64))
    signin_time = Column(Integer)  # null if not signing in
    signin_ip = Column(String(64))
    signin_location = Column(String(64))

    # 创建eid和uid的唯一索引
    __table_args__ = (
        UniqueConstraint('uid', 'eid', name='unique_eid_uid'),
    )
