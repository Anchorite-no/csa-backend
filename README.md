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

### Catagory 定义

#### event 的 category

1 培训信息 2 科研信息

#### news 的 category

1 新闻 2 通知公告 3 网安知识 4 战队信息 5 赛事信息

### TODO

- 会员的数据库设计

- 会员管理的接口

### 11.17 TODO

- 数据库设计: 权限表，用户角色与权限表的关联
- 管理员操作设计: 更改用户信息（不是角色）
- 新增文件的测试，包括`route/user.py`中新增的方法，`route/admin.py`, `route/event.py`
  - 即扩展`test/UserTest`, 设计`test/AdminTest` `test/UserEventTest`


