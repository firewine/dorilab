CREATE TABLE IF NOT EXISTS project_documents (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    profile text NOT NULL CHECK (profile IN ('KASA','ECSS','NASA')),
    document_code text NOT NULL,
    title text NOT NULL,
    revision text NOT NULL,
    product_level text NOT NULL,
    clause_locator text NOT NULL,
    adoption_note text NOT NULL,
    status text NOT NULL DEFAULT 'UNCONFIRMED' CHECK (status IN ('UNCONFIRMED','ADOPTED','REJECTED')),
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    updated_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(project_id, profile, document_code)
);

CREATE TABLE IF NOT EXISTS tailoring_decisions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    profile text NOT NULL CHECK (profile IN ('KASA','ECSS','NASA')),
    title text NOT NULL,
    clause_locator text NOT NULL,
    reason text NOT NULL,
    owner text NOT NULL,
    status text NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT','APPROVED','REJECTED')),
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    decided_by text REFERENCES users(id),
    decided_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS project_documents_project_idx ON project_documents(project_id, profile);
CREATE INDEX IF NOT EXISTS tailoring_decisions_project_idx ON tailoring_decisions(project_id, profile, created_at);
