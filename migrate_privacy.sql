-- Migration : ajout des colonnes de confidentialité sur la table users
-- À exécuter UNE SEULE FOIS sur la base de production

ALTER TABLE users
  ADD COLUMN IF NOT EXISTS privacy_profile_public  BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS privacy_show_activity   BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS privacy_show_location   BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS privacy_allow_messages  BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS privacy_show_online     BOOLEAN NOT NULL DEFAULT TRUE,
  ADD COLUMN IF NOT EXISTS privacy_show_phone      BOOLEAN NOT NULL DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS privacy_show_birthday   BOOLEAN NOT NULL DEFAULT TRUE;
