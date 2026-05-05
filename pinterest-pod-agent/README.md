# nanobot - Pinterest 自动化运营系统

基于 AI 的 Pinterest 多账号自动化运营平台，支持内容生成、暖机养号、Pin 发布、趋势追踪和自动回复。

## 技术栈

- **后端**: FastAPI
- **任务队列**: Celery + Redis
- **数据库**: PostgreSQL
- **浏览器自动化**: Playwright + AdsPower
- **AI**: 多智能体内容生成（文案 + 图片 + 视频）

## 快速开始

### 1. 环境要求

- Python 3.11+
- PostgreSQL 数据库
- Redis
- [AdsPower](https://www.adspower.com/) 浏览器环境

### 2. 配置环境变量

复制 `.env.example` 为 `.env`，填写必要配置：

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
```

### 3. 安装依赖

```powershell
cd c:\nanobot\pinterest-pod-agent
..\.venv\Scripts\pip.exe install -r requirements.txt
playwright install chromium
```

### 4. 数据库迁移

```powershell
..\.venv\Scripts\alembic.exe upgrade head
```

### 5. 启动服务

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_all.ps1
```

停止服务：

```powershell
powershell -ExecutionPolicy Bypass -File scripts\stop_all.ps1
```

## 核心功能

| 功能 | 说明 |
|------|------|
| 内容生成 | AI 多智能体自动生成 Pin 标题、描述和图片 |
| 暖机养号 | 模拟真实用户浏览、搜索、滚动行为 |
| Pin 发布 | 自动创建和发布 Pin，支持图片和视频 |
| 趋势追踪 | 定期抓取 Pinterest 趋势关键词 |
| 自动回复 | 监控并自动回复评论 |
| 定时调度 | Celery Beat 驱动的任务调度系统 |
| 多账号管理 | Redis 锁防止账号并发冲突 |

## nanobot 常用指令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "检查服务健康状态"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "查看今天所有账号的任务状态"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "给 scope=pet_lovers 写入 Pinterest 趋势关键词"
powershell -ExecutionPolicy Bypass -File scripts\nanobot.ps1 "查看最近 4 小时失败任务"
```

详细文档见 [nanobot_调度与操作指南.md](nanobot_调度与操作指南.md)。
