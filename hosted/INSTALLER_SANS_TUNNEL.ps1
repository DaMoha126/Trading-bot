param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
if (!(Test-Path (Join-Path $ProjectRoot 'hosted\host.py')) -or !(Test-Path (Join-Path $ProjectRoot 'hosted\pool.json'))) {
    throw 'Ouvre PowerShell dans le dossier du projet qui contient hosted et connector.'
}
$files = @('outbound.py','run_outbound.py','LANCER_SANS_TUNNEL.ps1')
$stage = Join-Path ([IO.Path]::GetTempPath()) ('TradingBotOutbound-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    foreach ($file in $files) {
        $uri = 'https://raw.githubusercontent.com/DaMoha126/Trading-bot/feature/hosted-mt5-pilot/hosted/' + $file
        Invoke-WebRequest -UseBasicParsing -Uri $uri -OutFile (Join-Path $stage $file)
    }
    $python = Join-Path $env:USERPROFILE '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) { $python = Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
    if (!(Test-Path $python)) { throw 'Python du projet introuvable.' }
    foreach ($file in @('outbound.py','run_outbound.py')) {
        & $python -c 'import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_bytes())' (Join-Path $stage $file)
        if ($LASTEXITCODE -ne 0) { throw 'Verification du programme echouee.' }
    }
    foreach ($file in $files) {
        $destination = Join-Path $ProjectRoot ('hosted\' + $file)
        if (Test-Path $destination) { Copy-Item -LiteralPath $destination -Destination ($destination + '.previous') -Force }
        Copy-Item -LiteralPath (Join-Path $stage $file) -Destination $destination -Force
    }
    Write-Host 'Liaison sortante installee. Strategie, comptes, terminaux et secrets inchanges. Aucun bot demarre.'
    Write-Host 'Arrete ancien service et tunnel, puis lance hosted\LANCER_SANS_TUNNEL.ps1.'
} finally { Remove-Item -LiteralPath $stage -Recurse -Force }
