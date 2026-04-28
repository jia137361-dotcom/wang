Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& "c:\nanobot\.venv\Scripts\celery.exe" -A app.celery_app.celery_app beat --loglevel=info
