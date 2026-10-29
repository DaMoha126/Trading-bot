param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
if (!(Test-Path (Join-Path $ProjectRoot 'connector\scalping_bridge.py')) -or !(Test-Path (Join-Path $ProjectRoot 'hosted\pool.json'))) {
    throw 'Ouvre PowerShell dans le projet Trading Bot avec le moteur scalping et hosted\pool.json.'
}
$port = 8770
if ($env:MT5_HOST_PORT) { $port = [int]$env:MT5_HOST_PORT }
$probe = New-Object System.Net.Sockets.TcpClient
try {
    $probe.Connect('127.0.0.1', $port)
    throw 'Arrete la fenetre du service avec Ctrl+C avant cette mise a jour. Garde MT5 ouvert.'
} catch [System.Net.Sockets.SocketException] { } finally { $probe.Dispose() }
$files = @('connector/scalping_settings.py','connector/scalping_bridge.py','hosted/host.py','hosted/worker.py','public/control.html','public/control.css','public/control.js')
$stage = Join-Path ([IO.Path]::GetTempPath()) ('TradingBotSettings-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    foreach ($file in $files) {
        $dest = Join-Path $stage $file
        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
        Invoke-WebRequest -UseBasicParsing -Uri ('https://raw.githubusercontent.com/DaMoha126/Trading-bot/research/scalping-m1-signal/' + $file) -OutFile $dest
    }
    $python = Join-Path $env:USERPROFILE '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) { $python = Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
    if (!(Test-Path $python)) { throw 'Python du projet introuvable.' }
    foreach ($file in $files | Where-Object { $_.EndsWith('.py') }) {
        & $python -c 'import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_bytes())' (Join-Path $stage $file)
        if ($LASTEXITCODE -ne 0) { throw 'Verification du code echouee : fichiers actuels conserves.' }
    }
    $backup = Join-Path $ProjectRoot ('hosted\data\backup-settings-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    foreach ($file in $files) {
        $old = Join-Path $ProjectRoot $file
        if (Test-Path $old) {
            $saved = Join-Path $backup $file
            New-Item -ItemType Directory -Force -Path (Split-Path $saved) | Out-Null
            Copy-Item -LiteralPath $old -Destination $saved
        }
    }
    foreach ($file in $files) { Copy-Item -LiteralPath (Join-Path $stage $file) -Destination (Join-Path $ProjectRoot $file) -Force }
    Write-Host 'Onglet Reglages installe. Comptes, liaison sortante et cles conserves. Aucun bot demarre.'
    Write-Host "Sauvegarde : $backup"
    Write-Host 'Relance hosted\LANCER_SANS_TUNNEL.ps1, puis actualise le site.'
} finally { if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Recurse -Force } }
