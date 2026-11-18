# Sets up (or removes) the daily news update in Windows Task Scheduler, for the current user only.
#   powershell -ExecutionPolicy Bypass -File pipeline\schedule_daily.ps1            set up, daily at 08:00
#   powershell -ExecutionPolicy Bypass -File pipeline\schedule_daily.ps1 -At 06:30  set up at another time
#   powershell -ExecutionPolicy Bypass -File pipeline\schedule_daily.ps1 -Remove    remove it
param([string]$At = '08:00', [switch]$Remove)
$name = 'Cyber Attack Map - daily news update'

if ($Remove) {
  Unregister-ScheduledTask -TaskName $name -Confirm:$false -ErrorAction SilentlyContinue
  Write-Host "Removed the scheduled task '$name' (if it existed)."
  exit 0
}

$script = Join-Path $PSScriptRoot 'run_daily.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
  -Argument "-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$script`"" `
  -WorkingDirectory (Split-Path -Parent $PSScriptRoot)
# Daily at the set time, and also shortly after you sign in to Windows (so a day the PC was off is not skipped).
$daily = New-ScheduledTaskTrigger -Daily -At $At
$logon = New-ScheduledTaskTrigger -AtLogOn -User "$env:USERDOMAIN\$env:USERNAME"
$logon.Delay = 'PT5M'
$trigger = @($daily, $logon)
# StartWhenAvailable: if the computer was off or asleep at the set time, run as soon as it is back.
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -RunOnlyIfNetworkAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
  -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger -Settings $settings `
  -Description 'Reads cybersecurity news feeds and updates data\incidents.json for the cyber attack map.' -Force | Out-Null
Write-Host "Scheduled '$name' to run daily at $At and 5 minutes after you sign in. Log: logs\update.log"
