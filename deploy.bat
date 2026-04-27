@echo off
set SERVER=root@178.104.248.78
set REMOTE=/opt/backend-stack/app

echo [1/2] Copie du code vers le serveur...
scp -r "%~dp0stream_backend\app\." %SERVER%:%REMOTE%/

echo [2/2] Rebuild et redemarrage du backend...
ssh %SERVER% "cd /opt/backend-stack && docker compose -f docker-compose.prod.yml build app && docker compose -f docker-compose.prod.yml up -d app"

echo Done!
pause
