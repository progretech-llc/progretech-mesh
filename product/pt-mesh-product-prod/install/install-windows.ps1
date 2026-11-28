$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$Venv = Join-Path $Root ".mesh-venv"

py -m venv $Venv
& "$Venv\Scripts\python.exe" -m pip install --upgrade pip
& "$Venv\Scripts\python.exe" -m pip install -r (Join-Path $Root "requirements.txt")

Write-Host "Mesh customer gateway dependencies installed."
Write-Host ""
Write-Host "Next: generate an activation code in Mesh and run the bootstrap command shown there."
