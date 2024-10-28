from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from models.user import User
from models import get_db

def clear_database_except_admin(db: Session = Depends(get_db)):
    try:
        db.query(User).filter(User.uid != 'admin').delete(synchronize_session=False)
        db.commit()
        print("Database Init Successfully")
    except Exception as e:
        db.rollback()
        print(f"Unexpected failure, Rolling back {str(e)}")

# 运行脚本的主函数
if __name__ == "__main__":
    clear_database_except_admin()
