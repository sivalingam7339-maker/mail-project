<#
Creates or updates the Customer Case Automation scheduled task.
Run this script manually from an elevated PowerShell only if your system requires
permission to register scheduled tasks. It does not start the task after registration.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

$taskName = "Customer Case Automation"
$projectRoot = "C:\Mail"
$batchLauncher = Join-Path $projectRoot "run_automation.bat"
$powerShellExecutable = Join-Path $PSHOME "powershell.exe"
$currentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name

if (-not (Test-Path -LiteralPath $batchLauncher -PathType Leaf)) {
    throw "Batch launcher not found: $batchLauncher"
}
if (-not (Test-Path -LiteralPath $powerShellExecutable -PathType Leaf)) {
    throw "PowerShell executable not found: $powerShellExecutable"
}

# Run the existing launcher once per invocation; this action contains no workflow logic.
$command = "& '$batchLauncher'; exit `$LASTEXITCODE"
$action = New-ScheduledTaskAction `
    -Execute $powerShellExecutable `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"$command`"" `
    -WorkingDirectory $projectRoot

# Start on the user's next logon, then use a separate five-minute repeating trigger.
$logonTrigger = New-ScheduledTaskTrigger -AtLogOn -User $currentUser
$fiveMinuteTrigger = New-ScheduledTaskTrigger `
    -Once `
    -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$principal = New-ScheduledTaskPrincipal -UserId $currentUser -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -MultipleInstances IgnoreNew

$task = New-ScheduledTask `
    -Action $action `
    -Trigger @($logonTrigger, $fiveMinuteTrigger) `
    -Principal $principal `
    -Settings $settings `
    -Description "Runs Customer Case Automation once at logon and every five minutes while the user is logged in."

# -Force updates the same named task rather than creating a duplicate.
Register-ScheduledTask -TaskName $taskName -InputObject $task -Force | Out-Null

Write-Output "Scheduled task created or updated: $taskName"
Write-Output "Working directory: $projectRoot"
Write-Output "Launcher: $batchLauncher"
Write-Output "Triggers: at logon and every 5 minutes"
