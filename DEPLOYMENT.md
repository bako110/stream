# Instructions de déploiement sur serveur distant

## Serveur cible
- **Hôte**: ubuntu-4gb-nbg1-1
- **Utilisateur**: root
- **Chemin**: /opt/backend-stack

## Prérequis sur le serveur
1. Docker installé
2. Docker Compose installé
3. Port 80 et 443 ouverts

## Étapes de déploiement

### 1. Vérifier le fichier .env

Le fichier `.env` existant sera utilisé pour le déploiement. Assurez-vous qu'il contient:

- POSTGRES_PASSWORD (mot de passe fort)
- MONGO_PASSWORD (mot de passe fort)
- REDIS_PASSWORD (mot de passe fort)
- JWT_SECRET_KEY (chaîne aléatoire très sécurisée)
- JWT_REFRESH_SECRET_KEY (autre chaîne sécurisée)
- DOMAIN_NAME (votre nom de domaine pour SSL)

### 2. Transférer les fichiers sur le serveur

**Option A: Utiliser le script PowerShell (recommandé)**
```powershell
.\deploy-to-server.ps1
```

**Option B: Transfert manuel avec scp**
```powershell
scp -r app root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
scp requirements.txt root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
scp Dockerfile.prod root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
scp docker-compose.prod.yml root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
scp -r nginx-config root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
scp .env.prod root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
scp init_schema.sql root@ubuntu-4gb-nbg1-1:/opt/backend-stack/
```

### 3. Déployer sur le serveur

Se conneau serveur:
```bash
ssh root@ubuntu-4gb-nbg1-1
```

Créer le répertoire si nécessaire:
```bash
mkdir -p /opt/backend-stack
cd /opt/backend-stack
```

Lancer les containers:
```bash
docker-compose -f docker-compose.prod.yml up -d --build
```

### 4. Initialiser la base de données PostgreSQL

```bash
docker exec -it stream_postgres psql -U stream -d streaming -f /app/init_schema.sql
```

### 5. Configurer SSL avec Certbot (optionnel)

Si vous avez un nom de domaine configuré:

```bash
# Obtenir le certificat SSL
docker run --rm -v certbot_conf:/etc/letsencrypt -v certbot_www:/var/www/certbot certbot/certbot certonly --webroot --webroot-path /var/www/certbot -d votre-domain.com

# Redémarrer nginx
docker restart stream_nginx
```

### 6. Vérifier le déploiement

```bash
# Vérifier les containers
docker-compose -f docker-compose.prod.yml ps

# Voir les logs
docker-compose -f docker-compose.prod.yml logs -f

# Tester l'API
curl http://localhost/api/health
```

## Commandes utiles

```bash
# Arrêter les services
docker-compose -f docker-compose.prod.yml down

# Redémarrer les services
docker-compose -f docker-compose.prod.yml restart

# Mettre à jour l'application
git pull
docker-compose -f docker-compose.prod.yml up -d --build

# Voir les logs d'un service spécifique
docker logs -f stream_app
docker logs -f stream_postgres
docker logs -f stream_mongo
docker logs -f stream_redis
docker logs -f stream_nginx
```

## Sécurité

⚠️ **IMPORTANT**: Assurez-vous de:
1. Modifier tous les mots de passe par défaut dans `.env.prod`
2. Utiliser des clés SSH pour l'accès au serveur
3. Configurer un firewall (UFW)
4. Maintenir le système à jour
