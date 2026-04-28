$env:PGPASSWORD = "123456"
Set-Location -LiteralPath (Split-Path -Parent $PSScriptRoot)
& "C:\Program Files\PostgreSQL\18\bin\psql.exe" `
  -h 127.0.0.1 `
  -p 5432 `
  -U postgres `
  -d pinterest_pod `
  -v ON_ERROR_STOP=1 `
  -f ".\scripts\init_db.sql"
