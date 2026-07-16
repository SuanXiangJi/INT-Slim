param(
    [string]$EnvironmentName = "xbots-sandbox"
)

$ErrorActionPreference = "Stop"
$backend = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$marker = Join-Path $backend ".sandbox-env-ready"
if (Test-Path -LiteralPath $marker) {
    Remove-Item -LiteralPath $marker -Force
}

conda install -n $EnvironmentName -c conda-forge openjdk=21 nodejs=20 m2w64-toolchain -y --solver libmamba
if ($LASTEXITCODE -ne 0) { throw "Conda runtime installation failed." }

conda run -n $EnvironmentName python -m pip install -r (Join-Path $backend "sandbox-requirements.txt")
if ($LASTEXITCODE -ne 0) { throw "Python sandbox dependency installation failed." }

conda run -n $EnvironmentName python -c "import numpy,pandas,scipy,sklearn,matplotlib,torch; print('python-libraries-ok')"
if ($LASTEXITCODE -ne 0) { throw "Python library verification failed." }
conda run -n $EnvironmentName java -version
if ($LASTEXITCODE -ne 0) { throw "Java runtime verification failed." }
conda run -n $EnvironmentName javac -version
if ($LASTEXITCODE -ne 0) { throw "Java compiler verification failed." }
conda run -n $EnvironmentName node --version
if ($LASTEXITCODE -ne 0) { throw "Node.js runtime verification failed." }
conda run -n $EnvironmentName gcc --version
if ($LASTEXITCODE -ne 0) { throw "C compiler verification failed." }
conda run -n $EnvironmentName g++ --version
if ($LASTEXITCODE -ne 0) { throw "C++ compiler verification failed." }

Set-Content -LiteralPath $marker -Value (Get-Date).ToString("o") -Encoding ascii
Write-Output "xbots-sandbox is ready."
