# CSA Backend

浙江大学学生网络空间安全协会后端服务

## 功能特性

- 用户管理
- 活动管理
- 新闻管理
- 招新报名
- PDF简历上传

## 简历上传功能

### 安全特性
- 文件类型验证：只允许PDF格式
- 文件大小限制：最大10MB
- 文件内容验证：检查PDF文件头
- 文件名安全：使用学号的SHA256哈希作为文件名
- 访问控制：只有已提交报名信息的用户才能上传简历

### 存储位置
- 文件存储在 `uploads/resumes/` 目录下
- 文件名格式：`{uid_sha256}.pdf`

### API端点
- `POST /api/recruit/upload_resume`
- 参数：
  - `uid`: 学号
  - `resume_file`: PDF文件

## 安装和运行

1. 安装依赖：
```bash
pip install -r requirements.txt
```

2. 运行服务：
```bash
python -m uvicorn main:app --reload --port 8000
```

## 环境要求

- Python 3.8+
- FastAPI
- SQLAlchemy
- 其他依赖见 requirements.txt
