param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
if (!(Test-Path (Join-Path $ProjectRoot 'hosted\host.py')) -or !(Test-Path (Join-Path $ProjectRoot 'hosted\pool.json'))) {
    throw 'Ouvre PowerShell dans le dossier du projet qui contient hosted\pool.json.'
}
$probe = New-Object System.Net.Sockets.TcpClient
try {
    $probe.Connect('127.0.0.1', 8770)
    throw 'Le service MT5 est encore actif. Arrete-le avec Ctrl+C, puis relance cette mise a jour.'
} catch [System.Net.Sockets.SocketException] { } finally { $probe.Dispose() }
$stage = Join-Path ([IO.Path]::GetTempPath()) ('TradingBotScalp-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null
$files = @('connector/bridge.py','connector/strategy.py','connector/trade_history.py','connector/structure_m1.py','connector/liquidity_signal.py','connector/scalping_bridge.py','hosted/host.py','hosted/worker.py','public/control.js')
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/DaMoha126/Trading-bot/archive/refs/heads/research/scalping-m1-signal.zip' -OutFile (Join-Path $stage 'source.zip')
    Expand-Archive -LiteralPath (Join-Path $stage 'source.zip') -DestinationPath (Join-Path $stage 'source')
    $source = (Get-ChildItem (Join-Path $stage 'source') -Directory | Select-Object -First 1).FullName
    foreach ($file in $files) { if (!(Test-Path (Join-Path $source $file))) { throw "Fichier manquant : $file" } }
    $python = Join-Path $env:USERPROFILE '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) { throw 'Python du projet introuvable dans .venv.' }
    foreach ($file in $files | Where-Object { $_.EndsWith('.py') }) {
        & $python -c 'import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_bytes())' (Join-Path $source $file)
        if ($LASTEXITCODE -ne 0) { throw "Verification Python echouee : $file" }
    }
    $backup = Join-Path $ProjectRoot ('hosted\data\backup-scalp-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    foreach ($file in $files) {
        $old = Join-Path $ProjectRoot $file
        if (Test-Path $old) {
            $saved = Join-Path $backup $file
            New-Item -ItemType Directory -Force -Path (Split-Path $saved) | Out-Null
            Copy-Item -LiteralPath $old -Destination $saved
        }
    }
    foreach ($file in $files) {
        $destination = Join-Path $ProjectRoot $file
        New-Item -ItemType Directory -Force -Path (Split-Path $destination) | Out-Null
        Copy-Item -LiteralPath (Join-Path $source $file) -Destination $destination -Force
    }
    Write-Host 'Mise a jour du prototype M1 terminee. Aucun bot demarre.'
    Write-Host "Sauvegarde des anciens fichiers : $backup"
} finally { Remove-Item -LiteralPath $stage -Recurse -Force }
