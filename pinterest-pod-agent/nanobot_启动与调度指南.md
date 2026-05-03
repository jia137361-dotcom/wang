# nanobot 启动与调度指南

## 版本信息

| 组件 | 版本 | 路径 |
|------|------|------|
| nanobot (智能体) | 0.1.5.post3 | `scripts/nanobot.ps1`（已内置 UTF-8 防乱码） |
| MCP Server | — | `c:\nanobot\pinterest-pod-agent\scripts\nanobot_mcp_server.py` |
| 项目后端 | — | `c:\nanobot\pinterest-pod-agent\` |

---

## 一、中文乱码处理（首次配置，之后无需重复）

如果终端中文显示乱码，按优先级选一个：

### 方案 B（推荐，只影响 nanobot 自己）

`scripts/nanobot.ps1` 已内置 `chcp 65001` + `PYTHONIOENCODING=utf-8`，用它替代裸调 nanobot.exe 即可，**不影响系统和其他项目**。

### 方案 A（临时）

每次开终端先 `chcp 65001`。

### 方案 C（永久，影响全局，谨慎）

会修改注册表和用户环境变量，**整个系统和所有 Python 项目都会变成 UTF-8**。大多数现代软件没问题，但老旧 GBK 程序可能乱码。

需要管理员权限：
```powershell
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-File c:\nanobot\pinterest-pod-agent\scripts\set_utf8.ps1'"
```

撤销：
```powershell
powershell -Command "Start-Process powershell -Verb RunAs -ArgumentList '-File c:\nanobot\pinterest-pod-agent\scripts\unset_utf8.ps1'"
```

---

## 二、前置检查

```powershell
chcp 65001

# 1. 确认 nanobot 可用
c:\nanobot\.venv\Scripts\nanobot.exe --version

# 2. 确认 MCP Server 能导入
c:\nanobot\.venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'c:\\nanobot\\pinterest-pod-agent'); from scripts.nanobot_mcp_server import mcp; print('MCP server OK, tools:', len(mcp._tools))"

# 3. 确认数据库连通
c:\nanobot\.venv\Scripts\python.exe -c "from app.database import get_sessionmaker; from sqlalchemy import text; db=get_sessionmaker()(); db.execute(text('SELECT 1')); print('DB OK'); db.close()"
```

---

## 二、一键启动项目后端

```powershell
powershell -File c:\nanobot\pinterest-pod-agent\scripts\start_all.ps1
```

这条命令同时启动 3 个服务（各自独立窗口）：
- FastAPI → `http://127.0.0.1:8900`
- Celery Worker → 监听 4 个队列 (publish / media / engagement / trend)
- Celery Beat → 定时调度 + stale 任务回收

停止所有服务：

```powershell
powershell -File c:\nanobot\pinterest-pod-agent\scripts\stop_all.ps1
```

---

## 三、启动 nanobot 并调度任务

### 3.1 一键全日运营

```powershell
powershell -File scripts/nanobot.ps1 "检查所有服务状态，确认每个账号的美国代理 IP 正常，然后为我今天的账号运营排任务"
```

nanobot 会自动执行：
1. `check_health` → 确认 PostgreSQL / Redis / AdsPower 都在线
2. `check_account_proxies` → 验证每个账号的 AdsPower profile 是美国 IP
3. `get_evo_keyword_signals` → 拉取高 CTR 关键词（内容决策依据）
4. `auto_schedule_daily` → 为每个账号创建今日任务：
   - warmup_and_publish（有可发内容时）或 standalone warmup
   - auto_reply（开启了自动回复的账号）
5. 汇报排期结果

### 3.2 常用调度指令

```powershell
# 查看所有账号今日状态
powershell -File scripts/nanobot.ps1 "看一下所有账号今天的任务完成情况"

# 查看某个账号的详细数据
powershell -File scripts/nanobot.ps1 "查账号 k1buvn6c 最近7天的曝光、点击和CTR"

# 给特定账号创建养号+发帖任务
powershell -File scripts/nanobot.ps1 "给账号 k1buvn6c 创建一次 warmup_and_publish，job_id 用 pj_abc123，养号10分钟"

# 紧急直接发帖（绕过正常调度）
powershell -File scripts/nanobot.ps1 "用 publish_pin_direct 工具发帖，account_id=k1buvn6c, job_id=pj_abc123, dry_run=false"

# 搜索趋势并写入策略表
powershell -File scripts/nanobot.ps1 "在网上搜一下 pet lovers 和 home decor 这两个 niche 最近在 Pinterest 上什么关键词火，把 top 20 写入 store_trend_signals"

# 生成商品图
powershell -File scripts/nanobot.ps1 "用 generate_image 生成一张图，prompt: 'cute dog mom t-shirt design, minimalist watercolor, Pinterest vertical pin'"

# 查看最近的错误
powershell -File scripts/nanobot.ps1 "看一下最近24小时哪些任务失败了，什么原因"

# 取消任务
powershell -File scripts/nanobot.ps1 "取消任务 st_abc123def456"

# 分析账号表现并给建议
powershell -File scripts/nanobot.ps1 "分析所有账号过去一周的 CTR，对比 EvoMap 关键词策略，给我优化建议"
```

---

## 四、完整运营流程

```
┌─ 用户指令 ─────────────────────────────────────────────────┐
│ "powershell -File scripts/nanobot.ps1 '开始今天的运营'"                          │
└────────────────────────────┬───────────────────────────────┘
                             │
                             ▼
┌─ nanobot 智能体（调度层） ─────────────────────────────────┐
│                                                            │
│  1. check_health           → PG ✅  Redis ✅  AdsPower ✅  │
│  2. check_account_proxies  → acc_001 US ✅  acc_002 US ✅ │
│  3. get_evo_keyword_signals → "dog lover" 3.2% CTR        │
│                            → "cat mom" 2.8% CTR           │
│  4. Web Search 搜趋势       → 汇总 top 20 关键词            │
│  5. store_trend_signals    → 写入 global_strategy         │
│  6. auto_schedule_daily    → 创建 4 warmup_and_publish    │
│                            → 创建 2 auto_reply            │
│  7. get_status_dashboard   → 汇报今日排期                  │
│                                                            │
└────────────────────────────┬──────────────────────────────┘
                             │ 任务写入 scheduled_task 表
                             ▼
┌─ Celery Beat + Dispatcher（调度执行层） ───────────────────┐
│                                                            │
│  每 N 分钟扫描 scheduled_task 表                            │
│  → 检查账号限速 (AccountPolicy)                             │
│  → 抢 DB 行锁 (FOR UPDATE SKIP LOCKED)                     │
│  → send_task 到对应队列                                    │
│                                                            │
└────────────────────────────┬──────────────────────────────┘
                             │ Celery 队列
                             ▼
┌─ Celery Worker（执行层） ─────────────────────────────────┐
│                                                            │
│  warmup_and_publish:                                       │
│    ├─ 获取 Redis 账号锁 + profile 锁                        │
│    ├─ 打开 AdsPower 浏览器（一次）                          │
│    ├─ 验证 US IP                                           │
│    ├─ 养号 5 分钟（搜索/浏览/互动）                         │
│    ├─ 同 page 发帖（不重新登录）                            │
│    ├─ EvoMap 记录 PinPerformance                           │
│    └─ 关闭浏览器                                           │
│                                                            │
│  auto_reply:                                               │
│    ├─ 打开浏览器 → 拉取未回复评论                           │
│    ├─ Volcengine LLM 生成回复文案                           │
│    ├─ 发布回复                                             │
│    └─ 关闭浏览器                                           │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 五、nanobot 通过 MCP 调用的 15 个工具

| 工具 | 做什么 |
|------|--------|
| `check_health` | 检查 PostgreSQL / Redis / AdsPower 连通性 |
| `check_account_proxies` | 验证每个账号的 AdsPower profile 是否美国 IP |
| `get_evo_keyword_signals` | 拉取高 CTR 关键词 + 权重 |
| `get_evo_strategy_advice` | LLM 生成的中文运营策略建议 |
| `get_account_analytics` | 账号维度曝光/点击/CTR/保存 |
| `auto_schedule_daily` | 一键为所有账号生成今日任务表 |
| `create_task` | 手动创建单个 scheduled_task |
| `list_tasks` | 按条件查看任务队列 |
| `cancel_task` | 取消 pending/scheduled 的任务 |
| `get_status_dashboard` | 今日各账号完成/运行/失败统计 |
| `get_task_detail` | 单个任务详情（payload + 错误） |
| `get_recent_errors` | 最近 N 小时的失败任务列表 |
| `store_trend_signals` | 将趋势关键词写入 global_strategy |
| `generate_image` | Fal.ai Flux 2 Pro 生图 |
| `publish_pin_direct` | 跳过调度，直接 Celery 发帖 |

---

## 六、排错

| 现象 | 检查 |
|------|------|
| nanobot 报 MCP 工具不可用 | MCP server 是否在 config.json 注册；python 路径是否正确 |
| 任务创建了但一直是 pending | Celery Worker + Beat 是否在运行；scheduled_at 是否在未来 |
| warmup_and_publish 失败 | AdsPower 是否在运行；profile 是否绑定；代理 IP 是否美国 |
| 评论回复不发 | `auto_reply_enabled` 在 AccountPolicy 中是否开启 |
| 任务卡在 running 不结束 | stale task 回收器每 10 分钟自动清理 >45 分钟无心跳的任务 |
