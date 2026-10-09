CREATE TABLE IF NOT EXISTS configuration_changes (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    change_code text NOT NULL,
    from_baseline text NOT NULL,
    to_baseline text NOT NULL,
    from_configuration text NOT NULL,
    to_configuration text NOT NULL,
    from_test_run text NOT NULL,
    to_test_run text NOT NULL,
    reason text NOT NULL,
    impact_assessment jsonb NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPLIED','REJECTED')),
    requested_by text NOT NULL REFERENCES users(id),
    decided_by text REFERENCES users(id),
    decision_note text,
    source_project_version integer NOT NULL CHECK (source_project_version >= 1),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, change_code)
);

CREATE INDEX IF NOT EXISTS configuration_changes_project_idx
    ON configuration_changes(project_id, created_at DESC);
