import pytest
from fastapi.testclient import TestClient
from main import app
from models import Base, engine, SessionLocal
from sqlalchemy.orm import Session

@pytest.fixture
def client():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    return TestClient(app)

@pytest.fixture
def db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def test_create_user(client: TestClient):
    response = client.post("/users/", json={"username": "testuser", "email": "test@example.com", "password": "testpass"})
    assert response.status_code == 200
    assert response.json()["username"] == "testuser"

def test_login(client: TestClient, db: Session):
    client.post("/users/", json={"username": "testuser", "email": "test@example.com", "password": "testpass"})
    response = client.post("/login/", data={"username": "testuser", "password": "testpass"})
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_create_plate_unauthorized(client: TestClient):
    response = client.post("/plates/", json={"plate_number": "ABC123", "deadline": "2025-12-31T00:00:00"})
    assert response.status_code == 401