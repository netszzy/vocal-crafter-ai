@echo off
setlocal
cd /d "%~dp0"
:: 使用 Bypass 模式运行 PowerShell 脚本，绕过执行策略限制
powershell -NoProfile -ExecutionPolicy Bypass -File "launch.ps1"
if %ERRORLEVEL% neq 0 pause
endlocal
