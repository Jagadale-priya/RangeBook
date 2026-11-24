# Windows Task Scheduler — run daily before market (e.g. 7:30 AM IST)
# Action: powershell.exe -ExecutionPolicy Bypass -File "C:\Users\Priyanka\Agent\scripts\morning_cron.ps1"

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot -Parent)

$logDir = Join-Path (Get-Location) "stock_signal_data\morning_reports"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir ("cron_" + (Get-Date -Format "yyyy-MM-dd") + ".log")

Write-Output "=== Morning job $(Get-Date -Format o) ===" | Tee-Object -FilePath $log -Append
python stock_signal_ml.py --morning-report 2>&1 | Tee-Object -FilePath $log -Append
exit $LASTEXITCODE
