# 一键启动 Pinterest POD Agent 全部后端服务
# 用法: powershell -File scripts\start_all.ps1

$ProjectRoot = "c:\nanobot\pinterest-pod-agent"
$VenvRoot   = "c:\nanobot\.venv"

# Ensure scheduler is enabled (regardless of .env default)
$env:SCHEDULER_ENABLED = "true"
$env:SCHEDULER_DRY_RUN = "false"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Pinterest POD Agent - 全部启动" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# -- FastAPI --------------------------------------------------
Write-Host "[1/3] 启动 FastAPI (端口 8900)..." -ForegroundColor Green
Start-Process -FilePath "$VenvRoot\Scripts\python.exe" `
    -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8900" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Normal

# -- Celery Worker --------------------------------------------
Write-Host "[2/3] 启动 Celery Worker..." -ForegroundColor Green
Start-Process -FilePath "$VenvRoot\Scripts\celery.exe" `
    -ArgumentList "-A app.celery_app worker -Q publish,media,engagement,trend --loglevel=info --concurrency=2 --pool=solo" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Normal

# -- Celery Beat ----------------------------------------------
Write-Host "[3/3] 启动 Celery Beat..." -ForegroundColor Green
Start-Process -FilePath "$VenvRoot\Scripts\celery.exe" `
    -ArgumentList "-A app.celery_app beat --loglevel=info" `
    -WorkingDirectory $ProjectRoot `
    -WindowStyle Normal

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  3 个服务已在独立窗口中启动" -ForegroundColor Cyan
Write-Host "  FastAPI       → http://127.0.0.1:8900" -ForegroundColor Yellow
Write-Host "  Celery Worker → 4 队列 (publish/media/engagement/trend)" -ForegroundColor Yellow
Write-Host "  Celery Beat   → 定时调度 + stale 回收" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "下一步: nanobot agent -m '开始今天的运营'" -ForegroundColor Magenta
