ALTER TABLE projects ADD COLUMN IF NOT EXISTS baseline_display_id text NOT NULL DEFAULT 'BL-001';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS product_configuration text NOT NULL DEFAULT 'UNASSIGNED';
ALTER TABLE projects ADD COLUMN IF NOT EXISTS test_run text NOT NULL DEFAULT 'UNASSIGNED';

CREATE TABLE IF NOT EXISTS claim_revisions (
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    version integer NOT NULL CHECK (version >= 1),
    question text NOT NULL,
    scope jsonb NOT NULL,
    status text NOT NULL,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (claim_id, version)
);

CREATE TABLE IF NOT EXISTS requirements (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    display_id text NOT NULL,
    level text NOT NULL CHECK (level IN ('MISSION','SYSTEM','SUBSYSTEM','EQUIPMENT')),
    parent_ref text NOT NULL,
    statement text NOT NULL,
    verification_method text NOT NULL,
    owner text NOT NULL,
    claim_id uuid REFERENCES claims(id) ON DELETE SET NULL,
    claim_label text NOT NULL,
    source_chapter integer NOT NULL CHECK (source_chapter BETWEEN 1 AND 20),
    sort_order integer NOT NULL DEFAULT 0,
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, display_id)
);

CREATE INDEX IF NOT EXISTS requirements_project_idx ON requirements(project_id, sort_order, display_id);
CREATE INDEX IF NOT EXISTS claim_revisions_project_idx ON claim_revisions(project_id, claim_id, version);

INSERT INTO claim_revisions(claim_id,project_id,version,question,scope,status,created_by,created_at)
SELECT id,project_id,version,question,scope,status,created_by,created_at FROM claims
ON CONFLICT (claim_id,version) DO NOTHING;
