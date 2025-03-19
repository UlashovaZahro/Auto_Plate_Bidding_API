from datetime import datetime
from pydantic import BaseModel
from typing import List, Optional
from decimal import Decimal

class PlateCreate(BaseModel):
    plate_number: str
    description: Optional[str] = None
    deadline: datetime
    is_active: bool = True

    class Config:
        from_attributes = True

class PlateResponse(BaseModel):
    id: int
    plate_number: str
    description: Optional[str] = None
    deadline: datetime
    is_active: bool
    highest_bid: Optional[float] = None 
    bids: Optional[List["BidResponse"]] = None

    class Config:
        from_attributes = True

class BidCreate(BaseModel):
    amount: Decimal
    plate_id: int

class BidResponse(BaseModel):
    id: int
    amount: float 
    user_id: int
    plate_id: int
    created_at: datetime

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    username: str
    email: str
    password: str