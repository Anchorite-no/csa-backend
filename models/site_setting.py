from sqlalchemy import Column, String

from models import Base


class SiteSetting(Base):
    __tablename__ = "site_setting"

    key = Column(String(128), primary_key=True)
    value = Column(String(256), nullable=False)
