CREATE TABLE IF NOT EXISTS orchestration_runs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id uuid NOT NULL UNIQUE REFERENCES review_jobs(id) ON DELETE CASCADE,
    graph_id text NOT NULL,
    graph_version integer NOT NULL CHECK (graph_version >= 1),
    origin text NOT NULL CHECK (origin IN ('NATIVE','LEGACY_PROJECTION')),
    status text NOT NULL CHECK (
        status IN ('QUEUED','RUNNING','WAITING_HUMAN','COMPLETED','FAILED','UNKNOWN_OUTCOME','STALE')
    ),
    current_node text NOT NULL CHECK (
        current_node IN (
            'SELECT_TASK','SCOPE_GATE','RETRIEVE_CONTEXT','BUILD_CONTEXT','SOURCE_REVIEW',
            'VALIDATE','UPDATE_BLACKBOARD','ROUTE','WAIT_HUMAN','RESUME','COMPLETE'
        )
    ),
    state jsonb NOT NULL DEFAULT '{}'::jsonb,
    checkpoint_seq integer NOT NULL DEFAULT 0 CHECK (checkpoint_seq >= 0),
    checkpoint_sha256 text CHECK (checkpoint_sha256 IS NULL OR length(checkpoint_sha256) = 64),
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    started_at timestamptz,
    completed_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orchestration_node_attempts (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES orchestration_runs(id) ON DELETE CASCADE,
    node_key text NOT NULL CHECK (
        node_key IN (
            'SELECT_TASK','SCOPE_GATE','RETRIEVE_CONTEXT','BUILD_CONTEXT','SOURCE_REVIEW',
            'VALIDATE','UPDATE_BLACKBOARD','ROUTE','WAIT_HUMAN','RESUME','COMPLETE'
        )
    ),
    attempt_no integer NOT NULL CHECK (attempt_no >= 1),
    status text NOT NULL CHECK (
        status IN ('RUNNING','COMPLETED','FAILED','WAITING','UNKNOWN_OUTCOME','RECOVERED','SKIPPED')
    ),
    input_sha256 text CHECK (input_sha256 IS NULL OR length(input_sha256) = 64),
    output_sha256 text CHECK (output_sha256 IS NULL OR length(output_sha256) = 64),
    input_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    output_summary jsonb NOT NULL DEFAULT '{}'::jsonb,
    worker_id text,
    error_code text,
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE (run_id, node_key, attempt_no)
);

CREATE UNIQUE INDEX IF NOT EXISTS orchestration_node_open_attempt_idx
    ON orchestration_node_attempts(run_id, node_key)
    WHERE finished_at IS NULL;

CREATE TABLE IF NOT EXISTS orchestration_checkpoints (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL REFERENCES orchestration_runs(id) ON DELETE CASCADE,
    sequence integer NOT NULL CHECK (sequence >= 1),
    node_key text NOT NULL,
    run_status text NOT NULL,
    event_type text NOT NULL,
    state_snapshot jsonb NOT NULL,
    state_sha256 text NOT NULL CHECK (length(state_sha256) = 64),
    basis text NOT NULL CHECK (basis IN ('APP_SHA256','LEGACY_PROJECTION')),
    actor_type text NOT NULL CHECK (actor_type IN ('HUMAN','MODEL','TOOL','SYSTEM')),
    actor_id text NOT NULL,
    idempotency_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (run_id, sequence),
    UNIQUE (run_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS orchestration_runs_project_idx
    ON orchestration_runs(project_id, status, updated_at DESC);

CREATE INDEX IF NOT EXISTS orchestration_node_attempts_run_idx
    ON orchestration_node_attempts(run_id, started_at);

CREATE INDEX IF NOT EXISTS orchestration_checkpoints_run_idx
    ON orchestration_checkpoints(run_id, sequence);
