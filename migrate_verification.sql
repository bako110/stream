-- Migration : ajout du système de vérification FoliX
-- À exécuter : docker exec -i <postgres_container> psql -U stream -d streaming < migrate_verification.sql

CREATE TYPE IF NOT EXISTS verificationstatus AS ENUM ('none', 'pending', 'approved', 'rejected');

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS verification_status     verificationstatus NOT NULL DEFAULT 'none',
    ADD COLUMN IF NOT EXISTS verification_note       TEXT,
    ADD COLUMN IF NOT EXISTS verification_requested_at TIMESTAMP,
    ADD COLUMN IF NOT EXISTS verification_reviewed_at  TIMESTAMP;

CREATE INDEX IF NOT EXISTS ix_users_verification_status ON users(verification_status);
