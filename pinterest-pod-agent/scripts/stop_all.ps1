# Stop backend services started for this project.

$ProjectRoot = "c:\nanobot\pinterest-pod-agent"

Write-Host "Stopping project services..." -ForegroundColor Yellow

# Stop Celery workers/beat. This project does not share Celery processes with
# other local apps in the supported dev setup.
Get-Process -Name celery -ErrorAction SilentlyContinue | Stop-Process -Force

# Stop FastAPI only when it owns the project port.
$fastApiPids = Get-NetTCPConnection -LocalPort 8900 -ErrorAction SilentlyContinue |
    Select-Object -ExpandProperty OwningProcess -Unique
foreach ($processId in $fastApiPids) {
    if ($processId) {
        Stop-Process -Id $processId -Force
        Write-Host "  Stopped process on port 8900: $processId" -ForegroundColor Green
    }
}

Write-Host "Project services stopped for $ProjectRoot" -ForegroundColor Cyan
