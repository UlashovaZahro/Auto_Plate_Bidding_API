from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from sqlalchemy import func
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
from typing import List, Optional
from models import User, AutoPlate, Bid, get_db
from schemas import Token, UserCreate, PlateCreate, PlateResponse, BidCreate, BidResponse

SECRET_KEY = "Zahro"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

app = FastAPI(title="Auto Plate Bidding API")

def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    return user

async def get_current_admin(user: User = Depends(get_current_user)):
    if not user.is_staff:
        raise HTTPException(status_code=403, detail="Not enough permissions")
    return user

@app.post("/login/", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not verify_password(form_data.password, user.password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(data={"sub": user.username}, expires_delta=access_token_expires)
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/users/", response_model=UserCreate)
async def create_user(user: UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(User).filter(User.username == user.username).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Username already registered")
    hashed_password = get_password_hash(user.password)
    new_user = User(username=user.username, email=user.email, password=hashed_password, is_staff=False)
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    return user

@app.post("/plates/", response_model=PlateResponse)
async def create_plate(
    plate: PlateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    if plate.deadline <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Deadline must be in the future")
    if db.query(AutoPlate).filter(AutoPlate.plate_number == plate.plate_number).first():
        raise HTTPException(status_code=400, detail="Plate number already exists")
    new_plate = AutoPlate(
        plate_number=plate.plate_number,
        description=plate.description,
        deadline=plate.deadline,
        is_active=plate.is_active,
        created_by=current_user.id
    )
    db.add(new_plate)
    db.commit()
    db.refresh(new_plate)
    return new_plate

@app.get("/plates/", response_model=List[PlateResponse])
async def list_plates(
    ordering: Optional[str] = None,
    plate_number__contains: Optional[str] = None,
    db: Session = Depends(get_db)
):
    query = db.query(AutoPlate).filter(AutoPlate.is_active == True)
    if plate_number__contains:
        query = query.filter(AutoPlate.plate_number.contains(plate_number__contains))
    if ordering:
        query = query.order_by(AutoPlate.deadline.asc() if ordering == "deadline" else AutoPlate.deadline.desc())
    plates = query.all()
    for plate in plates:
        highest_bid = db.query(Bid).filter(Bid.plate_id == plate.id).order_by(Bid.amount.desc()).first()
        setattr(plate, "highest_bid", float(highest_bid.amount) if highest_bid else None)
    return plates

@app.get("/plates/{plate_id}/", response_model=PlateResponse)
async def get_plate(plate_id: int, db: Session = Depends(get_db)):
    plate = db.query(AutoPlate).filter(AutoPlate.id == plate_id).first()
    if not plate:
        raise HTTPException(status_code=404, detail="Plate not found")
    plate.bids = db.query(Bid).filter(Bid.plate_id == plate_id).all()
    highest_bid = db.query(Bid).filter(Bid.plate_id == plate.id).order_by(Bid.amount.desc()).first()
    setattr(plate, "highest_bid", float(highest_bid.amount) if highest_bid else None)
    return plate

@app.put("/plates/{plate_id}/", response_model=PlateResponse)
async def update_plate(
    plate_id: int,
    plate: PlateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    db_plate = db.query(AutoPlate).filter(AutoPlate.id == plate_id).first()
    if not db_plate:
        raise HTTPException(status_code=404, detail="Plate not found")
    if plate.deadline <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Deadline must be in the future")
    db_plate.plate_number = plate.plate_number
    db_plate.description = plate.description
    db_plate.deadline = plate.deadline
    db_plate.is_active = plate.is_active
    db.commit()
    db.refresh(db_plate)
    return db_plate

@app.delete("/plates/{plate_id}/")
async def delete_plate(
    plate_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin)
):
    db_plate = db.query(AutoPlate).filter(AutoPlate.id == plate_id).first()
    if not db_plate:
        raise HTTPException(status_code=404, detail="Plate not found")
    if db.query(Bid).filter(Bid.plate_id == plate_id).first():
        raise HTTPException(status_code=400, detail="Cannot delete plate with active bids")
    db.delete(db_plate)
    db.commit()
    return {"message": "Plate deleted"}

@app.post("/bids/", response_model=BidResponse)
async def create_bid(
    bid: BidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    plate = db.query(AutoPlate).filter(AutoPlate.id == bid.plate_id).first()
    if not plate:
        raise HTTPException(status_code=404, detail="Plate not found")
    if not plate.is_active or plate.deadline <= datetime.utcnow():
        raise HTTPException(status_code=400, detail="Bidding is closed")
    if bid.amount <= 0:
        raise HTTPException(status_code=400, detail="Bid amount must be positive")
    with db.begin():
        existing_bid = db.query(Bid).filter(Bid.user_id == current_user.id, Bid.plate_id == bid.plate_id).first()
        if existing_bid:
            raise HTTPException(status_code=400, detail="You already have a bid on this plate")
        highest_bid = db.query(Bid).filter(Bid.plate_id == bid.plate_id).order_by(Bid.amount.desc()).first()
        if highest_bid and bid.amount <= highest_bid.amount:
            raise HTTPException(status_code=400, detail="Bid must exceed current highest bid")
        new_bid = Bid(amount=bid.amount, user_id=current_user.id, plate_id=bid.plate_id)
        db.add(new_bid)
        db.commit()
        db.refresh(new_bid)
    return new_bid

@app.get("/bids/", response_model=List[BidResponse])
async def list_bids(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    bids = db.query(Bid).filter(Bid.user_id == current_user.id).all()
    return bids

@app.get("/bids/{bid_id}/", response_model=BidResponse)
async def get_bid(bid_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if bid.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this bid")
    return bid

@app.put("/bids/{bid_id}/", response_model=BidResponse)
async def update_bid(
    bid_id: int,
    bid: BidCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not db_bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if db_bid.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to update this bid")
    plate = db.query(AutoPlate).filter(AutoPlate.id == db_bid.plate_id).first()
    if plate.deadline <= datetime.utcnow():
        raise HTTPException(status_code=403, detail="Bidding period has ended")
    if bid.amount <= 0:
        raise HTTPException(status_code=400, detail="Bid amount must be positive")
    with db.begin(): 
        highest_bid = db.query(Bid).filter(Bid.plate_id == db_bid.plate_id, Bid.id != bid_id).order_by(Bid.amount.desc()).first()
        if highest_bid and bid.amount <= highest_bid.amount:
            raise HTTPException(status_code=400, detail="Bid must exceed current highest bid")
        db_bid.amount = bid.amount
        db.commit()
        db.refresh(db_bid)
    return db_bid

@app.delete("/bids/{bid_id}/")
async def delete_bid(
    bid_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    db_bid = db.query(Bid).filter(Bid.id == bid_id).first()
    if not db_bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    if db_bid.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this bid")
    plate = db.query(AutoPlate).filter(AutoPlate.id == db_bid.plate_id).first()
    if plate.deadline <= datetime.utcnow():
        raise HTTPException(status_code=403, detail="Bidding period has ended")
    db.delete(db_bid)
    db.commit()
    return {"message": "Bid deleted"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)