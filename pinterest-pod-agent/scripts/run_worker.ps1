param(
    [string]$Queue = "publish,media,engagement,trend",
    [int]$Concurrency = 4,
    [string]$Pool = "prefork"
)

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& "c:\nanobot\.venv\Scripts\celery.exe" -A app.celery_app.celery_app worker --loglevel=info --pool=$Pool --concurrency=$Concurrency -Q $Queue
