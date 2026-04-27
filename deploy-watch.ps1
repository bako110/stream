# ── FoliX Auto-Deploy — surveille stream_backend\app et deploie sur changement
$SERVER   = "root@178.104.248.78"
$LOCAL    = "$PSScriptRoot\stream_backend\app"
$REMOTE   = "/opt/backend-stack/app"
$COOLDOWN = 3

Write-Host "Surveillance de $LOCAL..." -ForegroundColor Cyan
Write-Host "Appuie sur Ctrl+C pour arreter." -ForegroundColor DarkGray

$watcher                       = New-Object System.IO.FileSystemWatcher
$watcher.Path                  = $LOCAL
$watcher.Filter                = "*.py"
$watcher.IncludeSubdirectories = $true
$watcher.EnableRaisingEvents   = $true

$lastDeploy = [DateTime]::MinValue

while ($true) {
    # Attendre un evenement (timeout 1000ms puis reboucler)
    $result = $watcher.WaitForChanged([System.IO.WatcherChangeTypes]::All, 1000)

    if ($result.TimedOut) { continue }

    $now = [DateTime]::Now
    if (($now - $lastDeploy).TotalSeconds -lt $COOLDOWN) { continue }
    $lastDeploy = $now

    $relPath = $result.Name.Replace("\", "/")
    $fullPath = Join-Path $LOCAL $result.Name

    Write-Host ""
    Write-Host "  Modifie : $relPath" -ForegroundColor Yellow
    Write-Host "  Deploiement en cours..." -ForegroundColor Cyan

    $remotePath = "${SERVER}:${REMOTE}/${relPath}"
    & scp $fullPath $remotePath

    if ($LASTEXITCODE -eq 0) {
        & ssh $SERVER "cd /opt/backend-stack && docker restart stream_app"
        Write-Host "  OK — deploye et redémarre !" -ForegroundColor Green
    } else {
        Write-Host "  ERREUR scp — verifier la connexion SSH" -ForegroundColor Red
    }
}
