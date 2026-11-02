$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (Get-Command py -ErrorAction SilentlyContinue) { & py -3 -m venv (Join-Path $Root ".venv") }
elseif (Get-Command python -ErrorAction SilentlyContinue) { & python -m venv (Join-Path $Root ".venv") }
else { throw "Python >=3.11 required" }
if ($LASTEXITCODE -ne 0) { throw "Failed to create virtual environment" }
$Python = Join-Path $Root ".venv\Scripts\python.exe"
& $Python -c "import sys; assert sys.version_info >= (3,11), 'Python >=3.11 required'"
if ($LASTEXITCODE -ne 0) { throw "Unsupported Python version" }
& $Python -m pip install -e $Root
if ($LASTEXITCODE -ne 0) { throw "API installation failed" }
& $Python -c "import lucida_api; print(lucida_api.API_VERSION)"
