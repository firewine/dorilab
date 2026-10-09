CREATE TABLE IF NOT EXISTS data_quality_assessments (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    quality_status text NOT NULL CHECK (quality_status IN ('VALID','LIMITED','INVALID','UNRESOLVED')),
    note text NOT NULL,
    actor text NOT NULL REFERENCES users(id),
    source_claim_version integer NOT NULL CHECK (source_claim_version >= 1),
    source_project_version integer NOT NULL CHECK (source_project_version >= 1),
    baseline_display_id text NOT NULL,
    product_configuration text NOT NULL,
    test_run text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verification_closures (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    result text NOT NULL CHECK (result IN ('SATISFIED','NOT_SATISFIED','INCONCLUSIVE')),
    closure_basis text NOT NULL CHECK (closure_basis IN ('COMPLIANCE','NON_COMPLIANCE','INCONCLUSIVE')),
    note text NOT NULL,
    actor text NOT NULL REFERENCES users(id),
    source_claim_version integer NOT NULL CHECK (source_claim_version >= 1),
    source_project_version integer NOT NULL CHECK (source_project_version >= 1),
    source_quality_assessment_id uuid NOT NULL REFERENCES data_quality_assessments(id) ON DELETE RESTRICT,
    scope jsonb NOT NULL,
    baseline_display_id text NOT NULL,
    product_configuration text NOT NULL,
    test_run text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (claim_id, source_claim_version, source_project_version)
);

CREATE INDEX IF NOT EXISTS data_quality_claim_idx
    ON data_quality_assessments(claim_id, source_claim_version, source_project_version, created_at);
CREATE INDEX IF NOT EXISTS verification_closure_project_idx
    ON verification_closures(project_id, created_at);
