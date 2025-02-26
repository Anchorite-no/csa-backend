def create_admin():
    from misc.auth import hash_passwd
    from models.user import User
    from models.admin import Admin
    from models import get_db

    db = list(get_db())[0]
    has_user = db.query(User).count()
    if not has_user:
        passwd = hash_passwd("admin123")
        user = User(uid="00001", email="root@localhost", nick="管理员", passwd=passwd)
        admin = Admin(uid="00001", is_active=True, role_id=7)
        db.add(user)
        db.add(admin)
        db.commit()


def aid_to_nick(db, aid: str):
    from models.admin import Admin
    from models.user import User

    admin = db.query(Admin).filter(Admin.aid == aid).first()
    if not admin:
        return None
    
    user = db.query(User).filter(User.uid == admin.uid).first()
    if not user:
        return None
    
    return user.nick
