from sqlalchemy import Column, Integer, String, Text
from database import Base

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, index=True)
    email = Column(String, unique=True, index=True)
    hashed_password = Column(String)
    bio = Column(Text, nullable=True)
    phone = Column(String, nullable=True)
    image_url = Column(String, nullable=True)
