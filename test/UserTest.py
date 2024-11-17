import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import Base, get_db
from main import app
import requests

BASE_URL = "http://127.0.0.1:8000/api/user"
VALID_UID1 = "3220100100"
VALID_UID2 = "3220100101"
VALID_UID3 = "3220100102"
VALID_UID4 = "3220100103"
NONEXISTENCE_UID = "3220100109"

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

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def test_register(setup_database):
    response = client.post(f"{BASE_URL}/register", json={
        "uid": VALID_UID1,
        "nick": "TestUser",
        "passwd": "testpassword",
        "email": "testuser@example.com"
    })
    assert response.status_code == 200
    assert response.json()["access_token"] is not None

def test_register_duplicate_user():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": VALID_UID1,
        "nick": "TestUser",
        "passwd": "testpassword",
        "email": "testuser@example.com"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "用户已存在"

def test_register_duplicate_email():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": VALID_UID2,
        "nick": "TestUser2",
        "passwd": "testpassword",
        "email": "testuser@example.com"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "邮箱已被注册"

def test_login_correct_password():
    response = client.post(f"{BASE_URL}/login", json={
        "uid": VALID_UID1,
        "passwd": "testpassword",
    })
    assert response.status_code == 200

def test_login_wrong_password():
    response = client.post(f"{BASE_URL}/login", json={
        "uid": VALID_UID1,
        "passwd": "wrongpassword"
    })
    assert response.status_code == 400

def test_login_nonexistent_user():
    response = client.post(f"{BASE_URL}/login", json={
        "uid": NONEXISTENCE_UID,
        "passwd": "testpassword"
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "用户未找到"

def test_change_password_unauthorized():
    response = client.post(f"{BASE_URL}/passwd", json={
        "old": "testpassword",
        "new": "newpassword"
    })
    assert response.status_code == 401

def test_register_missing_fields():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": VALID_UID3,
    })
    assert response.status_code == 422

def test_register_invalid_email_format_1():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": VALID_UID4,
        "nick": "TestUser4",
        "passwd": "testpassword",
        "email": "invalid-email-format"
    })
    assert response.status_code == 422

def test_login_empty_password():
    response = client.post(f"{BASE_URL}/login", json={
        "uid": "testuser",
        "passwd": ""
    })
    assert response.status_code == 422

# ----------Unexpected Chars-----------

def test_login_special_characters():
    response = client.post(f"{BASE_URL}/login", json={
        "uid": "<script>alert('XSS')</script>",
        "passwd": "password"
    })
    assert response.status_code == 422

def test_register_reuse_old_password():
    token = get_test_token()
    response = client.post(f"{BASE_URL}/passwd", json={
        "old": "testpassword",
        "new": "testpassword"
    }, headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401

def test_register_uid_non_digit():
    # 测试 uid 包含非数字字符
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "abc123",
        "nick": "ValidNick",
        "passwd": "ValidPasswd",
        "email": "valid@example.com"
    })
    assert response.status_code == 422

# ----------Unexpected Uid-----------

def test_register_uid_only_digits():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "ValidNick",
        "passwd": "ValidPasswd",
        "email": "valid@example.com"
    })
    assert response.status_code == 200

def test_register_uid_empty():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "",
        "nick": "ValidNick",
        "passwd": "ValidPasswd",
        "email": "valid@example.com"
    })
    assert response.status_code == 422


def test_register_nick_invalid_characters():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "Invalid@Nick",
        "passwd": "ValidPasswd",
        "email": "valid@example.com"
    })
    assert response.status_code == 422

# ----------Unexpected Nick-----------

def test_register_nick_too_short():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "ab",
        "passwd": "ValidPasswd",
        "email": "valid@example.com"
    })
    assert response.status_code == 422

def test_register_nick_valid():
    # 测试合法的 nick
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "12345678",
        "nick": "Valid_Nick-123",
        "passwd": "ValidPasswd",
        "email": "valid78@example.com"
    })
    assert response.status_code == 200

# ----------Unexpected Passwd-----------

def test_register_passwd_invalid_characters():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "ValidNick",
        "passwd": "Invalid!Pass",
        "email": "valid@example.com"
    })
    assert response.status_code == 422

def test_register_passwd_too_short():
    # 测试 passwd 过短
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "ValidNick",
        "passwd": "ab",
        "email": "valid@example.com"
    })
    assert response.status_code == 422

def test_register_passwd_valid():
    # 测试合法的 passwd
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "12345689",
        "nick": "ValidNick",
        "passwd": "Valid_Pass-123",
        "email": "valid89@example.com"
    })
    assert response.status_code == 200

# ----------Unexpected Email-----------

def test_register_invalid_email_format():

    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "ValidNick",
        "passwd": "ValidPasswd",
        "email": "invalid-email"
    })
    assert response.status_code == 422

def test_register_empty_email():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "123456",
        "nick": "ValidNick",
        "passwd": "ValidPasswd",
        "email": ""
    })
    assert response.status_code == 422

def test_register_valid_email():
    response = client.post(f"{BASE_URL}/register", json={
        "uid": "1234568910",
        "nick": "ValidNick",
        "passwd": "ValidPasswd",
        "email": "valid910@example.com"
    })
    assert response.status_code == 200

def get_test_token():
    response = client.post(f"{BASE_URL}/login", json={
        "uid": VALID_UID1,
        "passwd": "testpassword"
    })
    assert response.status_code == 200
    return response.json()["access_token"]

