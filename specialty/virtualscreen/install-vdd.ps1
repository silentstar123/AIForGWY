#Requires -RunAsAdministrator
<#
  安装常驻虚拟显示器（Virtual Display Driver, VDD）。

  做四件事：
    1. 下载官方 VDD 驱动包，校验 SHA256；
    2. 校验驱动的 Authenticode 签名（SignPath Foundation）；
    3. 复制到 C:\VirtualDisplayDriver；
    4. 用 devcon 建一个 Root\MttVDD 设备，让 Windows 多出一块虚拟屏。

  不装第三方来路不明的可执行文件：只用 VDD 官方 release 和本机已有的 devcon。

  用法（管理员 PowerShell）：
    powershell -ExecutionPolicy Bypass -File install-vdd.ps1 -Action status
    powershell -ExecutionPolicy Bypass -File install-vdd.ps1 -Action install
    powershell -ExecutionPolicy Bypass -File install-vdd.ps1 -Action remove
#>
param(
    [ValidateSet("status", "install", "remove")]
    [string]$Action = "install"
)

$ErrorActionPreference = "Stop"

$VddVersion = "25.7.23"
$VddUrl = "https://github.com/VirtualDrivers/Virtual-Display-Driver/releases/download/$VddVersion/VirtualDisplayDriver-x86.Driver.Only.zip"
$VddSha256 = "e24210692b442b39af763536330ce78b423f19342b7a7792c26de3944e418b3a"
$InstallDir = "C:\VirtualDisplayDriver"
$LocalDir = Join-Path $PSScriptRoot "vdd"
$DevconCandidates = @(
    (Join-Path $LocalDir "devcon.exe"),
    "$env:SystemRoot\System32\devcon.exe",
    "C:\Program Files\Oray\AweSun\driver\Idd64\devcon.exe",
    "C:\Program Files (x86)\Oray\AweSun\driver\Idd64\devcon.exe"
)

function Get-Screens {
    Add-Type -AssemblyName System.Windows.Forms
    foreach ($screen in [System.Windows.Forms.Screen]::AllScreens) {
        "{0} {1}x{2} at ({3},{4}) primary={5}" -f $screen.DeviceName, $screen.Bounds.Width, $screen.Bounds.Height, $screen.Bounds.X, $screen.Bounds.Y, $screen.Primary
    }
}

function Get-VddDevices {
    Get-PnpDevice -Class Display -ErrorAction SilentlyContinue |
        Where-Object { $_.FriendlyName -match "Virtual Display Driver" -or $_.InstanceId -like "ROOT\MttVDD*" } |
        Select-Object FriendlyName, Status, InstanceId
}

function Find-Devcon {
    foreach ($path in $DevconCandidates) {
        if (Test-Path $path) { return $path }
    }
    $onPath = Get-Command devcon.exe -ErrorAction SilentlyContinue
    if ($onPath) { return $onPath.Source }
    throw "找不到 devcon.exe。可先安装向日葵（自带 devcon），或从 Windows Driver Kit 取一份放到 PATH。"
}

function Show-State {
    Write-Host "== 虚拟显示设备 =="
    $devices = Get-VddDevices
    if ($devices) { $devices | Format-Table -AutoSize | Out-String | Write-Host }
    else { Write-Host "（未安装 VDD）" }
    Write-Host "== 当前显示器 =="
    Get-Screens | ForEach-Object { Write-Host $_ }
}

Show-State

if ($Action -eq "status") { exit 0 }

$devcon = Find-Devcon

if ($Action -eq "remove") {
    Write-Host "移除 Root\MttVDD ..."
    & $devcon remove "Root\MttVDD" | Out-Host
    Start-Sleep -Seconds 3
    Show-State
    Write-Host "如需彻底删除驱动文件，手动删除 $InstallDir"
    exit 0
}

# install
if (-not (Test-Path (Join-Path $InstallDir "MttVDD.inf"))) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
    $localInf = Join-Path $LocalDir "MttVDD.inf"
    if (Test-Path $localInf) {
        Write-Host "使用迁移包内置的 VDD 文件（$LocalDir）..."
        Copy-Item -Path (Join-Path $LocalDir "*") -Destination $InstallDir -Recurse -Force
    } else {
        $temp = Join-Path $env:TEMP ("vdd-" + [guid]::NewGuid().ToString("N"))
        New-Item -ItemType Directory -Path $temp -Force | Out-Null
        $zip = Join-Path $temp "vdd.zip"
        Write-Host "下载 VDD $VddVersion ..."
        Invoke-WebRequest -Uri $VddUrl -OutFile $zip -UseBasicParsing
        $hash = (Get-FileHash $zip -Algorithm SHA256).Hash.ToLower()
        if ($hash -ne $VddSha256) {
            throw "SHA256 不匹配：$hash"
        }
        Expand-Archive -Path $zip -DestinationPath $temp -Force
        Copy-Item -Path (Join-Path $temp "VirtualDisplayDriver\*") -Destination $InstallDir -Recurse -Force
        Remove-Item -Path $temp -Recurse -Force -ErrorAction SilentlyContinue
    }
} else {
    Write-Host "已存在 $InstallDir\MttVDD.inf，跳过下载"
}

$cat = Join-Path $InstallDir "mttvdd.cat"
$signature = Get-AuthenticodeSignature $cat
if ($signature.Status -ne "Valid") {
    throw "驱动签名无效：$($signature.Status)（$cat）"
}
Write-Host "驱动签名：$($signature.SignerCertificate.Subject)"

$before = @(Get-Screens).Count
Write-Host "安装 Root\MttVDD ..."
& $devcon install (Join-Path $InstallDir "MttVDD.inf") "Root\MttVDD" | Out-Host
Start-Sleep -Seconds 8

$after = @(Get-Screens).Count
Write-Host "显示器数量：$before -> $after"

if ($after -le $before) {
    Write-Host "新显示器已建成但桌面还没扩展，执行 DisplaySwitch /extend ..."
    Start-Process -FilePath "DisplaySwitch.exe" -ArgumentList "/extend" -Wait
    Start-Sleep -Seconds 3
    $after = @(Get-Screens).Count
    Write-Host "扩展后显示器数量：$before -> $after"
}

Show-State

if ($after -gt $before) {
    Write-Host "虚拟屏已出现。普通权限运行：python specialty/virtualscreen/virtualscreen.py status"
    exit 0
}

Write-Host "设备已安装但没有新增显示器。检查设备管理器里是否有“Virtual Display Driver”，"
Write-Host "再运行 setup.ps1 -Action restart，或重启一次。"
exit 2
