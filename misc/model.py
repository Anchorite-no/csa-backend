def create_admin():
    from misc.auth import hash_passwd
    from hashlib import sha256
    from models.user import User
    from models.admin import Admin
    from models import get_db
    from config import get_config
    db = list(get_db())[0]
    has_user = db.query(User).count()

    admin_password = get_config("ADMIN_PASSWORD")
    passwd = sha256(admin_password.encode("utf-8")).hexdigest()
    passwd = hash_passwd(passwd)
    create_test_users()
    if not has_user:
        user = User(uid="00001", email="root@localhost", nick="管理员", passwd=passwd, role_id=1)
        admin = Admin(uid="00001", is_active=True, role_id=7)
        db.add(user)
        db.add(admin)
        db.commit()
    else:
        user = db.query(User).filter_by(uid="00001").first()
        if passwd != user.passwd:
            user.passwd = passwd
            db.commit()


def aid_to_nick(db, aid: str):
    from models.admin import Admin
    from models.user import User

    admin = db.query(Admin).filter_by(aid=aid).first()
    if not admin:
        return None
    
    user = db.query(User).filter_by(uid=admin.uid).first()
    if not user:
        return None
    
    return user.nick


def create_test_users():
    """创建测试账号（用于开发测试）"""
    from misc.auth import hash_passwd
    from hashlib import sha256
    from models.user import User
    from models.admin import Admin
    from models import get_db

    db = list(get_db())[0]
    
    # 测试账号配置
    test_users = [
        {
            "uid": "10001",
            "nick": "测试发布者",
            "email": "publisher@test.com",
            "passwd": "123456",
            "admin_rid": 8,  # 发布者
        },
        {
            "uid": "10002",
            "nick": "测试运维",
            "email": "operator@test.com",
            "passwd": "123456",
            "admin_rid": 9,  # 运维
        },
        {
            "uid": "10003",
            "nick": "测试普通用户",
            "email": "normal@test.com",
            "passwd": "123456",
            "admin_rid": None,  # 普通用户
        },
    ]

    
    for user_data in test_users:
        uid = user_data["uid"]
        nick = user_data["nick"]
        email = user_data["email"]
        passwd = user_data["passwd"]
        admin_rid = user_data.get("admin_rid")
        
        # 检查用户是否已存在
        existing_user = db.query(User).filter_by(uid=uid).first()
        if existing_user:
            # 更新密码（确保密码正确）
            sha256_passwd = sha256(passwd.encode("utf-8")).hexdigest()
            hashed_passwd = hash_passwd(sha256_passwd)
            existing_user.passwd = hashed_passwd
            existing_user.nick = nick
            existing_user.email = email
            
            # 处理管理员权限
            existing_admin = db.query(Admin).filter_by(uid=uid).first()
            if admin_rid and not existing_admin:
                new_admin = Admin(uid=uid, role_id=admin_rid, is_active=True)
                db.add(new_admin)
            elif admin_rid and existing_admin:
                existing_admin.role_id = admin_rid
                existing_admin.is_active = True
            elif not admin_rid and existing_admin:
                db.delete(existing_admin)
            
            db.commit()
            print(f"✓ 更新测试用户: {uid} ({nick})")
            continue
        
        # 创建新用户
        sha256_passwd = sha256(passwd.encode("utf-8")).hexdigest()
        hashed_passwd = hash_passwd(sha256_passwd)
        new_user = User(
            uid=uid,
            nick=nick,
            email=email,
            passwd=hashed_passwd,
            role_id=1,
        )
        db.add(new_user)
        
        # 如果需要，创建管理员记录
        if admin_rid:
            new_admin = Admin(uid=uid, role_id=admin_rid, is_active=True)
            db.add(new_admin)
        
        db.commit()
        print(f"✓ 创建测试用户: {uid} ({nick})")
