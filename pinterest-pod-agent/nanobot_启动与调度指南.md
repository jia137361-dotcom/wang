# nanobot 启动与调度指南

## 运行组件

- FastAPI 后端：`http://127.0.0.1:8900`
- Celery Worker：监听 `publish,media,engagement,trend`
- Celery Beat：周期调度任务和回收卡住的任务
- nanobot MCP Server：`scripts/nanobot_mcp_server.py`

## 环境变量

生产环境至少配置：

```env
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
REDIS_URL=redis://host:6379/0
CELERY_BROKER_URL=redis://host:6379/0
CELERY_RESULT_BACKEND=redis://host:6379/1
API_KEY=change-me
VOLC_API_KEY=change-me
FAL_KEY=change-me
PINTEREST_API_KEY=
PINTEREST_TRENDS_ENABLED=false
SCHEDULER_ENABLED=true
SCHEDULER_DRY_RUN=false
ADSPOWER_BASE_URL=http://local.adspower.net:50325
```

`SCHEDULER_DRY_RUN=false` 会允许真实发布任务执行。测试环境请显式设置为 `true`。

## 启动

```powershell
cd c:\nanobot\pinterest-pod-agent
powershell -File scripts\start_all.ps1
```

如果要 dry-run：

```powershell
$env:SCHEDULER_DRY_RUN = "true"
powershell -File scripts\start_all.ps1
```

## nanobot 常用指令

```powershell
powershell -File scripts\nanobot.ps1 "检查服务健康状态"
powershell -File scripts\nanobot.ps1 "查看今天所有账号的任务状态"
powershell -File scripts\nanobot.ps1 "检查所有账号的 AdsPower profile 状态"
powershell -File scripts\nanobot.ps1 "给 scope=pet_lovers 写入 Pinterest 趋势关键词 dog mom shirt, custom pet gift"
powershell -File scripts\nanobot.ps1 "触发 Pinterest 爆品趋势刷新，scope=pet_lovers, niche=pet lovers, product_type=t-shirt"
powershell -File scripts\nanobot.ps1 "查看最近 4 小时失败任务"
```

## MCP 工具

主要工具：

- `check_health`
- `check_account_proxies`
- `get_status_dashboard`
- `list_tasks`
- `get_task_detail`
- `get_recent_errors`
- `store_trend_signals`
- `get_trend_snapshot`
- `refresh_pinterest_trends`
- `generate_image`
- `create_publish_task`
- `dispatch_ready_tasks`
- `auto_schedule_daily`
- `publish_pin_direct`

`publish_pin_direct` 保持安全默认，只做 dry-run。真实发布请创建任务后调用 `dispatch_ready_tasks(dry_run=false)`。

## 多账号运行

一个 nanobot/后端可以管理多个账号。系统通过 Redis account lock 和 AdsPower profile lock 防止同一账号或同一 profile 并发执行。

建议按机器资源限制并发浏览器数量：

- 2 核 4G：1-2 个并发浏览器
- 4 核 8G：3-5 个并发浏览器
- 8 核 16G：8-12 个并发浏览器

账号量继续扩大时，使用多台服务器分片运行 Worker，并共享 PostgreSQL 与 Redis。
