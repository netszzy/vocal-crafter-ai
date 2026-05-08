$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$venv = Join-Path $root ".venv-gpu"
$python = "C:\Users\netsz\AppData\Local\Programs\Python\Python311\python.exe"
$repo = Join-Path $root "CosyVoice"
$req = Join-Path $root "requirements-windows-gpu.txt"

if (!(Test-Path $python)) {
    throw "Python 3.11 not found at $python"
}

if (!(Test-Path $venv)) {
    & $python -m venv $venv --system-site-packages
}

$py = Join-Path $venv "Scripts\python.exe"

& $py -m pip install --upgrade pip "setuptools<81" wheel
& $py -m pip install --no-build-isolation openai-whisper==20231117
& $py -m pip uninstall -y onnxruntime onnxruntime-directml
& $py -m pip install -r $req
& $py -m pip install --upgrade --force-reinstall onnxruntime-gpu==1.18.1 --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/
& $py -m pip install --upgrade --force-reinstall numpy==1.26.4 packaging==24.2 protobuf==4.25.0 sympy==1.13.1

Write-Host ""
Write-Host "GPU environment is ready:" -ForegroundColor Green
Write-Host "  $venv"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Download a model into $repo\pretrained_models"
Write-Host "  2. Put reference audio into $root\refs\clean"
Write-Host "  3. Run scripts\run_zero_shot.py"
