# Runs the news update once and keeps a log. Windows Task Scheduler starts this every day
# (set up by pipeline\schedule_daily.ps1). It only reads public news feeds and rewrites data\.
$ErrorActionPreference = 'Continue'
$root = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $root 'logs'
New-Item -ItemType Directory -Force $logDir | Out-Null
$log = Join-Path $logDir 'update.log'

$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { $python = (Get-Command py -ErrorAction SilentlyContinue).Source }

Set-Location $root
$env:PYTHONIOENCODING = 'utf-8'
Add-Content -Path $log -Encoding utf8 -Value "`n===== $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') ====="
if (-not $python) {
  Add-Content -Path $log -Encoding utf8 -Value 'Python was not found, so the update did not run.'
  exit 1
}
& $python -I (Join-Path $root 'pipeline\update.py') *>&1 | ForEach-Object { "$_" } | Add-Content -Path $log -Encoding utf8
$code = $LASTEXITCODE
Add-Content -Path $log -Encoding utf8 -Value "Finished with exit code $code."

# keep the log to its last 2,000 lines
$lines = Get-Content $log -Encoding utf8
if ($lines.Count -gt 2000) { $lines | Select-Object -Last 2000 | Set-Content $log -Encoding utf8 }
exit $code
