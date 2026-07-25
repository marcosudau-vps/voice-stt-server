$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    py -3.12 -m venv (Join-Path $ProjectRoot ".venv")
}

& $PythonExe -m pip install --upgrade pip setuptools wheel
& $PythonExe -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu
& $PythonExe -m pip install -e "${ProjectRoot}[faster-whisper,silero-onnx-cpu,wakewords,kroko-builder,server,example-app]"

Write-Host "CPU-only environment installed at $PythonExe"
Write-Host "Install the local Kroko Windows wheel into this environment if it is not already present."
