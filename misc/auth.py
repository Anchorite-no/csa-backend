import time
from datetime import timedelta

from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError
from sqlalchemy.orm import Session

import bcrypt

from config import get_secret_key, get_secret_key_admin


SECRET_KEY = get_secret_key()
SECRET_KEY_ADMIN = get_secret_key_admin()
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/user/token")
credentials_exception = HTTPException(
    status_code=401,
    detail="验证用户失败，请重新登录",
    headers={"WWW-Authenticate": "Bearer"},
)
credentials_exception_admin = HTTPException(
    status_code=401,
    detail="验证管理员失败，请重新登录",
    headers={"WWW-Authenticate": "Bearer"},
)
permission_exception = HTTPException(
    status_code=403,
    detail="您没有权限访问此资源",
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

def create_access_token_admin(
        uid: str, aid: int, expires_delta: timedelta = timedelta(hours=1), **extra_data
) -> str:
    to_encode = extra_data.copy()
    expire = int(time.time()) + expires_delta.total_seconds()

    to_encode.update({"uid": uid})
    to_encode.update({"aid": aid})
    to_encode.update({"exp": expire})

    print(to_encode)

    encoded_jwt = jwt.encode(to_encode, SECRET_KEY_ADMIN, algorithm=ALGORITHM)
    print(encoded_jwt)
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


async def get_current_user_flexible(token: str = Depends(oauth2_scheme)):
    """
    灵活的用户验证：同时支持普通用户token和管理员token
    优先尝试管理员token，失败则尝试普通用户token
    """
    # 先尝试管理员token
    try:
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=[ALGORITHM])
        uid = payload.get("uid")
        if uid:
            return uid
    except JWTError:
        pass
    
    # 尝试普通用户token
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)
        uid = payload.get("uid")
        if uid:
            return uid
    except JWTError:
        pass
    
    # 两种token都失败
    raise credentials_exception

async def get_current_admin(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=[ALGORITHM])
        
        uid: str = payload.get("uid")
        aid: int = payload.get("aid")
        # exp: datetime = datetime.fromtimestamp(payload.get("exp"))
        
        if not uid or not aid:
            raise credentials_exception_admin
        
    except JWTError:
        raise credentials_exception
    
    return aid

async def get_current_admin_uid(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=ALGORITHM)
        uid = payload.get("uid")
        aid = payload.get("aid")

        if not uid:
            raise credentials_exception

        if not aid:
            raise credentials_exception_admin

    except JWTError:
        raise credentials_exception

    return uid


async def login_required(token: str = Depends(oauth2_scheme)):
    try:
        jwt.decode(token, SECRET_KEY, algorithms=ALGORITHM)

    except JWTError:
        raise credentials_exception

    return True

async def login_required_admin(token: str = Depends(oauth2_scheme)):
    
    # return True

    try:
        jwt.decode(token, SECRET_KEY_ADMIN, algorithms=ALGORITHM)

    except JWTError:
        raise credentials_exception

    return True


async def get_current_user_role(token: str = Depends(oauth2_scheme)):
    """获取当前用户的管理员角色ID，如果不是管理员返回None"""
    from models import get_db
    from models.admin import Admin
    
    try:
        # 先尝试解码管理员token
        payload = jwt.decode(token, SECRET_KEY_ADMIN, algorithms=[ALGORITHM])
        aid = payload.get("aid")
        
        if aid:
            # 获取数据库会话
            db = next(get_db())
            try:
                admin = db.query(Admin).filter_by(aid=aid).first()
                if admin and admin.is_active:
                    return admin.role_id
            finally:
                db.close()
    except JWTError:
        pass
    
    return None


async def login_required_manager(token: str = Depends(oauth2_scheme)):
    """只允许管理员（rid=7）访问"""
    role_id = await get_current_user_role(token)
    
    if role_id != 7:
        raise permission_exception
    
    return True


async def login_required_operator(token: str = Depends(oauth2_scheme)):
    """允许管理员（rid=7）和运维（rid=9）访问"""
    role_id = await get_current_user_role(token)
    
    if role_id not in [7, 9]:
        raise permission_exception
    
    return True


async def login_required_publisher(token: str = Depends(oauth2_scheme)):
    """允许管理员（rid=7）、运维（rid=9）和发布者（rid=8）访问"""
    role_id = await get_current_user_role(token)
    
    if role_id not in [7, 8, 9]:
        raise permission_exception
    
    return True


def hash_passwd(passwd: str) -> str:
    pwd_bytes = passwd.encode("utf-8")
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(password=pwd_bytes, salt=salt)
    return hashed_password.decode('utf-8')


def verify_passwd(plain: str, hashed: bytes) -> bool:
    plain = plain.encode("utf-8")
    return bcrypt.checkpw(password=plain, hashed_password=hashed)
