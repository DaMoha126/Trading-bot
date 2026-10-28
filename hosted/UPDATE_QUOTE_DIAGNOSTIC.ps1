param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
$target = Join-Path $ProjectRoot 'connector\scalping_bridge.py'
if (!(Test-Path $target)) { throw 'Le moteur scalping est introuvable dans ce dossier. Ouvre PowerShell dans le projet Trading Bot qui le contient.' }
$probe = New-Object System.Net.Sockets.TcpClient
try {
    $probe.Connect('127.0.0.1', 8770)
    throw 'Arrete la fenetre du service avec Ctrl+C avant la mise a jour. Garde MT5 ouvert.'
} catch [System.Net.Sockets.SocketException] { } finally { $probe.Dispose() }
$stage = Join-Path ([IO.Path]::GetTempPath()) ('TradingBotQuote-' + [guid]::NewGuid() + '.py')
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'https://raw.githubusercontent.com/DaMoha126/Trading-bot/research/scalping-m1-signal/connector/scalping_bridge.py' -OutFile $stage
    $python = Join-Path $env:USERPROFILE '.venv\Scripts\python.exe'
    if (!(Test-Path $python)) { $python = Join-Path $ProjectRoot '.venv\Scripts\python.exe' }
    if (!(Test-Path $python)) { throw 'Python du projet introuvable.' }
    & $python -c 'import ast,pathlib,sys; ast.parse(pathlib.Path(sys.argv[1]).read_bytes())' $stage
    if ($LASTEXITCODE -ne 0) { throw 'Verification Python echouee. Ancien fichier conserve.' }
    $backup = $target + '.backup-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
    Copy-Item -LiteralPath $target -Destination $backup
    Copy-Item -LiteralPath $stage -Destination $target -Force
    Write-Host 'Diagnostic des cotations mis a jour. Aucun bot demarre. Relance hosted\LANCER_SANS_TUNNEL.ps1.'
} finally { if (Test-Path $stage) { Remove-Item -LiteralPath $stage -Force } }
