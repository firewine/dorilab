ALTER TABLE projects ADD COLUMN IF NOT EXISTS current_phase integer NOT NULL DEFAULT 0 CHECK (current_phase BETWEEN 0 AND 6);

CREATE TABLE IF NOT EXISTS review_gates (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    framework text NOT NULL CHECK (framework IN ('KASA','ECSS','NASA')),
    gate_key text NOT NULL CHECK (gate_key IN ('mission','srr','pdr','cdr','sir','trr','trb','accept','orr')),
    original_name text NOT NULL,
    display_name text NOT NULL,
    product_level text NOT NULL,
    description text NOT NULL,
    entry_criteria jsonb NOT NULL,
    success_criteria jsonb NOT NULL,
    authority text NOT NULL CHECK (authority IN ('REVIEWER_OR_APPROVER','APPROVER')),
    source_chapter integer NOT NULL CHECK (source_chapter BETWEEN 1 AND 20),
    sort_order integer NOT NULL,
    version integer NOT NULL DEFAULT 1,
    created_by text NOT NULL REFERENCES users(id),
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (project_id, framework, gate_key)
);

CREATE TABLE IF NOT EXISTS gate_decisions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    gate_id uuid NOT NULL REFERENCES review_gates(id) ON DELETE RESTRICT,
    disposition text NOT NULL CHECK (disposition IN ('APPROVED','REJECTED')),
    note text NOT NULL,
    actor text NOT NULL REFERENCES users(id),
    source_gate_version integer NOT NULL,
    source_project_version integer NOT NULL,
    baseline_display_id text NOT NULL,
    product_configuration text NOT NULL,
    test_run text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS phase_transition_decisions (
    id uuid PRIMARY KEY,
    project_id uuid NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    framework text NOT NULL CHECK (framework IN ('KASA','ECSS','NASA')),
    from_phase integer NOT NULL CHECK (from_phase BETWEEN 0 AND 6),
    to_phase integer NOT NULL CHECK (to_phase BETWEEN 0 AND 6),
    disposition text NOT NULL CHECK (disposition IN ('HOLD','GO')),
    note text NOT NULL,
    actor text NOT NULL REFERENCES users(id),
    source_project_version integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS review_gates_project_idx ON review_gates(project_id, framework, sort_order);
CREATE INDEX IF NOT EXISTS gate_decisions_gate_idx ON gate_decisions(gate_id, created_at);
CREATE INDEX IF NOT EXISTS phase_transition_project_idx ON phase_transition_decisions(project_id, created_at);
