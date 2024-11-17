from sqlalchemy import Table, Column, Integer, ForeignKey
from sqlalchemy.orm import relationship
from models import Base

admin_role_association = Table(
    'admin_role_association',
    Base.metadata,
    Column('aid', Integer, ForeignKey('admins.aid'), primary_key=True),
    Column('rid', Integer, ForeignKey('roles.rid'), primary_key=True),
)
