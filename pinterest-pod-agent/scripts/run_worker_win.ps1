# Windows development worker (solo pool — prefork not available on Windows)
param(
    [string]$Queue = "publish,media,engagement,trend"
)

Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& "c:\nanobot\.venv\Scripts\celery.exe" -A app.celery_app.celery_app worker --loglevel=info --pool=solo -Q $Queue
