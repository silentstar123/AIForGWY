@echo off
REM 切到外网/代理环境后双击本文件，推送到 GitHub
cd /d %~dp0
git push -u origin main
if %errorlevel%==0 (
    echo.
    echo ===== 推送成功 =====
) else (
    echo.
    echo ===== 推送失败：请确认网络可访问 GitHub，或先登录 GitHub 账号 =====
)
pause
