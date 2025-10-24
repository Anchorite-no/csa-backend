# 🚀 CSA Backend

> **浙江大学学生网络空间安全协会后端服务**  
> *现代化、高性能、企业级的Python Web API服务*

[![Python](https://img.shields.io/badge/Python-3.8+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-green.svg)](https://fastapi.tiangolo.com)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://sqlalchemy.org)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## 🚀 快速开始

### 📋 环境要求
- **Python**: 3.8+ (推荐 3.11+)
- **操作系统**: Linux/macOS/Windows
- **内存**: 最低 2GB，推荐 4GB+

### 🔧 安装步骤

#### 1. 克隆项目
```bash
git clone https://github.com/zjucsa/csa-backend.git
cd csa-backend
```

#### 2. 创建虚拟环境
```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或
venv\Scripts\activate     # Windows
```

#### 3. 安装依赖
```bash
pip install -r requirements.txt
```

#### 4. 环境配置
创建 `.env` 文件：
```env
# 数据库配置
DB_PATH=sqlite:///data.sqlite

# 安全配置
CSA_SECRET_KEY=your-secret-key-here
CSA_SECRET_KEY_ADMIN=your-admin-secret-key-here

# 微信配置
WEIXIN_APP_ID=your-weixin-app-id
WEIXIN_APP_SECRET=your-weixin-app-secret

# 钉钉配置
DINGTALK_APPID=your-dingtalk-appid
DINGTALK_APPKEY=your-dingtalk-appkey
DINGTALK_SECRET=your-dingtalk-secret
DINGTALK_ENABLED=true
```

#### 5. 数据库初始化
```bash
# 运行数据库迁移
alembic upgrade head

# 或直接创建表（开发环境）
python -c "from models import Base, engine; Base.metadata.create_all(bind=engine)"
```

#### 6. 启动服务
```bash
# 开发环境
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 生产环境
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

#### 7. 访问服务
- **API文档**: http://localhost:8000/docs
- **ReDoc文档**: http://localhost:8000/redoc
- **健康检查**: http://localhost:8000/health

## 📁 项目结构

```
csa-backend/
├── 📁 models/                 # 数据模型
├── 📁 routes/                 # API路由
├── 📁 misc/                   # 工具模块
├── 📁 test/                   # 测试文件
├── 📁 uploads/                # 文件上传目录
├── 📄 main.py                 # 应用入口
├── 📄 config.py               # 配置管理
└── 📄 requirements.txt        # 依赖列表
```

## 📚 文档

详见仓库Wiki

- **[开发文档](DEVELOPMENT.md)** - 完整的开发指南
- **[API文档](API.md)** - 详细的API接口文档
- **[部署指南](DEPLOYMENT.md)** - 生产环境部署指南

## 🛠️ 技术栈

| 技术 | 版本 | 用途 |
|------|------|------|
| **FastAPI** | 0.115+ | Web框架 |
| **SQLAlchemy** | 2.0+ | ORM框架 |
| **Pydantic** | 2.10+ | 数据验证 |
| **Alembic** | 1.15+ | 数据库迁移 |
| **Uvicorn** | 0.34+ | ASGI服务器 |

## 🤝 贡献

我们欢迎各种形式的贡献！

1. **Fork** 项目
2. 创建功能分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 **Pull Request**

## 📄 许可证

本项目采用 [MIT License](LICENSE) 许可证。

<div align="center">


Made with ❤️ by [ZJU CSA Team](https://github.com/zjucsa)

</div>
