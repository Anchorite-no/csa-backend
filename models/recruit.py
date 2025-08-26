from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, UniqueConstraint, DateTime, Float
from sqlalchemy.orm import relationship
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
    
    # 评价相关字段
    evaluation_status = Column(String(20), default='pending')  # pending, accepted, rejected
    evaluation_time = Column(DateTime, default=datetime.utcnow)
    evaluator_id = Column(String(36))  # 评价人ID
    assigned_department = Column(String(50))  # 分配的部门
    
    # 面试相关字段
    interview_status = Column(String(20), default='first_round')  # first_round, second_round, completed
    interview_time_slots = Column(Text)  # 面试时间段选择，存储为JSON字符串
    interview_completed = Column(Boolean, default=False)  # 当前阶段面试是否已完成
    first_round_passed = Column(Boolean, default=False)  # 一面是否通过
    second_round_passed = Column(Boolean, default=False)  # 二面是否通过
    
    # 录取相关字段
    is_admitted = Column(Boolean, default=False)  # 是否录取
    admission_time = Column(DateTime)  # 录取时间
    
    # 关联关系
    interviews = relationship("Interview", back_populates="recruitment", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Recruitment(name={self.name}, render={self.render}, uid={self.uid}, major_id={self.major_id}, major_name={self.major_name}, college_id={self.college_id}, college_name={self.college_name}, grade={self.grade}, phone={self.phone}, office_department_willing={self.office_department_willing}, competition_department_willing={self.competition_department_willing}, activity_department_willing={self.activity_department_willing}, research_department_willing={self.research_department_willing}, if_agree_to_be_reassigned={self.if_agree_to_be_reassigned}, if_be_member={self.if_be_member}, introduction={self.introduction}, skill={self.skill})>"


class Evaluation(Base):
    __tablename__ = "evaluation"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uid = Column(String(36), ForeignKey("recruitment.uid"), nullable=False)
    evaluator_id = Column(String(36), nullable=False)  # 评价人ID
    evaluator_name = Column(String(50), nullable=False)  # 评价人姓名
    evaluation_comment = Column(Text, nullable=False)  # 评价意见
    evaluation_time = Column(DateTime, default=datetime.utcnow)
    department = Column(String(50))  # 评价人所属部门
    
    # 评分项目（1-10分）- 与面试管理字段对齐
    technical_skills = Column(Float)  # 技术能力
    communication_skills = Column(Float)  # 沟通能力
    problem_solving = Column(Float)  # 问题解决能力
    teamwork = Column(Float)  # 团队协作能力
    learning_ability = Column(Float)  # 学习能力
    motivation = Column(Float)  # 动机和热情
    
    # 总体评分
    overall_score = Column(Float)  # 总体评分
    
    # 详细评价
    strengths = Column(Text)  # 优点
    weaknesses = Column(Text)  # 不足
    
    # 评价结果
    result = Column(String(20), default='pending')  # 'pass', 'fail', 'pending', 'recommended'
    
    # 推荐部门
    recommended_department = Column(String(50))  # 推荐部门

    def __repr__(self):
        return f"<Evaluation(id={self.id}, uid={self.uid}, evaluator_id={self.evaluator_id}, evaluator_name={self.evaluator_name}, evaluation_comment={self.evaluation_comment}, evaluation_time={self.evaluation_time}, department={self.department})>"
    
    def calculate_overall_score(self):
        """计算总体评分"""
        scores = [
            self.technical_skills,
            self.communication_skills,
            self.problem_solving,
            self.teamwork,
            self.learning_ability,
            self.motivation
        ]
        valid_scores = [score for score in scores if score is not None]
        if valid_scores:
            return sum(valid_scores) / len(valid_scores)
        return None
