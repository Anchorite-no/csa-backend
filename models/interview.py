from sqlalchemy import Column, String, Integer, Text, Boolean, ForeignKey, DateTime, Float
from datetime import datetime
from sqlalchemy.orm import relationship

from . import Base

class InterviewTimeSlot(Base):
    __tablename__ = "interview_time_slot"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    slot_name = Column(String(50), nullable=False)  # 如 "周一 19:00-20:00"
    day_of_week = Column(String(10), nullable=False)  # 如 "周一"
    start_time = Column(String(10), nullable=False)  # 如 "19:00"
    end_time = Column(String(10), nullable=False)  # 如 "20:00"
    week_number = Column(Integer, default=0)  # 0=本周, 1=下周
    venue = Column(String(50), default="场地A")  # 面试场地
    max_capacity = Column(Integer, default=10)  # 最大容量
    current_count = Column(Integer, default=0)  # 当前人数
    is_active = Column(Boolean, default=True)  # 是否激活
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<InterviewTimeSlot(id={self.id}, slot_name='{self.slot_name}', current_count={self.current_count})>"

class Interview(Base):
    __tablename__ = "interview"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    uid = Column(String(36), ForeignKey("recruitment.uid"), nullable=False, index=True)
    time_slot_id = Column(Integer, ForeignKey("interview_time_slot.id"), nullable=True)  # 关联时间段ID
    
    # 面试阶段
    stage = Column(String(20), nullable=False)  # 'screening', 'first_round', 'second_round'
    
    # 面试基本信息
    interview_date = Column(DateTime, nullable=False)
    interview_format = Column(String(20), nullable=False, default='one_to_one')  # 面试形式: one_to_one, one_to_many, many_to_many
    interview_duration = Column(Integer)  # 面试时长（分钟）
    location = Column(String(100))  # 面试地点
    notes = Column(Text)  # 备注
    status = Column(String(20), default='scheduled')  # 排班状态: scheduled, completed, cancelled
    notification_sent = Column(Boolean, default=False)  # 是否已发送通知
    
    # 评分项目（1-10分）
    technical_skills = Column(Float)  # 技术能力
    communication_skills = Column(Float)  # 沟通能力
    problem_solving = Column(Float)  # 问题解决能力
    teamwork = Column(Float)  # 团队协作能力
    learning_ability = Column(Float)  # 学习能力
    motivation = Column(Float)  # 动机和热情
    
    # 总体评分
    overall_score = Column(Float)  # 总体评分
    
    # 面试结果
    result = Column(String(20), default='pending')  # 'pass', 'fail', 'pending', 'recommended'
    
    # 详细评价
    strengths = Column(Text)  # 优点
    weaknesses = Column(Text)  # 不足
    technical_questions = Column(Text)  # 技术问题及回答
    behavioral_questions = Column(Text)  # 行为问题及回答
    additional_notes = Column(Text)  # 其他备注
    
    # 推荐部门
    recommended_department = Column(String(50))  # 推荐部门
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # 关联关系 - 使用字符串引用避免循环导入
    recruitment = relationship("Recruitment", back_populates="interviews", lazy="joined")
    time_slot = relationship("InterviewTimeSlot", lazy="joined")
    
    def __repr__(self):
        return f"<Interview(id={self.id}, uid={self.uid}, stage={self.stage}, result={self.result})>"
    
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
