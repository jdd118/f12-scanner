# Schedule the F12 Scanner to run daily at 7:00 AM
# Run this script as Administrator

$Action = New-ScheduledTaskAction -Execute "C:\Users\m3nbtp\Downloads\F12 scanner\run_scanner.bat"
$Trigger = New-ScheduledTaskTrigger -Daily -At 07:00AM
$Principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -RunLevel Limited
$Settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName "F12Scanner" `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Settings $Settings `
    -Description "Daily Ferrari F12 Canada listing scanner"

Write-Host "Scheduled task 'F12Scanner' created for daily 7:00 AM"
