#Requires -RunAsAdministrator
<#
  启用常驻虚拟屏幕（一次性，管理员）。

  只做两件事：
    1. 列出虚拟显示设备和当前显示器；
    2. -Action restart：重启已装的虚拟显示设备，让它重新创建监视器。

  不安装任何新驱动。如果重启后仍没有新增屏幕，说明该驱动只在远程会话里
  创建监视器，需要改用向日葵客户端的“扩展屏”，或安装 Virtual Display Driver。

  用法（管理员 PowerShell）：
    powershell -ExecutionPolicy Bypass -File setup.ps1 -Action status
    powershell -ExecutionPolicy Bypass -File setup.ps1 -Action restart
#>
param(
    [ValidateSet("status", "restart")]
    [string]$Action = "status",
    [string]$InstanceId = ""
)

$ErrorActionPreference = "Stop"

function Get-Screens {
    Add-Type -AssemblyName System.Windows.Forms
    foreach ($s in [System.Windows.Forms.Screen]::AllScreens) {
        "{0} {1}x{2} at ({3},{4}) primary={5}" -f $s.DeviceName, $s.Bounds.Width, $s.Bounds.Height, $s.Bounds.X, $s.Bounds.Y, $s.Primary
    }
}

function Get-VirtualDevices {
    Get-PnpDevice -Class Display -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like "ROOT\*" -or $_.FriendlyName -match "Oray|Idd|Virtual|VDD" } |
        Select-Object FriendlyName, Status, InstanceId
}

function Show-State {
    Write-Host "== 虚拟显示设备 =="
    $devices = Get-VirtualDevices
    if ($devices) { $devices | Format-Table -AutoSize | Out-String | Write-Host }
    else { Write-Host "（未安装虚拟显示驱动）" }
    Write-Host "== 当前显示器 =="
    Get-Screens | ForEach-Object { Write-Host $_ }
}

Show-State

if ($Action -eq "status") { exit 0 }

$devices = @()
if ($InstanceId) {
    $devices = @(Get-PnpDevice -Class Display -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -eq $InstanceId })
} else {
    $devices = @(Get-PnpDevice -Class Display -ErrorAction SilentlyContinue |
        Where-Object { $_.InstanceId -like "ROOT\*" })
}

if (-not $devices) {
    Write-Host "没有 Root 枚举的虚拟显示设备。"
    Write-Host "可以：向日葵客户端里开启“扩展屏”，或运行 install-vdd.ps1 -Action install。"
    exit 1
}

$before = @(Get-Screens).Count
foreach ($device in $devices) {
    Write-Host "重启虚拟显示设备：$($device.InstanceId)"
    pnputil /restart-device "$($device.InstanceId)" | Out-Host
    Start-Sleep -Seconds 3
}

$after = @(Get-Screens).Count
Write-Host "显示器数量：$before -> $after"
Get-Screens | ForEach-Object { Write-Host $_ }

if ($after -gt $before) {
    Write-Host "虚拟屏已出现。回到普通权限运行：python specialty/virtualscreen/virtualscreen.py status"
    exit 0
}

Write-Host "重启后没有新增虚拟屏。可以再重启一次电脑；仍不行就用 -InstanceId 指定设备单独重启。"
exit 2
