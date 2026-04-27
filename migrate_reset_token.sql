-- Migration: ajout des colonnes reset_token et reset_token_expires sur la table users
-- À exécuter une seule fois sur le serveur de production

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS reset_token VARCHAR(128),
  ADD COLUMN IF NOT EXISTS reset_token_expires TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_users_reset_token ON users(reset_token);
