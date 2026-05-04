# Nanobot launcher with UTF-8 console output.
chcp 65001 > $null
$env:PYTHONIOENCODING = "utf-8"

$message = $MyInvocation.Line -replace '^.*\.ps1\s*', ''
if ($message) {
    c:\nanobot\.venv\Scripts\nanobot.exe agent -m $message
} else {
    c:\nanobot\.venv\Scripts\nanobot.exe agent
}
