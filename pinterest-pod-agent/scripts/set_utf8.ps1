# 永久设置 Windows 命令行 UTF-8 编码（需管理员运行一次即可）
# 用法: 右键 → 以管理员身份运行 PowerShell → 执行此脚本

Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "OEMCP" -Value "65001" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "ACP" -Value "65001" -ErrorAction SilentlyContinue

$userEnv = [Environment]::GetEnvironmentVariable("PYTHONIOENCODING", "User")
if ($userEnv -ne "utf-8") {
    [Environment]::SetEnvironmentVariable("PYTHONIOENCODING", "utf-8", "User")
}

Write-Host "UTF-8 已设为系统默认编码。重启终端生效。" -ForegroundColor Green
Write-Host ""
Write-Host "如果不想改系统设置，每次用 nanobot 前执行：" -ForegroundColor Yellow
Write-Host "  chcp 65001" -ForegroundColor White
Write-Host "  或者用 scripts/nanobot.ps1 启动（已内置 UTF-8）" -ForegroundColor White
