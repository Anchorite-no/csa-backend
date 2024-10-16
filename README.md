# csa-backend

浙江大学学生网络空间安全协会官网 后端

### Tips

1、建议使用集成开发环境进行调试。若要直接在 Shell 调试，请使用 `uvicorn main:app`

2、修改数据库后请使用 alembic 进行迁移，具体步骤为

```shell
alembic revision --autogenerate -m "commit信息"
alembic upgrade head
```

    特别的，如果增加了新的数据表，请在 `alembic/env.py` 中 import。

### TODO

- 会员的数据库设计

- 用户管理、会员管理的接口


