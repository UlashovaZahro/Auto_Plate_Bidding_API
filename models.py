from sqlalchemy import Column, Integer, Boolean, DateTime, String, ForeignKey, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from datetime import datetime  

connect_string = 'sqlite:///auksion.db'
connect_args = {'check_same_thread': False}
engine = create_engine(connect_string, connect_args=connect_args)
Base = declarative_base()
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, unique=True, nullable=False)
    email = Column(String, unique=True, nullable=False)
    password = Column(String, nullable=False)  # Hashed password
    is_staff = Column(Boolean, default=False, nullable=False)

class AutoPlate(Base):
    __tablename__ = 'autoplate'
    id = Column(Integer, primary_key=True, autoincrement=True)
    plate_number = Column(String(10), nullable=False, unique=True)
    description = Column(String, nullable=True)
    deadline = Column(DateTime, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey('users.id'), nullable=False)

class Bid(Base):
    __tablename__ = 'bids'
    id = Column(Integer, primary_key=True, autoincrement=True)
    amount = Column(Float, nullable=False)  # Integer o‘rniga Float ishlatildi
    user_id = Column(Integer, ForeignKey('users.id'), nullable=False)
    plate_id = Column(Integer, ForeignKey('autoplate.id'), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)