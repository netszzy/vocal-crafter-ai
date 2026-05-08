$ErrorActionPreference = "Stop"

$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$voiceRoot = Split-Path -Parent $scriptRoot
$venvActivate = Join-Path $voiceRoot ".venv-gpu\Scripts\Activate.ps1"
$configPath = Join-Path $scriptRoot "batch_config.json"
$runnerPath = Join-Path $scriptRoot "batch_zero_shot.py"

if (!(Test-Path $venvActivate)) {
    throw "GPU environment not found: $venvActivate"
}

if (!(Test-Path $configPath)) {
    throw "Config file not found: $configPath"
}

if (!(Test-Path $runnerPath)) {
    throw "Batch runner not found: $runnerPath"
}

$config = Get-Content $configPath -Raw | ConvertFrom-Json

if (!$config.model_dir) { throw "Missing model_dir in batch_config.json" }
if (!$config.ref_wav) { throw "Missing ref_wav in batch_config.json" }
if (!$config.ref_text) { throw "Missing ref_text in batch_config.json" }
if (!$config.input) { throw "Missing input in batch_config.json" }
if (!$config.output_dir) { throw "Missing output_dir in batch_config.json" }

& $venvActivate

$prefix = if ($config.prefix) { [string]$config.prefix } else { "line" }
$mergedOutput = if ($config.merged_output) {
    [string]$config.merged_output
} else {
    Join-Path ([string]$config.output_dir) ($prefix + "_full.wav")
}

$args = @(
    $runnerPath,
    "--model-dir", $config.model_dir,
    "--ref-wav", $config.ref_wav,
    "--ref-text", $config.ref_text,
    "--input", $config.input,
    "--output-dir", $config.output_dir,
    "--merge-output", $mergedOutput
)

if ($config.prefix) {
    $args += @("--prefix", [string]$config.prefix)
}

if ($null -ne $config.start_index) {
    $args += @("--start-index", [string]$config.start_index)
}

if ($config.cv3_prefix) {
    $args += @("--cv3-prefix", [string]$config.cv3_prefix)
}

if ($null -ne $config.silence_secs) {
    $args += @("--silence-secs", [string]$config.silence_secs)
}

if ($null -ne $config.max_chars) {
    $args += @("--max-chars", [string]$config.max_chars)
}

if ($config.force_cpu -eq $true) {
    $args += "--force-cpu"
}

python @args

Write-Host ""
Write-Host "Batch generation finished." -ForegroundColor Green
