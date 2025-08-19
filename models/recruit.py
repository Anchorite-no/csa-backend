from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, UniqueConstraint, DateTime
from datetime import datetime

from . import Base  # 假设这是你的基类

class Recruitment(Base):
    __tablename__ = "recruitment"

    name = Column(String(24))
    render = Column(Boolean) # false 为 男， true 为 女
    uid = Column(String(36), primary_key=True, index=True, unique=True)
    major_id = Column(String(24))
    major_name = Column(String(24))
    college_id = Column(String(24))
    college_name = Column(String(24))
    grade = Column(Integer)
    phone = Column(String(24))
    degree = Column(Integer)

    office_department_willing = Column(Integer)
    competition_department_willing = Column(Integer)
    activity_department_willing = Column(Integer)
    research_department_willing = Column(Integer)

    if_agree_to_be_reassigned = Column(Boolean)
    if_be_member = Column(Boolean)
    introduction = Column(Text)
    skill = Column(Text)

    def __repr__(self):
        return f"<Recruitment(name={self.name}, render={self.render}, uid={self.uid}, major_id={self.major_id}, major_name={self.major_name}, college_id={self.college_id}, college_name={self.college_name}, grade={self.grade}, phone={self.phone}, office_department_willing={self.office_department_willing}, competition_department_willing={self.competition_department_willing}, activity_department_willing={self.activity_department_willing}, research_department_willing={self.research_department_willing}, if_agree_to_be_reassigned={self.if_agree_to_be_reassigned}, if_be_member={self.if_be_member}, introduction={self.introduction}, skill={self.skill})>"


class Evaluation(Base):
    __tablename__ = "evaluation"

    uid = Column(String(36), primary_key=True, index=True, unique=True)
    evaluation_status = Column(String(20), default='pending')  # pending, accepted, rejected
    evaluation_comment = Column(Text)
    evaluation_time = Column(DateTime, default=datetime.utcnow)
    evaluator_id = Column(String(36))  # 评价人ID
    assigned_department = Column(String(50))  # 分配的部门