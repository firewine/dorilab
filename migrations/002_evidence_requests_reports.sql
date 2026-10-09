CREATE TABLE IF NOT EXISTS evidence_requests (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES review_jobs(id) ON DELETE CASCADE,
    claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE RESTRICT,
    requested_item text NOT NULL,
    source text NOT NULL CHECK (source IN ('MODEL','HUMAN')),
    assignee text REFERENCES users(id),
    status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','RECEIVED','ACCEPTED','REJECTED')),
    submitted_evidence_id uuid,
    created_by text NOT NULL REFERENCES users(id),
    received_by text REFERENCES users(id),
    decided_by text REFERENCES users(id),
    decision_note text,
    version integer NOT NULL DEFAULT 1,
    created_at timestamptz NOT NULL DEFAULT now(),
    received_at timestamptz,
    decided_at timestamptz,
    UNIQUE(job_id, requested_item),
    FOREIGN KEY (submitted_evidence_id, project_id) REFERENCES evidence(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS report_exports (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    job_id uuid NOT NULL REFERENCES review_jobs(id) ON DELETE RESTRICT,
    kind text NOT NULL DEFAULT 'REVIEW_MARKDOWN' CHECK (kind IN ('REVIEW_MARKDOWN')),
    filename text NOT NULL,
    content_type text NOT NULL,
    byte_size bigint NOT NULL CHECK (byte_size >= 0),
    sha256 text NOT NULL CHECK (length(sha256) = 64),
    object_key text NOT NULL UNIQUE,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(job_id, sha256)
);

CREATE INDEX IF NOT EXISTS evidence_requests_project_idx ON evidence_requests(project_id, status, created_at);
CREATE INDEX IF NOT EXISTS report_exports_project_idx ON report_exports(project_id, created_at);
