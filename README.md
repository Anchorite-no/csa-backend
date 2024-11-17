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



### To Start

建议使用conda+pycharm集成开发。

Anaconda安装指南：[安装conda搭建python环境（保姆级教程）_conda创建python虚拟环境-CSDN博客](https://blog.csdn.net/2301_82000445/article/details/135703847?ops_request_misc=%7B%22request%5Fid%22%3A%22CCB6368E-0D6E-4F11-A337-A5DC1116A438%22%2C%22scm%22%3A%2220140713.130102334..%22%7D&request_id=CCB6368E-0D6E-4F11-A337-A5DC1116A438&biz_id=0&utm_medium=distribute.pc_search_result.none-task-blog-2~all~sobaiduend~default-2-135703847-null-null.142^v100^pc_search_result_base7&utm_term=conda安装指南&spm=1018.2226.3001.4187)

Pycharm安装指南：[PyCharm安装教程，图文教程(超详细)-CSDN博客](https://blog.csdn.net/SpringJavaMyBatis/article/details/137720715?ops_request_misc=%7B%22request%5Fid%22%3A%22194E085A-E74F-41B5-882C-DDC58E8C3048%22%2C%22scm%22%3A%2220140713.130102334..%22%7D&request_id=194E085A-E74F-41B5-882C-DDC58E8C3048&biz_id=0&utm_medium=distribute.pc_search_result.none-task-blog-2~all~sobaiduend~default-1-137720715-null-null.142^v100^pc_search_result_base7&utm_term=pycharm安装指南&spm=1018.2226.3001.4187)

Jetbrains面向在校学生提供免费软件服务，申请指南：[JetBrains 学生认证教程（Pycharm，IDEA… 等学生认证教程）_jetbrains学生认证-CSDN博客](https://blog.csdn.net/qq_36667170/article/details/79905198?ops_request_misc=%7B%22request%5Fid%22%3A%2269D20148-B7B6-43A6-A51F-9AE05993AD49%22%2C%22scm%22%3A%2220140713.130102334..%22%7D&request_id=69D20148-B7B6-43A6-A51F-9AE05993AD49&biz_id=0&utm_medium=distribute.pc_search_result.none-task-blog-2~all~sobaiduend~default-2-79905198-null-null.142^v100^pc_search_result_base7&utm_term=jetbrains学生认证登录&spm=1018.2226.3001.4187)

conda + pycharm集成开发：[pycharm 配置 conda 新环境_pycharm配置conda环境-CSDN博客](https://blog.csdn.net/qq_44886601/article/details/136006225?ops_request_misc=%7B%22request%5Fid%22%3A%2206B7B89A-ABA0-49D4-8610-C3B4FBE4B2CF%22%2C%22scm%22%3A%2220140713.130102334..%22%7D&request_id=06B7B89A-ABA0-49D4-8610-C3B4FBE4B2CF&biz_id=0&utm_medium=distribute.pc_search_result.none-task-blog-2~all~baidu_landing_v2~default-1-136006225-null-null.142^v100^pc_search_result_base7&utm_term=conda %2B pycharm&spm=1018.2226.3001.4187)
