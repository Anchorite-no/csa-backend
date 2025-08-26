import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from main import app
from models import Base, get_db
from models.recruit import Recruitment
from datetime import datetime

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

BASE_URL = "/api/recruit"

client = TestClient(app)

@pytest.fixture(scope="module")
def setup_database():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

def get_test_token():
    # 注册测试用户
    response = client.post(f"/api/user/register", json={
        "uid": "1234567890",
        "nick": "TestUser",
        "passwd": "testpassword",
        "email": "testuser@example.com"
    })
    assert response.status_code == 200

    # 登录获取token
    response = client.post(f"/api/user/login", json={
        "uid": "1234567890",
        "passwd": "testpassword"
    })
    assert response.status_code == 200
    return response.json()["access_token"]

def get_admin_token():
    # 管理员登录
    import hashlib
    admin_passwd = hashlib.sha256("admin123".encode("utf-8")).hexdigest()
    response = client.post(f"/api/user/login/admin", json={
        "uid": "00001",  # 使用misc/model.py中创建的管理员uid
        "passwd": admin_passwd
    })
    assert response.status_code == 200
    return response.json()["access_token"]

@pytest.fixture(scope="module")
def token(setup_database):
    return get_test_token()

@pytest.fixture(scope="module")
def admin_token(setup_database):
    return get_admin_token()

def test_major_search():
    """测试专业搜索功能"""
    response = client.post(f"{BASE_URL}/major_search", json={
        "major_name": "计算机",
        "grade": 24
    })
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_major_confirm():
    """测试专业确认功能"""
    response = client.post(f"{BASE_URL}/major_confirm", json={
        "major_name": "计算机科学与技术",
        "grade": 24
    })
    assert response.status_code == 200
    assert isinstance(response.json(), list)

def test_recruit_confirm(token):
    """测试纳新信息提交"""
    recruit_data = {
        "name": "张三",
        "render": False,  # 男
        "uid": "2024001",
        "major_id": "080901",
        "major_name": "计算机科学与技术",
        "college_id": "08",
        "college_name": "计算机学院",
        "degree": 0,  # 学士
        "grade": 24,
        "phone": "13800138000",
        "office_department_willing": 1,
        "competition_department_willing": 2,
        "activity_department_willing": 3,
        "research_department_willing": 4,
        "if_agree_to_be_reassigned": True,
        "if_be_member": True,
        "introduction": "我是一名计算机专业的学生，对编程有浓厚的兴趣，希望能在CSA中学习更多知识。",
        "skill": "Python, Java, 数据结构与算法"
    }
    
    response = client.post(f"{BASE_URL}/recruit_confirm", json=recruit_data)
    assert response.status_code == 200
    assert response.json()["message"] == "Recruit information submitted successfully"

def test_recruit_confirm_duplicate_uid(token):
    """测试重复学号提交"""
    recruit_data = {
        "name": "李四",
        "render": True,  # 女
        "uid": "2024001",  # 重复的学号
        "major_id": "080901",
        "major_name": "计算机科学与技术",
        "college_id": "08",
        "college_name": "计算机学院",
        "degree": 0,
        "grade": 24,
        "phone": "13800138001",
        "office_department_willing": 2,
        "competition_department_willing": 1,
        "activity_department_willing": 4,
        "research_department_willing": 3,
        "if_agree_to_be_reassigned": False,
        "if_be_member": True,
        "introduction": "我是李四，对竞赛很感兴趣。",
        "skill": "C++, 算法竞赛"
    }
    
    response = client.post(f"{BASE_URL}/recruit_confirm", json=recruit_data)
    assert response.status_code == 400
    assert "该学号已提交过报名信息" in response.json()["detail"]

def test_add_test_recruits():
    """添加更多测试数据"""
    test_recruits = [
        {
            "name": "王五",
            "render": False,
            "uid": "2024002",
            "major_id": "080901",
            "major_name": "计算机科学与技术",
            "college_id": "08",
            "college_name": "计算机学院",
            "degree": 1,  # 硕士
            "grade": 23,
            "phone": "13800138002",
            "office_department_willing": 3,
            "competition_department_willing": 1,
            "activity_department_willing": 2,
            "research_department_willing": 4,
            "if_agree_to_be_reassigned": True,
            "if_be_member": True,
            "introduction": "我是王五，硕士在读，研究方向是人工智能。",
            "skill": "机器学习, 深度学习, Python"
        },
        {
            "name": "赵六",
            "render": True,
            "uid": "2024003",
            "major_id": "080901",
            "major_name": "计算机科学与技术",
            "college_id": "08",
            "college_name": "计算机学院",
            "degree": 0,
            "grade": 24,
            "phone": "13800138003",
            "office_department_willing": 4,
            "competition_department_willing": 3,
            "activity_department_willing": 1,
            "research_department_willing": 2,
            "if_agree_to_be_reassigned": False,
            "if_be_member": True,
            "introduction": "我是赵六，喜欢组织活动，有丰富的社团经验。",
            "skill": "活动策划, 团队协作, 沟通能力"
        },
        {
            "name": "孙七",
            "render": False,
            "uid": "2024004",
            "major_id": "080901",
            "major_name": "计算机科学与技术",
            "college_id": "08",
            "college_name": "计算机学院",
            "degree": 2,  # 博士
            "grade": 22,
            "phone": "13800138004",
            "office_department_willing": 2,
            "competition_department_willing": 4,
            "activity_department_willing": 3,
            "research_department_willing": 1,
            "if_agree_to_be_reassigned": True,
            "if_be_member": True,
            "introduction": "我是孙七，博士在读，专注于科研工作。",
            "skill": "学术研究, 论文写作, 数据分析"
        }
    ]
    
    for recruit_data in test_recruits:
        response = client.post(f"{BASE_URL}/recruit_confirm", json=recruit_data)
        assert response.status_code == 200

def test_admin_get_recruits(admin_token):
    """测试管理员获取纳新者列表"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/recruits", headers=headers, params={
        "page": 1,
        "size": 10
    })
    assert response.status_code == 200
    data = response.json()
    assert "recruits" in data
    assert "total" in data
    assert isinstance(data["recruits"], list)
    assert isinstance(data["total"], int)

def test_admin_add_evaluation(admin_token):
    """测试管理员添加评价"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/api/admin/add_evaluation", 
                          headers=headers,
                          json={
                              "uid": "2024001",
                              "comment": "表现优秀，技术基础扎实",
                              "department": "技术部"
                          })
    assert response.status_code == 200
    assert "评价添加成功" in response.json()["message"]

def test_admin_get_evaluations(admin_token):
    """测试管理员获取评价列表"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/evaluations/2024001", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "evaluations" in data
    assert "total" in data
    assert isinstance(data["evaluations"], list)



def test_admin_assign_department(admin_token):
    """测试管理员分配部门"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/api/admin/assign_department", 
                          headers=headers,
                          json={
                              "uid": "2024001",
                              "department": "office"
                          })
    assert response.status_code == 200
    assert "部门分配成功" in response.json()["message"]

def test_admin_assign_department_invalid_uid(admin_token):
    """测试分配部门时无效的学号"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.post("/api/admin/assign_department", 
                          headers=headers,
                          json={
                              "uid": "9999999",
                              "department": "office"
                          })
    assert response.status_code == 404
    assert "纳新者未找到" in response.json()["detail"]

def test_admin_export_recruits(admin_token):
    """测试管理员导出纳新者数据"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/export_recruits", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "attachment" in response.headers["content-disposition"]

def test_admin_export_recruits_csv(admin_token):
    """测试管理员导出纳新者数据为CSV格式"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/export_recruits?export_format=csv", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"] == "text/csv"
    assert "attachment" in response.headers["content-disposition"]

def test_admin_get_recruits_with_filters(admin_token):
    """测试带筛选条件的纳新者列表"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = client.get("/api/admin/recruits", headers=headers, params={
        "page": 1,
        "size": 5,
        "name": "张",
        "degree": "0",
        "grade": "24",
        "status": "accepted"
    })
    assert response.status_code == 200
    data = response.json()
    assert "recruits" in data
    assert "total" in data

if __name__ == "__main__":
    # 运行测试
    pytest.main([__file__, "-v"])
