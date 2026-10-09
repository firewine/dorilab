CREATE TABLE IF NOT EXISTS agent_contributions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id uuid,
    contribution_type text NOT NULL CHECK (
        contribution_type IN ('FACT_PROPOSAL','FINDING','HYPOTHESIS','CHALLENGE')
    ),
    target_object_type text NOT NULL,
    target_object_id text NOT NULL,
    content jsonb NOT NULL,
    evidence_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    status text NOT NULL DEFAULT 'PROPOSED' CHECK (
        status IN ('PROPOSED','ACCEPTED','REVISION_REQUESTED','REJECTED','SUPERSEDED')
    ),
    actor_type text NOT NULL CHECK (actor_type IN ('HUMAN','MODEL','TOOL','SYSTEM')),
    actor_id text NOT NULL,
    source_snapshot_id uuid REFERENCES context_snapshots(id) ON DELETE RESTRICT,
    source_job_id uuid REFERENCES review_jobs(id) ON DELETE RESTRICT,
    action_index integer CHECK (action_index IS NULL OR action_index >= 0),
    read_project_version integer NOT NULL CHECK (read_project_version >= 1),
    read_claim_version integer CHECK (read_claim_version IS NULL OR read_claim_version >= 1),
    content_hash text NOT NULL CHECK (length(content_hash) = 64),
    idempotency_key text NOT NULL,
    reviewed_by text REFERENCES users(id),
    review_note text,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    decided_at timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (claim_id, project_id) REFERENCES claims(id, project_id) ON DELETE RESTRICT,
    UNIQUE (project_id, idempotency_key)
);

CREATE UNIQUE INDEX IF NOT EXISTS agent_contributions_job_action_idx
    ON agent_contributions(source_job_id, action_index)
    WHERE source_job_id IS NOT NULL AND action_index IS NOT NULL;

CREATE INDEX IF NOT EXISTS agent_contributions_project_idx
    ON agent_contributions(project_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS work_items (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id uuid,
    work_type text NOT NULL CHECK (work_type IN ('TASK','TOOL_REQUEST','EVIDENCE_REQUEST')),
    title text NOT NULL,
    purpose text NOT NULL,
    input_refs jsonb NOT NULL DEFAULT '[]'::jsonb,
    assigned_role text NOT NULL CHECK (
        assigned_role IN ('EVIDENCE','ANALYSIS','CRITIC','ROUTER','HUMAN','TOOL')
    ),
    budget jsonb NOT NULL DEFAULT '{}'::jsonb,
    status text NOT NULL DEFAULT 'OPEN' CHECK (
        status IN ('OPEN','READY','RUNNING','WAITING_INPUT','WAITING_REVIEW','COMPLETED','CANCELLED','REJECTED')
    ),
    idempotency_key text NOT NULL,
    source_contribution_id uuid REFERENCES agent_contributions(id) ON DELETE RESTRICT,
    source_job_id uuid REFERENCES review_jobs(id) ON DELETE RESTRICT,
    evidence_request_id uuid UNIQUE REFERENCES evidence_requests(id) ON DELETE RESTRICT,
    source_project_version integer NOT NULL CHECK (source_project_version >= 1),
    source_claim_version integer CHECK (source_claim_version IS NULL OR source_claim_version >= 1),
    actor_type text NOT NULL CHECK (actor_type IN ('HUMAN','MODEL','TOOL','SYSTEM')),
    actor_id text NOT NULL,
    version integer NOT NULL DEFAULT 1 CHECK (version >= 1),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (claim_id, project_id) REFERENCES claims(id, project_id) ON DELETE RESTRICT,
    UNIQUE (project_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS work_items_project_idx
    ON work_items(project_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS object_dependencies (
    id bigserial PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    upstream_object_type text NOT NULL,
    upstream_object_id text NOT NULL,
    upstream_version integer NOT NULL CHECK (upstream_version >= 1),
    downstream_object_type text NOT NULL,
    downstream_object_id text NOT NULL,
    downstream_version integer NOT NULL CHECK (downstream_version >= 1),
    relationship text NOT NULL CHECK (
        relationship IN ('DERIVED_FROM','SUPPORTS','CONSTRAINS','INFORMS','RESPONDS_TO','REQUESTS')
    ),
    source_job_id uuid REFERENCES review_jobs(id) ON DELETE RESTRICT,
    created_by_type text NOT NULL CHECK (created_by_type IN ('HUMAN','MODEL','TOOL','SYSTEM')),
    created_by text NOT NULL,
    active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (
        project_id, upstream_object_type, upstream_object_id, upstream_version,
        downstream_object_type, downstream_object_id, downstream_version, relationship
    )
);

CREATE INDEX IF NOT EXISTS object_dependencies_reverse_idx
    ON object_dependencies(project_id, upstream_object_type, upstream_object_id)
    WHERE active;

CREATE INDEX IF NOT EXISTS object_dependencies_forward_idx
    ON object_dependencies(project_id, downstream_object_type, downstream_object_id)
    WHERE active;

CREATE TABLE IF NOT EXISTS board_events (
    id bigserial PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    event_type text NOT NULL,
    object_type text NOT NULL,
    object_id text NOT NULL,
    actor_type text NOT NULL CHECK (actor_type IN ('HUMAN','MODEL','TOOL','SYSTEM')),
    actor_id text NOT NULL,
    payload jsonb NOT NULL,
    source_version integer,
    result_version integer,
    idempotency_key text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS board_events_project_idx
    ON board_events(project_id, created_at DESC);
