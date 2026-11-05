from sqlalchemy import Column, Integer, String, Text
from app.core.database import Base


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(150), nullable=False)
    address = Column(Text, nullable=False)
    contact_number = Column(String(30), nullable=False)
