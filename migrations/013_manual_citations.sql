-- Legacy receipts remain unresolved. This migration performs no data reclassification.
ALTER TABLE evidence ADD COLUMN IF NOT EXISTS source_verification jsonb NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE context_snapshots ADD COLUMN IF NOT EXISTS source_verifications jsonb NOT NULL DEFAULT '{}'::jsonb;
