# nanobot 启动脚本 — 自动设 UTF-8 防止乱码
chcp 65001 > $null
$env:PYTHONIOENCODING = "utf-8"

$args = $MyInvocation.Line -replace '^.*\.ps1\s*', ''
if ($args) {
    c:\nanobot\.venv\Scripts\nanobot.exe agent -m $args
} else {
    c:\nanobot\.venv\Scripts\nanobot.exe agent
}
