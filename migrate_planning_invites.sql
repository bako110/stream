-- Migration : système d'invitations planning
DO $$ BEGIN
  CREATE TYPE invitestatus AS ENUM ('pending', 'accepted', 'declined');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS planning_invites (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entry_id      UUID NOT NULL REFERENCES planning_entries(id) ON DELETE CASCADE,
    inviter_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    invitee_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status        invitestatus NOT NULL DEFAULT 'pending',
    message       TEXT,
    responded_at  TIMESTAMP,
    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_planning_invites_entry_id   ON planning_invites(entry_id);
CREATE INDEX IF NOT EXISTS ix_planning_invites_invitee_id ON planning_invites(invitee_id);
CREATE INDEX IF NOT EXISTS ix_planning_invites_inviter_id ON planning_invites(inviter_id);
