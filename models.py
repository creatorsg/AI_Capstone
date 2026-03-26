from sqlalchemy import Column, Integer, String, Date
from database import Base

class Child(Base):
    __tablename__ = "children"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    birth_date = Column(Date)
    gender = Column(String) 