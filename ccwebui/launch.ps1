# 语音合成 WebUI 增强启动脚本
$OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "语音合成 WebUI - 启动中"

# 1. 路径初始化
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ProjectRoot = (Get-Item $ScriptDir).Parent.FullName
Set-Location $ProjectRoot

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "   语音合成系统自检与启动" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host "项目根目录: $ProjectRoot"

# 2. 环境校验
$VenvPath = Join-Path $ProjectRoot ".venv-gpu"
$PythonExe = Join-Path $VenvPath "Scripts\python.exe"
$AppPy = Join-Path $ProjectRoot "ccwebui\app.py"
$ModelPath = Join-Path $ProjectRoot "CosyVoice\pretrained_models\Fun-CosyVoice3-0.5B"

$CheckPassed = $true

if (-not (Test-Path $PythonExe)) {
    Write-Host "[错误] 未找到虚拟环境: $VenvPath" -ForegroundColor Red
    $CheckPassed = $false
}

if (-not (Test-Path $AppPy)) {
    Write-Host "[错误] 未找到启动文件: $AppPy" -ForegroundColor Red
    $CheckPassed = $false
}

if (-not (Test-Path $ModelPath)) {
    Write-Host "[警告] 未找到模型目录: $ModelPath" -ForegroundColor Yellow
    Write-Host "       请确保模型已正确放置在 CosyVoice 目录下。" -ForegroundColor Yellow
}

# 3. 端口冲突检测
$Port = 7861
$PortProcess = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -First 1
if ($PortProcess) {
    try {
        $Proc = Get-Process -Id $PortProcess -ErrorAction SilentlyContinue
        if ($Proc) {
            $ProcName = $Proc.ProcessName
            Write-Host "[提示] 端口 $Port 已被占用 (进程: $ProcName, PID: $PortProcess)" -ForegroundColor Yellow
            Write-Host "       尝试清理旧进程..." -ForegroundColor Gray
            Stop-Process -Id $PortProcess -Force -ErrorAction SilentlyContinue
            Start-Sleep -Seconds 1
        }
    } catch {}
}

if (-not $CheckPassed) {
    Write-Host "--------------------------------------------------"
    Write-Host "环境校验未通过，请确认后再试。" -ForegroundColor Red
    Read-Host "按任意键退出..."
    exit 1
}

# 4. 启动应用
Write-Host "正在启动服务..." -ForegroundColor Green
$Host.UI.RawUI.WindowTitle = "语音合成 WebUI - 运行中"

# 显式调用 python
& $PythonExe $AppPy

if ($LASTEXITCODE -ne 0) {
    Write-Host "`n[错误] 程序异常退出，退出码: $LASTEXITCODE" -ForegroundColor Red
    Read-Host "按任意键退出..."
}
