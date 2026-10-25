param([string]$ProjectRoot = (Get-Location).Path)
$ErrorActionPreference = 'Stop'
if (!(Test-Path (Join-Path $ProjectRoot 'hosted\pool.json'))) {
    throw 'Ouvre PowerShell dans le dossier du projet contenant hosted et connector.'
}
$probe = New-Object System.Net.Sockets.TcpClient
try {
    $probe.Connect('127.0.0.1', 8770)
    throw 'Le service MT5 tourne encore. Arrete uniquement sa fenetre avec Ctrl+C, puis relance cette mise a jour.'
} catch [System.Net.Sockets.SocketException] {
    # No listener: host is stopped. The Cloudflare tunnel may stay open.
} finally { $probe.Dispose() }
$stage = Join-Path ([IO.Path]::GetTempPath()) ('TradingBotGold-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $stage | Out-Null
$files = @('connector/bridge.py','connector/strategy.py','hosted/host.py','hosted/worker.py','public/control.html','public/control.js','public/lab/app.js')
try {
    Invoke-WebRequest -UseBasicParsing -Uri 'https://github.com/DaMoha126/Trading-bot/archive/refs/heads/feature/hosted-mt5-pilot.zip' -OutFile (Join-Path $stage 'source.zip')
    Expand-Archive -LiteralPath (Join-Path $stage 'source.zip') -DestinationPath (Join-Path $stage 'source')
    $source = (Get-ChildItem (Join-Path $stage 'source') -Directory | Select-Object -First 1).FullName
    foreach ($file in $files) {
        if (!(Test-Path (Join-Path $source $file))) { throw "Fichier manquant : $file" }
    }
    $python = Join-Path $env:USERPROFILE '.venv\Scripts\python.exe'
    foreach ($file in $files | Where-Object { $_.EndsWith('.py') }) {
        & $python -c 'import ast, pathlib, sys; ast.parse(pathlib.Path(sys.argv[1]).read_bytes())' (Join-Path $source $file)
        if ($LASTEXITCODE -ne 0) { throw "Verification Python echouee : $file" }
    }
    $backup = Join-Path $ProjectRoot ('hosted\data\backup-gold-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
    foreach ($file in $files) {
        $old = Join-Path $ProjectRoot $file
        $saved = Join-Path $backup $file
        New-Item -ItemType Directory -Force -Path (Split-Path $saved) | Out-Null
        Copy-Item -LiteralPath $old -Destination $saved
    }
    foreach ($file in $files) {
        Copy-Item -LiteralPath (Join-Path $source $file) -Destination (Join-Path $ProjectRoot $file)
    }
    Write-Host 'Mise a jour XAUUSD terminee. Configurations, cle, terminaux et historique conserves. Aucun bot demarre.'
    Write-Host "Sauvegarde : $backup"
} finally {
    Remove-Item -LiteralPath $stage -Recurse -Force
}
