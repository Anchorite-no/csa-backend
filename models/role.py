from sqlalchemy import Column, Integer, String, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.ext.declarative import declared_attr
from . import Base  # 假设这是你的基类


# 基类：Role
class Role(Base):
    __tablename__ = 'roles'

    rid = Column(Integer, primary_key=True, index=True)

    @declared_attr
    def role_name(cls):
        if cls.__name__ == 'User_Role':
            return Column(String, default="会员", unique=True)
        elif cls.__name__ == 'Admin_Role':
            return Column(String, default="管理员", unique=True)
        return Column(String, unique=True)
    
    @declared_attr
    def description(cls):
        if cls.__name__ == 'User_Role':
            return Column(String, default="普通会员角色")
        elif cls.__name__ == 'Admin_Role':
            return Column(String, default="系统管理员角色")
        return Column(String)

    @declared_attr
    def __mapper_args__(cls):
        """用于区分子类并设置多表继承"""
        if cls.__name__ != 'Role':
            return {'polymorphic_identity': cls.__name__}
        return {}

    def __repr__(self):
        return f"<Role(rid={self.rid}, role_name={self.role_name}, description={self.description})>"


# 子类：User_Role，代表普通用户角色
class User_Role(Role):
    __tablename__ = 'user_roles'

    rid = Column(Integer, ForeignKey('roles.rid', ondelete='CASCADE'), primary_key=True)

    MEMBER = {"rid": 1, "role_name": "会员", "description": "普通会员角色"}
    OFFICER = {"rid": 2, "role_name": "干事", "description": "干事角色"}
    VICE_MINISTER = {"rid": 3, "role_name": "副部长", "description": "副部长角色"}
    MINISTER = {"rid": 4, "role_name": "部长", "description": "部长角色"}
    FINANCIAL_RESPONSIBLE = {"rid": 5, "role_name": "财务负责人", "description": "财务负责人角色"}
    PRESIDENT = {"rid": 6, "role_name": "会长", "description": "会长角色"}

    @classmethod
    def get_roles(cls):
        return [
            cls.MEMBER,
            cls.OFFICER,
            cls.VICE_MINISTER,
            cls.MINISTER,
            cls.FINANCIAL_RESPONSIBLE,
            cls.PRESIDENT
        ]


# 子类：Admin_Role，代表管理员角色
class Admin_Role(Role):
    __tablename__ = 'admin_roles'

    rid = Column(Integer, ForeignKey('roles.rid', ondelete='CASCADE'), primary_key=True)

    ADMIN = {"rid": 7, "role_name": "管理者", "description": "系统管理员"}
    PUBLISHER = {"rid": 8, "role_name": "发布者", "description": "内容发布者"}
    OPERATOR = {"rid": 9, "role_name": "运维", "description": "系统运维角色"}

    @classmethod
    def get_roles(cls):
        return [
            cls.ADMIN,
            cls.PUBLISHER,
            cls.OPERATOR
        ]
