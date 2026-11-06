# 安装一次即可：把「重启显示设备」做成 SYSTEM 计划任务，之后不再弹 UAC。
# 需要管理员窗口运行：
#   powershell -ExecutionPolicy Bypass -File specialty\virtualscreen\install-helper.ps1
param(
    [string]$Instance = 'ROOT\DISPLAY\0001',
    [int]$Minutes = 1
)

$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$helperSource = Join-Path $here 'display-helper.ps1'
$dir = 'C:\ProgramData\DSHDisplay'
$queue = Join-Path $dir 'queue'
$helper = Join-Path $dir 'display-helper.ps1'

New-Item -ItemType Directory -Force -Path $dir | Out-Null
New-Item -ItemType Directory -Force -Path $queue | Out-Null
Copy-Item $helperSource $helper -Force

# 脚本目录只让 SYSTEM 和管理员改；队列目录让普通用户能写标志、读结果
$admins = 'BUILTIN\Administrators'
$aclDir = New-Object System.Security.AccessControl.DirectorySecurity
$aclDir.SetAccessRuleProtection($true, $false)
$aclDir.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule('SYSTEM', 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
$aclDir.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($admins, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
Set-Acl -Path $dir -AclObject $aclDir

$aclQueue = New-Object System.Security.AccessControl.DirectorySecurity
$aclQueue.SetAccessRuleProtection($true, $false)
$aclQueue.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule('SYSTEM', 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
$aclQueue.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule($admins, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
$aclQueue.AddAccessRule((New-Object System.Security.AccessControl.FileSystemAccessRule('BUILTIN\Users', 'Modify', 'ContainerInherit,ObjectInherit', 'None', 'Allow')))
Set-Acl -Path $queue -AclObject $aclQueue

$marker = @{ at = (Get-Date).ToString('s'); instance = $Instance } | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText((Join-Path $queue 'installed.json'), $marker, [System.Text.UTF8Encoding]::new($false))

$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$helper`" -Instance `"$Instance`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes $Minutes)
$principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable

Register-ScheduledTask -TaskName 'DSHDisplayHelper' -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Force | Out-Null

Write-Output "installed: DSHDisplayHelper (every $Minutes min, SYSTEM)"
Write-Output "helper dir: $dir"
