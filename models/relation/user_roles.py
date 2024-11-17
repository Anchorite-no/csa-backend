from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from models import Base

# user_role_association: 关联 User 和 Role 的多对多关系
user_role_association = Table(
    'user_role_association',  # 修改表名为 user_role_association
    Base.metadata,
    Column('uid', Integer, ForeignKey('users.uid'), primary_key=True),  # 用户 ID
    Column('rid', Integer, ForeignKey('roles.rid'), primary_key=True),  # 角色 ID
)
