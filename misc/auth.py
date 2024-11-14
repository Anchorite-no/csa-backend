import time
from datetime import timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt

from config import get_secret_key


SECRET_KEY = get_secret_key()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30


oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/user/token")
credentials_exception = HTTPException(
    status_code=401,
    detail="无法验证用户信息",
    headers={"WWW-Authenticate": "Bearer"},
)


def create_access_token(
    uid: str, expires_delta: timedelta = timedelta(hours=1), **extra_data
) -> str:
    to_encode = extra_data.copy()
    expire = int(time.time()) + expires_delta.total_seconds()

    to_encode.update({"uid": uid})
    to_encode.update({"exp": expire})

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

    return encoded_jwt


async def get_current_user(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        uid = payload.get("uid")

        if not uid:
            raise credentials_exception

    except JWTError:
        raise credentials_exception

    return uid


async def login_required(token: str = Depends(oauth2_scheme)):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)

    except JWTError:
        raise credentials_exception

    return True


def hash_passwd(passwd: str) -> str:
    pwd_bytes = passwd.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password


def verify_passwd(plain: str, hashed: str) -> bool:
    plain = plain.encode("utf-8")
    hashed = hashed.encode("utf-8")
    return bcrypt.checkpw(password=plain, hashed_password=hashed)
