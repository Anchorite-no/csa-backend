import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from models import Base, get_db

SQLALCHEMY_DATABASE_URL = "sqlite:///./test.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

BASE_URL = "/api/create"

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
def get_test_token():
    response = client.post(f"/api/user/register", json={
        "uid": "1231231235",
        "nick": "TestUser",
        "passwd": "testpassword",
        "email": "testuser@example.com"
    })
    assert response.status_code == 200
    assert response.json()["access_token"] is not None

    response = client.post(f"/api/user/login", json={
        "uid": "1231231235",
        "passwd": "testpassword"
    })
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture(scope="module")
def token(setup_database):
    return get_test_token()

def test_create_news(token):
    response = client.post(
        f"{BASE_URL}/news",
        json={
            "title": "Sample News",
            "tag": "Test Tag",
            "content": "This is a sample news content.",
            "publisher": "Test Publisher"
        }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json() == {"result": "Create News Successfully"}

def test_create_event(token):
    response = client.post(
        f"{BASE_URL}/event",
        json={
            "title": "Sample Event",
            "tag": "Test Event",
            "description": "This is a sample event description.",
            "start_time": "2024-10-28 10:00:00",
            "end_time": "2024-10-28 12:00:00",
            "place": "Sample Place",
            "publisher": "Test Publisher"
        }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json() == {"result": "Create Event Successfull"}

def test_create_news_invalid_data(token):
    response = client.post(
        f"{BASE_URL}/news",
        json={
            "title": "Sample News",
            "tag": "Test Tag",
            # Missing content field
            "publisher": "Test Publisher"
        }, headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 422

