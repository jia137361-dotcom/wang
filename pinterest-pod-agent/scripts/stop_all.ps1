# 停止本项目启动的后端服务

$ProjectRoot = "c:\nanobot\pinterest-pod-agent"

Write-Host "正在停止本项目服务..." -ForegroundColor Yellow

# 精确匹配：只杀命令行中包含本项目路径的进程
$targets = @(
    @{Name="python"; Pattern="uvicorn"},
    @{Name="celery"; Pattern=$ProjectRoot}
)

foreach ($t in $targets) {
    $procs = Get-Process -Name $t.Name -ErrorAction SilentlyContinue | Where-Object {
        $_.CommandLine -match $t.Pattern
    }
    if ($procs) {
        $procs | Stop-Process -Force
        Write-Host "  已停止: $($t.Name) (匹配 '$($t.Pattern)')" -ForegroundColor Green
    } else {
        Write-Host "  未找到: $($t.Name) (匹配 '$($t.Pattern)')" -ForegroundColor Gray
    }
}

Write-Host "本项目服务已停止" -ForegroundColor Cyan
