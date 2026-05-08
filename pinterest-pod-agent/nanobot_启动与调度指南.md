# nanobot 启动与调度指南

## 1. 组件关系

- PostgreSQL：长期保存账号、发布任务、调度任务、趋势、回复记录和表现数据。
- Redis：Celery 队列和账号/Profile 锁。Redis 不通时，任务不会被 Worker 正常消费。
- Celery Worker：真正执行生图、暖机、发布、自动回复、趋势刷新。
- Celery Beat：定时扫描任务并派发，也负责回收卡住的任务。
- AdsPower：提供每个账号的浏览器 Profile。
- nanobot：通过 MCP 工具创建任务、查询状态、触发调度。

## 2. 必要环境变量

写入 `c:\nanobot\pinterest-pod-agent\.env`：

```env
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/pinterest_pod
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
API_KEY=change-me
VOLC_API_KEY=change-me
FAL_KEY=change-me
ADSPOWER_BASE_URL=http://127.0.0.1:50325
SCHEDULER_ENABLED=true
SCHEDULER_DRY_RUN=false
SCHEDULER_AUTO_DISPATCH_ENABLED=false
PINTEREST_TRENDS_ENABLED=false
WARMUP_ENABLE_PIN_ENGAGEMENT=false
WARMUP_ENABLE_SAVE=false
```

说明：

- `SCHEDULER_DRY_RUN=false` 才会真实打开浏览器执行发布/回复。
- `SCHEDULER_AUTO_DISPATCH_ENABLED=false` 时，后台启动不会自动派发到期发布任务；需要 nanobot 或手动调用 `dispatch_ready_tasks` 才会执行。
- `WARMUP_ENABLE_PIN_ENGAGEMENT=false` 时，暖机只浏览、搜索、滚动，不点赞。
- `WARMUP_ENABLE_SAVE=false` 时，暖机不会保存 Pin。
- 新号建议保持两个暖机互动开关为 `false`。

## 3. 启动 Redis

如果使用 Docker：

```powershell
docker start nanobot-redis
```

如果容器还不存在：

```powershell
docker run -d --name nanobot-redis -p 6379:6379 redis:7
```

验证：

```powershell
cd c:\nanobot\pinterest-pod-agent
..\.venv\Scripts\python.exe -c "import redis; r=redis.from_url('redis://localhost:6379/0'); print(r.ping())"
```

输出 `True` 表示正常。

## 4. 初始化和迁移数据库

```powershell
cd c:\nanobot\pinterest-pod-agent
..\.venv\Scripts\alembic.exe upgrade head
```

## 5. 启动服务

```powershell
cd c:\nanobot\pinterest-pod-agent
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```

停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1
```
taskkill /f /im celery.exe
taskkill /f /im python.exe

健康检查：

```powershell
Invoke-RestMethod http://127.0.0.1:8900/health
..\.venv\Scripts\celery.exe -A app.celery_app inspect ping --timeout=5
```

## 6. nanobot 常用指令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "为账号 test-account-1 的发布任务 手动创建新 Job  并创建一个暖机加发布任务，暖机 5 分钟，立即执行"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "检查服务健康状态"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "查看今天所有账号的任务状态"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "检查所有账号的 AdsPower profile 状态"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "给 scope=pet_lovers 写入 Pinterest 趋势关键词 dog mom shirt, custom pet gift"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "查看最近 4 小时失败任务"
```

## 7. 什么时候浏览器会动

会打开 AdsPower 浏览器的任务：

- `warmup`
- `publish`
- `warmup_and_publish`
- `auto_reply`

不会打开浏览器的任务：

- `generate_image`
- `refresh_trends`
- `auto_schedule_daily`
- `list_tasks`
- `get_status_dashboard`

如果浏览器没反应，优先检查：

1. `SCHEDULER_DRY_RUN` 是否为 `false`
2. Redis 是否 `ping=True`
3. Celery Worker 是否能 `inspect ping`
4. AdsPower 是否打开，`ADSPOWER_BASE_URL` 是否正确
5. 账号是否绑定 `adspower_profile_id`
6. 任务是否已经失败，查看 `get_recent_errors`

如果一启动后台就自己跑任务，检查：

1. `SCHEDULER_AUTO_DISPATCH_ENABLED` 是否误设为 `true`
2. 数据库里是否有旧的 `pending` / `scheduled` 任务
3. 是否手动调用过 `dispatch_ready_tasks`

默认配置下，Celery Beat 只会回收卡住的任务，不会自动发帖。

## 8. 多账号建议

一个 nanobot/后端可以管理多个账号。系统通过 Redis 锁防止同一个账号或同一个 AdsPower Profile 并发执行。

建议并发：

- 2 核 4G：1-2 个并发浏览器
- 4 核 8G：3-5 个并发浏览器
- 8 核 16G：8-12 个并发浏览器

账号量继续扩大时，用多台服务器分片运行 Worker，并共享 PostgreSQL 和 Redis。

## 9. 启动后又自动执行任务的排查

`SCHEDULER_AUTO_DISPATCH_ENABLED=false` 时，Celery Beat 不会主动派发新的发布任务。如果刚启动仍然继续执行，通常是旧 Worker 没停干净，或者 Redis 队列里已经有启动前排进去的任务。

启动脚本现在默认会先停止旧的项目 FastAPI/Celery 进程，再启动新服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```

如果你明确不想启动前停止旧进程：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1 -NoStopExisting
```

查看 Celery 是否还有旧 Worker：

```powershell
..\.venv\Scripts\celery.exe -A app.celery_app inspect ping --timeout=5
..\.venv\Scripts\celery.exe -A app.celery_app inspect active --timeout=5
..\.venv\Scripts\celery.exe -A app.celery_app inspect reserved --timeout=5
```

查看最近失败和正在执行的任务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "查看最近 4 小时失败任务"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "查看今天所有账号的任务状态"
```

不要默认清空 Redis 队列。只有确认队列里都是误触发任务时，再单独执行清理。

## 10. 发布和暖机安全规则

- 发布时不再填写 `tagged topics`。
- 发布只操作当前 Pin 创建表单，不操作右侧 `Pin drafts` 草稿列表。
- 发布前会校验当前表单标题和描述是否属于本次任务；不匹配就停止并保存 debug 截图。
- 暖机只允许 Pinterest 站内浏览；如果点击后跳到 Amazon 或其他外站，会自动返回 Pinterest。
- `warmup_and_publish` 会先暖机，暖机结束后回到 Pinterest 首页，再打开 Pin 创建页发布新任务。
