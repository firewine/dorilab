-- Additive metadata only. Historical text/IDs are not used to classify records.
ALTER TABLE claims ADD COLUMN review_purpose text NOT NULL DEFAULT 'UNSPECIFIED'
    CHECK (review_purpose IN ('INPUT_READINESS','PRODUCT_PERFORMANCE','UNSPECIFIED'));
ALTER TABLE claim_revisions ADD COLUMN review_purpose text NOT NULL DEFAULT 'UNSPECIFIED'
    CHECK (review_purpose IN ('INPUT_READINESS','PRODUCT_PERFORMANCE','UNSPECIFIED'));
ALTER TABLE requirements ADD COLUMN review_purpose text NOT NULL DEFAULT 'UNSPECIFIED'
    CHECK (review_purpose IN ('INPUT_READINESS','PRODUCT_PERFORMANCE','UNSPECIFIED'));
ALTER TABLE context_snapshots ADD COLUMN review_purpose text NOT NULL DEFAULT 'UNSPECIFIED'
    CHECK (review_purpose IN ('INPUT_READINESS','PRODUCT_PERFORMANCE','UNSPECIFIED'));
ALTER TABLE verification_closures ADD COLUMN review_purpose text NOT NULL DEFAULT 'UNSPECIFIED'
    CHECK (review_purpose IN ('INPUT_READINESS','PRODUCT_PERFORMANCE','UNSPECIFIED'));
ALTER TABLE verification_closures ADD COLUMN source_snapshot_id uuid
    REFERENCES context_snapshots(id) ON DELETE RESTRICT;
