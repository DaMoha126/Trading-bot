$ErrorActionPreference = 'Stop'
$project = Split-Path $PSScriptRoot -Parent
Set-Location $project
$python = Join-Path $env:USERPROFILE '.venv\Scripts\python.exe'
if (!(Test-Path $python)) { $python = Join-Path $project '.venv\Scripts\python.exe' }
if (!(Test-Path $python)) { throw 'Python du projet introuvable. Utiliser le même environnement Python que pour hosted\host.py.' }
& $python (Join-Path $project 'hosted\run_outbound.py')
if ($LASTEXITCODE -ne 0) { Write-Host 'Le lancement a échoué. Lis le message ci-dessus.' }
Read-Host 'Appuie sur Entree pour fermer'
