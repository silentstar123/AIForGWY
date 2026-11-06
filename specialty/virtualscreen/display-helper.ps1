param(
    [string]$Instance = 'ROOT\DISPLAY\0001'
)

$dir = if ($env:DSH_HELPER_DIR) { $env:DSH_HELPER_DIR } else { 'C:\ProgramData\DSHDisplay' }
$queue = Join-Path $dir 'queue'
$flag = Join-Path $queue 'restart.flag'
$result = Join-Path $queue 'result.json'

if (-not (Test-Path $flag)) { return }

# 先删标志，避免同一请求被重复执行
Remove-Item $flag -Force -ErrorAction SilentlyContinue

$payload = @{
    at      = (Get-Date).ToString('s')
    ok      = $false
    message = ''
}
try {
    $proc = Start-Process -FilePath 'pnputil.exe' -ArgumentList '/restart-device', $Instance -Wait -PassThru -NoNewWindow
    Start-Sleep -Seconds 3
    Start-Process -FilePath 'DisplaySwitch.exe' -ArgumentList '/extend' -Wait
    Start-Sleep -Seconds 2
    $payload.ok = ($proc.ExitCode -eq 0)
    $payload.exitCode = $proc.ExitCode
} catch {
    $payload.message = $_.Exception.Message
}

$json = $payload | ConvertTo-Json -Compress
[System.IO.File]::WriteAllText($result, $json, [System.Text.UTF8Encoding]::new($false))
