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
