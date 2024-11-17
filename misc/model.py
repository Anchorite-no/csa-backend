def create_admin():
    from hashlib import sha256
    from misc.auth import hash_passwd
    from models.user import User
    from models.admin import Admin
    from models import get_db

    db = list(get_db())[0]
    has_user = db.query(User).count()
    if not has_user:
        passwd = hash_passwd(sha256("admin".encode("utf-8")).hexdigest())
        user = User(uid="admin", email="root@localhost", nick="管理员", passwd=passwd)
        admin = Admin(uid="admin", is_active=True, role_id=7)
        db.add(user)
        db.add(admin)
        db.commit()


