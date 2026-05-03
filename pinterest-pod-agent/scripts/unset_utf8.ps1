# 撤销全局 UTF-8 设置，恢复默认
# 用法: 右键 → 以管理员身份运行 PowerShell → 执行此脚本

# 恢复注册表为中文 Windows 默认值
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "ACP" -Value "936" -ErrorAction SilentlyContinue
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Nls\CodePage" -Name "OEMCP" -Value "936" -ErrorAction SilentlyContinue

# 删除用户环境变量
[Environment]::SetEnvironmentVariable("PYTHONIOENCODING", $null, "User")

Write-Host "已恢复系统默认编码 (GBK/936)。nanobot 请用 nanobot.ps1 启动。" -ForegroundColor Green
