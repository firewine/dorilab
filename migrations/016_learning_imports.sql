-- Question-set review is separate from verified paper chunks and frozen datasets.
-- Original rows and terminal decisions are retained; no legacy labels are promoted.
CREATE TABLE IF NOT EXISTS learning_imports (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    artifact_id uuid NOT NULL,
    source_snapshot jsonb NOT NULL,
    source_sha256 text NOT NULL CHECK (length(source_sha256)=64),
    metadata_sha256 text NOT NULL CHECK (length(metadata_sha256)=64),
    importer_version text NOT NULL,
    format text NOT NULL,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    idempotency_key text NOT NULL,
    request_sha256 text NOT NULL CHECK (length(request_sha256)=64),
    UNIQUE (id,project_id),
    UNIQUE (project_id,idempotency_key),
    UNIQUE (project_id,source_sha256,metadata_sha256,importer_version),
    FOREIGN KEY (artifact_id,project_id) REFERENCES artifact_versions(id,project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS learning_import_items (
    id uuid PRIMARY KEY,
    import_id uuid NOT NULL,
    project_id uuid NOT NULL,
    question_id text NOT NULL,
    category text NOT NULL,
    split text NOT NULL CHECK (split IN ('TRAIN','EVALUATION')),
    family_key text,
    original_payload jsonb NOT NULL,
    original_sha256 text NOT NULL CHECK (length(original_sha256)=64),
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','REJECTED')),
    version integer NOT NULL DEFAULT 1 CHECK (version>=1),
    UNIQUE (id,project_id),
    UNIQUE (import_id,question_id),
    FOREIGN KEY (import_id,project_id) REFERENCES learning_imports(id,project_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS learning_import_items_family ON learning_import_items(project_id,family_key,split);

-- Also retain keys for reuploads that resolve to an existing set.
CREATE TABLE IF NOT EXISTS learning_import_requests (
    project_id uuid NOT NULL,
    idempotency_key text NOT NULL,
    request_sha256 text NOT NULL CHECK (length(request_sha256)=64),
    import_id uuid NOT NULL,
    PRIMARY KEY (project_id,idempotency_key),
    FOREIGN KEY (import_id,project_id) REFERENCES learning_imports(id,project_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS learning_import_decisions (
    id uuid PRIMARY KEY,
    item_id uuid NOT NULL UNIQUE,
    project_id uuid NOT NULL,
    decision text NOT NULL CHECK (decision IN ('APPROVED','REJECTED')),
    from_version integer NOT NULL,
    to_version integer NOT NULL,
    note text NOT NULL,
    reviewed_prompt text,
    reviewed_completion text,
    review_confirmed boolean NOT NULL,
    reviewed_by text NOT NULL REFERENCES users(id),
    reviewed_at timestamptz NOT NULL DEFAULT now(),
    FOREIGN KEY (item_id,project_id) REFERENCES learning_import_items(id,project_id) ON DELETE CASCADE,
    CHECK (to_version=from_version+1),
    CHECK (decision<>'APPROVED' OR (review_confirmed AND reviewed_prompt IS NOT NULL AND reviewed_completion IS NOT NULL))
);
