param(
    [string]$Root = (Resolve-Path "$PSScriptRoot\..").Path
)

$ErrorActionPreference = "Stop"
$State = if ($env:MESH_AGENT_STATE_DIR) {
    $env:MESH_AGENT_STATE_DIR
} else {
    Join-Path $HOME ".progretech-mesh"
}

New-Item -ItemType Directory -Force -Path (Join-Path $State "credentials") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $State "logs") | Out-Null

Write-Host "ProgreTech Mesh local components are available."
Write-Host "Root:  $Root"
Write-Host "State: $State"
Write-Host "No running agent process was restarted or modified."
