-- Migration : ajout de la colonne video_url sur la table episodes
ALTER TABLE IF EXISTS episodes ADD COLUMN IF NOT EXISTS video_url VARCHAR(500);
