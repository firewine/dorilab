ALTER TABLE artifact_versions
    ADD COLUMN IF NOT EXISTS usage_purpose text NOT NULL DEFAULT 'OPERATIONAL_EVIDENCE'
    CHECK (usage_purpose IN ('OPERATIONAL_EVIDENCE','TRAINING','EVALUATION_GOLD'));

CREATE TABLE IF NOT EXISTS document_parser_runs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    parser_name text NOT NULL,
    parser_version text NOT NULL,
    chunker_version text NOT NULL,
    source_sha256 text NOT NULL CHECK (length(source_sha256) = 64),
    status text NOT NULL CHECK (status IN ('PROCESSING','COMPLETED','FAILED')),
    page_count integer NOT NULL DEFAULT 0 CHECK (page_count >= 0),
    chunk_count integer NOT NULL DEFAULT 0 CHECK (chunk_count >= 0),
    issues jsonb NOT NULL DEFAULT '[]'::jsonb,
    receipt jsonb,
    receipt_sha256 text CHECK (receipt_sha256 IS NULL OR length(receipt_sha256) = 64),
    error_code text,
    error_detail text,
    created_by text NOT NULL REFERENCES users(id),
    started_at timestamptz NOT NULL DEFAULT now(),
    finished_at timestamptz,
    UNIQUE(id, project_id),
    FOREIGN KEY (artifact_id, project_id) REFERENCES artifact_versions(id, project_id) ON DELETE CASCADE
);

CREATE UNIQUE INDEX IF NOT EXISTS document_parser_runs_completed_release
    ON document_parser_runs(artifact_id, parser_version, chunker_version)
    WHERE status = 'COMPLETED';

CREATE TABLE IF NOT EXISTS document_chunks (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL,
    artifact_id uuid NOT NULL,
    parser_run_id uuid NOT NULL,
    source_span_id uuid NOT NULL REFERENCES source_spans(id) ON DELETE CASCADE,
    ordinal integer NOT NULL CHECK (ordinal >= 0),
    content_kind text NOT NULL DEFAULT 'BODY_TEXT'
        CHECK (content_kind IN ('BODY_TEXT','TABLE_TEXT','FIGURE_TEXT')),
    page_start integer CHECK (page_start IS NULL OR page_start >= 1),
    page_end integer CHECK (page_end IS NULL OR page_end >= page_start),
    section_path jsonb NOT NULL DEFAULT '[]'::jsonb,
    locator text NOT NULL,
    chunk_text text NOT NULL CHECK (length(chunk_text) > 0),
    char_count integer NOT NULL CHECK (char_count > 0),
    text_sha256 text NOT NULL CHECK (length(text_sha256) = 64),
    metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
    version integer NOT NULL DEFAULT 1,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('simple', chunk_text)) STORED,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(parser_run_id, ordinal),
    UNIQUE(id, project_id),
    FOREIGN KEY (artifact_id, project_id) REFERENCES artifact_versions(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (parser_run_id, project_id) REFERENCES document_parser_runs(id, project_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS document_chunks_search_vector_idx
    ON document_chunks USING GIN(search_vector);
CREATE INDEX IF NOT EXISTS document_chunks_artifact_idx
    ON document_chunks(project_id, artifact_id, ordinal);

CREATE TABLE IF NOT EXISTS retrieval_runs (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    claim_id uuid NOT NULL,
    claim_version integer NOT NULL CHECK (claim_version >= 1),
    project_version integer NOT NULL CHECK (project_version >= 1),
    query text NOT NULL CHECK (length(query) > 0),
    artifact_filter jsonb NOT NULL DEFAULT '[]'::jsonb,
    filter_policy text NOT NULL,
    parser_version text NOT NULL,
    index_version text NOT NULL,
    top_k integer NOT NULL CHECK (top_k BETWEEN 1 AND 20),
    status text NOT NULL CHECK (status IN ('COMPLETED','FAILED')),
    request_hash text NOT NULL CHECK (length(request_hash) = 64),
    idempotency_key text NOT NULL,
    candidate_count integer NOT NULL DEFAULT 0 CHECK (candidate_count >= 0),
    selected_count integer NOT NULL DEFAULT 0 CHECK (selected_count >= 0),
    receipt jsonb NOT NULL,
    receipt_sha256 text NOT NULL CHECK (length(receipt_sha256) = 64),
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    completed_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, idempotency_key),
    UNIQUE(id, project_id),
    FOREIGN KEY (claim_id, project_id) REFERENCES claims(id, project_id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS retrieval_results (
    retrieval_run_id uuid NOT NULL,
    project_id uuid NOT NULL,
    chunk_id uuid NOT NULL,
    candidate_rank integer NOT NULL CHECK (candidate_rank >= 1),
    score double precision NOT NULL CHECK (score >= 0),
    selected boolean NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (retrieval_run_id, chunk_id),
    UNIQUE(retrieval_run_id, candidate_rank),
    FOREIGN KEY (retrieval_run_id, project_id) REFERENCES retrieval_runs(id, project_id) ON DELETE CASCADE,
    FOREIGN KEY (chunk_id, project_id) REFERENCES document_chunks(id, project_id) ON DELETE RESTRICT
);

ALTER TABLE context_snapshots
    ADD COLUMN IF NOT EXISTS retrieval_run_id uuid REFERENCES retrieval_runs(id) ON DELETE RESTRICT,
    ADD COLUMN IF NOT EXISTS retrieved_chunk_ids jsonb NOT NULL DEFAULT '[]'::jsonb,
    ADD COLUMN IF NOT EXISTS retrieval_receipt jsonb,
    ADD COLUMN IF NOT EXISTS context_budget jsonb NOT NULL DEFAULT '{}'::jsonb;

CREATE INDEX IF NOT EXISTS retrieval_runs_project_claim_idx
    ON retrieval_runs(project_id, claim_id, created_at DESC);
