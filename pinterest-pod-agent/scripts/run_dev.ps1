Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& "c:\nanobot\.venv\Scripts\uvicorn.exe" app.main:app --host 127.0.0.1 --port 8000 --reload
