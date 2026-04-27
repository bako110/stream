# Script de déploiement pour le serveur distant
# À exécuter depuis Windows avec PowerShell

$SERVER_USER = "root"
$SERVER_HOST = "ubuntu-4gb-nbg1-1"
$SERVER_PATH = "/opt/backend-stack"
$LOCAL_PATH = "c:\Users\PC1\projetSah\perso\stream\stream_backend"

Write-Host "=== Déploiement du backend sur le serveur distant ===" -ForegroundColor Cyan
Write-Host "Serveur: ${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}" -ForegroundColor Yellow
Write-Host ""

# Vérifier si scp est disponible
$scpExists = Get-Command scp -ErrorAction SilentlyContinue
if (-not $scpExists) {
    Write-Host "Erreur: scp n'est pas installé. Installez OpenSSH ou utilisez Git Bash." -ForegroundColor Red
    exit 1
}

# Étape 1: Utiliser le fichier .env existant
Write-Host "Étape 1: Utilisation du fichier .env existant" -ForegroundColor Green
$envExists = Test-Path ".env"
if (-not $envExists) {
    Write-Host "Erreur: Le fichier .env n'existe pas!" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Fichier .env trouvé" -ForegroundColor Green

# Étape 2: Transférer les fichiers vers le serveur
Write-Host "Étape 2: Transfert des fichiers vers le serveur..." -ForegroundColor Green

$filesToTransfer = @(
    "app",
    "requirements.txt",
    "Dockerfile.prod",
    "docker-compose.prod.yml",
    "nginx-config",
    ".env.prod",
    "init_schema.sql"
)

foreach ($file in $filesToTransfer) {
    $localFile = Join-Path $LOCAL_PATH $file
    if (Test-Path $localFile) {
        Write-Host "Transfert de $file..." -ForegroundColor Yellow
        scp -r $localFile "${SERVER_USER}@${SERVER_HOST}:${SERVER_PATH}/"
    } else {
        Write-Host "⚠️  Fichier non trouvé: $file" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Transfert terminé ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "Commandes à exécuter sur le serveur:" -ForegroundColor Yellow
Write-Host "1. SSH vers le serveur: ssh ${SERVER_USER}@${SERVER_HOST}"
Write-Host "2. cd ${SERVER_PATH}"
Write-Host "3. docker-compose -f docker-compose.prod.yml up -d --build"
Write-Host ""
Write-Host "Pour initialiser la base de données PostgreSQL:" -ForegroundColor Yellow
Write-Host "docker exec -it stream_postgres psql -U stream -d streaming -f /app/init_schema.sql"
