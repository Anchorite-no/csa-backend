import pytest
import requests

BASE_URL = "http://localhost:8000/api/user"
UID = "3220105108"
EMAIL = f"{UID}@zju.edu.cn"
@pytest.fixture
def base_url():
    return BASE_URL

@pytest.fixture
def register_user():
    """Fixture to register a user."""
    url = f"{BASE_URL}/register"
    payload = {
        "uid": UID,
        "nick": "Test User",
        "passwd": "testpassword123",
        "email": EMAIL
    }
    response = requests.post(url, json=payload)
    return response

def test_clear_database_except_admin():
    response = requests.post(f"{BASE_URL}/clear")
    assert response.status_code == 200
    assert response.json() == {"result": "Database Init Done"}

def test_register_user(register_user):
    """Test to register a new user."""
    response = register_user
    assert response.status_code == 200, f"Failed to register user: {response.json()}"

def test_duplicate_registration():
    """Test registering a user with the same UID again."""
    url = f"{BASE_URL}/register"
    payload = {
        "uid": UID,
        "nick": "Test User Duplicate",
        "passwd": "testpassword123",
        "email": EMAIL
    }
    response = requests.post(url, json=payload)
    assert response.status_code == 400, f"Duplicate registration error: {response.json()}"

def test_login_user():
    """Test logging in with the registered user."""
    url = f"{BASE_URL}/login"
    payload = {
        "uid": UID,
        "password": "testpassword123"
    }
    response = requests.post(url, json=payload)
    assert response.status_code == 200, f"Failed to login user: {response.json()}"
    token = response.json().get("access_token")
    return token

def test_wrong_password_login():
    """Test logging in with an incorrect password."""
    url = f"{BASE_URL}/login"
    payload = {
        "uid": UID,
        "password": "wrongpassword"
    }
    response = requests.post(url, json=payload)
    assert response.status_code == 400, f"Allowed login with wrong password: {response.json()}"

def test_change_password():
    """Test changing the password of a user."""
    token = test_login_user()  # Log in to get the token
    url = f"{BASE_URL}/passwd"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    payload = {
        "old": "testpassword123",
        "new": "newtestpassword456"
    }
    response = requests.post(url, json=payload, headers=headers)
    assert response.status_code == 200, f"Failed to change password: {response.json()}"

def test_login_with_old_password():
    """Test logging in with the old password after changing it."""
    url = f"{BASE_URL}/login"
    payload = {
        "uid": UID,
        "password": "testpassword123"
    }
    response = requests.post(url, json=payload)
    assert response.status_code == 400, f"Old password still valid after change: {response.json()}"

def test_login_with_new_password():
    """Test logging in with the new password."""
    url = f"{BASE_URL}/login"
    payload = {
        "uid": UID,
        "password": "newtestpassword456"
    }
    response = requests.post(url, json=payload)
    assert response.status_code == 200, f"Failed to login with new password: {response.json()}"

