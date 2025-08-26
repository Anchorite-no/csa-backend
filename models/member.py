from sqlalchemy import Column, String, Integer, Text, Boolean, DateTime, Float
from datetime import datetime
from . import Base

class Member(Base):
    __tablename__ = "member"

    # 基本信息（从纳新者迁移）
    uid = Column(String(36), primary_key=True, index=True, unique=True)
    name = Column(String(24), nullable=False)
    render = Column(Boolean)  # false 为 男， true 为 女
    major_id = Column(String(24))
    major_name = Column(String(24))
    college_id = Column(String(24))
    college_name = Column(String(24))
    grade = Column(Integer)
    phone = Column(String(24))
    degree = Column(Integer)
    
    # 干事特有字段
    department = Column(String(50), nullable=False)  # 所属部门：office, competition, research, activity
    position = Column(String(50), default='干事')  # 职位：干事、副部长、部长等
    join_date = Column(DateTime, default=datetime.utcnow)  # 加入时间
    is_active = Column(Boolean, default=True)  # 是否在职
    
    # 财务信息
    bank_card = Column(String(20))  # 银行卡号
    bank_name = Column(String(50))  # 开户行
    account_holder = Column(String(24))  # 开户人姓名
    
    # 工作信息
    work_hours = Column(Float, default=0.0)  # 工作时长
    performance_score = Column(Float, default=0.0)  # 绩效评分
    evaluation_count = Column(Integer, default=0)  # 评价次数
    
    # 联系信息
    email = Column(String(100))
    wechat = Column(String(50))
    qq = Column(String(20))
    
    # 备注信息
    notes = Column(Text)  # 备注
    skills = Column(Text)  # 技能特长
    
    # 时间戳
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"<Member(uid={self.uid}, name={self.name}, department={self.department}, position={self.position})>"
