CREATE TABLE IF NOT EXISTS schema_migrations (
    version text PRIMARY KEY,
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS users (
    id text PRIMARY KEY,
    display_name text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS projects (
    id uuid PRIMARY KEY,
    display_id text UNIQUE NOT NULL,
    name text NOT NULL,
    framework text NOT NULL CHECK (framework IN ('KASA','ECSS','NASA')),
    framework_edition text,
    adoption_status text NOT NULL DEFAULT 'UNCONFIRMED',
    data_policy text NOT NULL DEFAULT 'LOCAL_ONLY' CHECK (data_policy IN ('LOCAL_ONLY','EXTERNAL_SYNTHETIC_ALLOWED','EXTERNAL_ALLOWED')),
    mode text NOT NULL DEFAULT 'DEMO' CHECK (mode IN ('DEMO','LIVE')),
    version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memberships (
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id text NOT NULL REFERENCES users(id),
    role text NOT NULL CHECK (role IN ('viewer','engineer','reviewer','approver')),
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (project_id, user_id)
);

CREATE TABLE IF NOT EXISTS claims (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    display_id text NOT NULL,
    question text NOT NULL,
    review_target text NOT NULL DEFAULT 'BM1',
    scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'OPEN',
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, display_id),
    UNIQUE(id, project_id)
);

CREATE TABLE IF NOT EXISTS artifact_versions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    kind text NOT NULL DEFAULT 'SOURCE',
    filename text NOT NULL,
    content_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    object_key text NOT NULL UNIQUE,
    rights_status text NOT NULL DEFAULT 'UNCONFIRMED',
    edition text,
    adopted boolean NOT NULL DEFAULT false,
    applicability_status text NOT NULL DEFAULT 'UNCONFIRMED',
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(id, project_id)
);

CREATE TABLE IF NOT EXISTS source_spans (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    locator text NOT NULL,
    quote text,
    sha256 text,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (artifact_id, project_id) REFERENCES artifact_versions(id, project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS evidence (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    source_span_id uuid REFERENCES source_spans(id),
    display_id text NOT NULL,
    kind text NOT NULL CHECK (kind IN ('REFERENCE','OBSERVATION')),
    basis text NOT NULL DEFAULT 'USER_PROVIDED',
    scope jsonb NOT NULL DEFAULT '{}'::jsonb,
    provenance jsonb NOT NULL DEFAULT '{}'::jsonb,
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, display_id),
    UNIQUE(id, project_id),
    FOREIGN KEY (artifact_id, project_id) REFERENCES artifact_versions(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS context_snapshots (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    claim_id uuid NOT NULL,
    claim_version integer NOT NULL,
    project_version integer NOT NULL,
    contract_id text NOT NULL,
    model_profile text NOT NULL,
    included_evidence_ids jsonb NOT NULL,
    excluded_evidence jsonb NOT NULL,
    messages jsonb NOT NULL,
    snapshot_sha256 text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (claim_id, project_id) REFERENCES claims(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS review_jobs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    snapshot_id uuid NOT NULL REFERENCES context_snapshots(id) ON DELETE RESTRICT,
    idempotency_key text NOT NULL,
    request_hash text NOT NULL,
    mode text NOT NULL CHECK (mode IN ('SIMULATED','REPLAY','LIVE_MODEL_RUN')),
    status text NOT NULL DEFAULT 'QUEUED',
    freshness text NOT NULL DEFAULT 'CURRENT',
    error_code text,
    error_detail text,
    leased_by text,
    leased_at timestamptz,
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS review_attempts (
    id uuid PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
    attempt_no integer NOT NULL,
    request_id text,
    boot_id text,
    status text NOT NULL,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE(job_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS model_runs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    job_id uuid NOT NULL UNIQUE REFERENCES review_jobs(id) ON DELETE RESTRICT,
    attempt_id uuid NOT NULL REFERENCES review_attempts(id) ON DELETE RESTRICT,
    raw_artifact_id uuid NOT NULL,
    raw_sha256 text NOT NULL,
    finish_reason text,
    token_usage jsonb NOT NULL DEFAULT '{}'::jsonb,
    receipt jsonb NOT NULL,
    request_id text,
    boot_id text,
    created_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (raw_artifact_id, project_id) REFERENCES artifact_versions(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS validations (
    id uuid PRIMARY KEY,
    model_run_id uuid NOT NULL UNIQUE REFERENCES model_runs(id) ON DELETE CASCADE,
    status text NOT NULL CHECK (status IN ('VALID','REJECTED')),
    errors jsonb NOT NULL DEFAULT '[]'::jsonb,
    parsed_output jsonb,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS human_reviews (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES review_jobs(id) ON DELETE RESTRICT,
    model_run_id uuid NOT NULL REFERENCES model_runs(id) ON DELETE RESTRICT,
    disposition text NOT NULL CHECK (disposition IN ('ACCEPTED','REVISION_REQUESTED','REJECTED')),
    edited_draft jsonb,
    note text,
    actor text NOT NULL REFERENCES users(id),
    source_job_version integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS audit_events (
    id bigserial PRIMARY KEY,
    project_id uuid,
    actor text NOT NULL,
    action text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    before_version integer,
    payload_hash text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS system_state (
    key text PRIMARY KEY,
    value jsonb NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS review_jobs_queue_idx ON review_jobs(status, created_at);
CREATE INDEX IF NOT EXISTS artifacts_project_idx ON artifact_versions(project_id, created_at);
CREATE INDEX IF NOT EXISTS evidence_project_idx ON evidence(project_id, created_at);
