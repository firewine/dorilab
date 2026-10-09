-- Additive local draft authoring only. Dataset/review/remote execution are not enabled.
CREATE TABLE IF NOT EXISTS learning_examples (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    title text NOT NULL,
    family_key text NOT NULL,
    split text NOT NULL CHECK (split IN ('TRAIN','EVALUATION')),
    origin text NOT NULL CHECK (origin IN ('HUMAN_AUTHORED','SYNTHETIC_HUMAN_AUTHORED')),
    source_chunk_id uuid NOT NULL,
    source_snapshot jsonb NOT NULL,
    prompt text NOT NULL,
    completion text NOT NULL,
    content_sha256 text NOT NULL CHECK (length(content_sha256)=64),
    input_sha256 text NOT NULL CHECK (length(input_sha256)=64),
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','REJECTED')),
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    reviewed_by text REFERENCES users(id),
    reviewed_at timestamptz,
    review_note text,
    data_use_confirmed boolean NOT NULL DEFAULT false,
    idempotency_key text NOT NULL,
    request_sha256 text NOT NULL,
    UNIQUE (id,project_id),
    UNIQUE (project_id,idempotency_key),
    FOREIGN KEY (source_chunk_id,project_id) REFERENCES document_chunks(id,project_id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS learning_examples_family ON learning_examples(project_id,family_key,split);
